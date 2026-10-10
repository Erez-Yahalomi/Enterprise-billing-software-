"""Safe, read-only data analysis for the AI agent.

The model never writes SQL. Instead it fills in a small structured request (dataset,
group_by, metric, field, filters, top_n) that this module executes with fixed, tenant-scoped
queries — so a natural-language question like "top 5 customers by revenue" or "failed
payments by country" becomes a bounded aggregation over the caller's own workspace only.
"""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.models import Invoice
from app.core.tenancy import TenantContext
from app.customers.models import Customer
from app.payments.models import Payment
from app.products.models import PricePlan
from app.subscriptions.models import Subscription
from app.usage.models import UsageAggregate

DATASETS = {
    "customers": {"group_by": ["country", "status"], "fields": []},
    "subscriptions": {"group_by": ["plan", "status", "customer", "country"], "fields": ["quantity_users"]},
    "invoices": {"group_by": ["customer", "status", "plan", "month", "country"], "fields": ["subtotal_cents"]},
    "payments": {"group_by": ["customer", "status", "month", "country"], "fields": ["amount_cents"]},
    "usage": {"group_by": ["event_type", "customer", "plan", "month", "country"], "fields": ["total_quantity"]},
}
METRICS = ("count", "sum", "avg", "max", "min")
MAX_ROWS = 200_000
MONEY_FIELDS = {"subtotal_cents", "amount_cents"}

# Real status values: invoices draft|finalized|paid|void — "finalized" is issued-and-not-yet-paid;
# payments pending|succeeded|failed; subscriptions active|trialing|paused|canceled.
# Everyday words map onto them so "unpaid invoices" means finalized ones.
_UNPAID = ("unpaid", "open", "outstanding", "overdue", "pending", "issued", "due", "not paid")
STATUS_ALIASES = {
    **{("invoices", w): "finalized" for w in _UNPAID},
    ("invoices", "settled"): "paid",
    ("payments", "success"): "succeeded",
    ("payments", "successful"): "succeeded",
    ("payments", "paid"): "succeeded",
    ("payments", "failure"): "failed",
    ("subscriptions", "cancelled"): "canceled",
    ("subscriptions", "inactive"): "canceled",
}


def _scoped(model, ctx: TenantContext):
    return select(model).where(model.tenant_id == ctx.tenant_id, model.workspace_type == ctx.workspace_type)


def _load_rows(db: Session, ctx: TenantContext, dataset: str) -> list[dict]:
    customers = {c.id: c for c in db.execute(_scoped(Customer, ctx)).scalars()}
    plans = {p.id: p for p in db.execute(_scoped(PricePlan, ctx)).scalars()}
    subs = {s.id: s for s in db.execute(_scoped(Subscription, ctx)).scalars()}

    def cust_name(cid):
        return customers[cid].name if cid in customers else cid

    def cust_country(cid):
        return (customers[cid].country if cid in customers else None) or "unknown"

    def sub_plan(sid):
        sub = subs.get(sid)
        plan = plans.get(sub.price_plan_id) if sub else None
        return plan.name if plan else "unknown"

    rows: list[dict] = []
    if dataset == "customers":
        for c in customers.values():
            rows.append({"country": c.country or "unknown", "status": c.status, "name": c.name})
    elif dataset == "subscriptions":
        for s in subs.values():
            plan = plans.get(s.price_plan_id)
            rows.append(
                {
                    "plan": plan.name if plan else "unknown",
                    "status": s.status,
                    "customer": cust_name(s.customer_id),
                    "country": cust_country(s.customer_id),
                    "quantity_users": s.quantity_users,
                }
            )
    elif dataset == "invoices":
        for i in db.execute(_scoped(Invoice, ctx).limit(MAX_ROWS)).scalars():
            rows.append(
                {
                    "customer": cust_name(i.customer_id),
                    "status": i.status,
                    "plan": sub_plan(i.subscription_id),
                    "month": i.period_start.isoformat()[:7],
                    "country": cust_country(i.customer_id),
                    "subtotal_cents": i.subtotal_cents,
                }
            )
    elif dataset == "payments":
        invoice_month = {i.id: i.period_start.isoformat()[:7] for i in db.execute(_scoped(Invoice, ctx)).scalars()}
        for p in db.execute(_scoped(Payment, ctx).limit(MAX_ROWS)).scalars():
            rows.append(
                {
                    "customer": cust_name(p.customer_id),
                    "status": p.status,
                    "month": invoice_month.get(p.invoice_id, "unknown"),
                    "country": cust_country(p.customer_id),
                    "amount_cents": p.amount_cents,
                }
            )
    elif dataset == "usage":
        for u in db.execute(_scoped(UsageAggregate, ctx).limit(MAX_ROWS)).scalars():
            sub = subs.get(u.subscription_id)
            cid = sub.customer_id if sub else None
            rows.append(
                {
                    "event_type": u.event_type,
                    "customer": cust_name(cid) if cid else "unknown",
                    "plan": sub_plan(u.subscription_id),
                    "month": u.period_date.isoformat()[:7],
                    "country": cust_country(cid) if cid else "unknown",
                    "total_quantity": u.total_quantity,
                }
            )
    return rows


def analyze_data(db: Session, ctx: TenantContext, params: dict) -> dict:
    dataset = params.get("dataset")
    if dataset not in DATASETS:
        return {"error": f"dataset must be one of {sorted(DATASETS)}"}
    spec = DATASETS[dataset]

    group_by = params.get("group_by") or None
    if group_by and group_by not in spec["group_by"]:
        return {"error": f"for '{dataset}', group_by must be one of {spec['group_by']} (or omitted)"}

    metric = params.get("metric") or "count"
    if metric not in METRICS:
        return {"error": f"metric must be one of {list(METRICS)}"}

    field = params.get("field")
    if metric != "count":
        if field not in spec["fields"]:
            return {"error": f"for '{dataset}' with metric '{metric}', field must be one of {spec['fields']}"}

    filters = params.get("filters") or {}
    if not isinstance(filters, dict):
        return {"error": "filters must be an object like {\"status\": \"failed\"}"}

    all_rows = _load_rows(db, ctx, dataset)
    rows = all_rows
    applied_filters: dict = {}
    for key, wanted in filters.items():
        if wanted in (None, ""):
            continue
        if all_rows and key not in all_rows[0]:
            return {"error": f"'{key}' is not a filterable column of '{dataset}'. Available: {sorted(all_rows[0])}"}
        wanted_norm = str(wanted).strip().lower()
        if key == "status":
            wanted_norm = STATUS_ALIASES.get((dataset, wanted_norm), wanted_norm)
        applied_filters[key] = wanted_norm
        rows = [r for r in rows if str(r.get(key, "")).lower() == wanted_norm]

    if not rows and applied_filters and all_rows:
        # A bad filter value must never look like "there is no data" — tell the model what exists.
        return {
            "dataset": dataset,
            "rows_considered": 0,
            "filters": applied_filters,
            "warning": "No rows matched these filters. This may be a wrong filter value, not an absence of data.",
            "available_values": {
                key: sorted({str(r.get(key)) for r in all_rows})[:30] for key in applied_filters
            },
            "results": [],
        }

    def aggregate(items: list[dict]) -> float:
        if metric == "count":
            return len(items)
        values = [r[field] for r in items]
        if not values:
            return 0
        return {"sum": sum, "avg": lambda v: sum(v) / len(v), "max": max, "min": min}[metric](values)

    if group_by:
        buckets: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            buckets[str(r.get(group_by, "unknown"))].append(r)
        groups = [{"group": k, "value": aggregate(v), "rows": len(v)} for k, v in buckets.items()]
    else:
        groups = [{"group": "all", "value": aggregate(rows), "rows": len(rows)}]

    descending = (params.get("order") or "desc") != "asc"
    groups.sort(key=lambda g: g["value"], reverse=descending)
    top_n = max(1, min(int(params.get("top_n") or 10), 50))
    total_groups = len(groups)
    groups = groups[:top_n]

    is_money = field in MONEY_FIELDS and metric != "count"
    if is_money:
        for g in groups:
            g["value_dollars"] = round(g["value"] / 100, 2)

    return {
        "dataset": dataset,
        "metric": metric,
        "field": field,
        "group_by": group_by,
        "filters": filters,
        "rows_considered": len(rows),
        "groups_total": total_groups,
        "groups_shown": len(groups),
        "unit": "cents (see value_dollars)" if is_money else ("count" if metric == "count" else "raw quantity"),
        "results": groups,
    }
