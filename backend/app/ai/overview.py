"""Read-only overview tools for the AI agent: a whole-workspace snapshot and a per-customer
profile. Both are plain tenant-scoped aggregates over the caller's own workspace (demo or
real), so the assistant can answer "how is the business doing?" or "tell me about ACME"
from facts instead of guessing. Amounts come back in cents plus *_dollars."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.billing.models import Invoice
from app.core.tenancy import TenantContext
from app.customers.models import Customer
from app.payments.models import Payment
from app.products.models import PricePlan
from app.subscriptions.models import Subscription
from app.usage.models import UsageAggregate


def _scope(model, ctx: TenantContext):
    return model.tenant_id == ctx.tenant_id, model.workspace_type == ctx.workspace_type


def _dollars(cents: int | None) -> float:
    return round((cents or 0) / 100, 2)


def _count_by(db: Session, ctx: TenantContext, model, column) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).where(*_scope(model, ctx)).group_by(column)).all()
    return {str(k): int(v) for k, v in rows}


def business_overview(db: Session, ctx: TenantContext, params: dict) -> dict:
    invoice_rows = db.execute(
        select(Invoice.status, func.count(), func.coalesce(func.sum(Invoice.subtotal_cents), 0))
        .where(*_scope(Invoice, ctx))
        .group_by(Invoice.status)
    ).all()
    invoices = {s: {"count": int(n), "total_cents": int(t), "total_dollars": _dollars(t)} for s, n, t in invoice_rows}

    payment_rows = db.execute(
        select(Payment.status, func.count(), func.coalesce(func.sum(Payment.amount_cents), 0))
        .where(*_scope(Payment, ctx))
        .group_by(Payment.status)
    ).all()
    payments = {s: {"count": int(n), "total_cents": int(t), "total_dollars": _dollars(t)} for s, n, t in payment_rows}

    usage_rows = db.execute(
        select(UsageAggregate.event_type, func.coalesce(func.sum(UsageAggregate.total_quantity), 0))
        .where(*_scope(UsageAggregate, ctx))
        .group_by(UsageAggregate.event_type)
    ).all()

    plan_names = {p.id: p.name for p in db.execute(select(PricePlan).where(*_scope(PricePlan, ctx))).scalars()}
    subs_by_plan: dict[str, int] = {}
    for plan_id, n in db.execute(
        select(Subscription.price_plan_id, func.count()).where(*_scope(Subscription, ctx)).group_by(Subscription.price_plan_id)
    ).all():
        name = plan_names.get(plan_id, "unknown")
        subs_by_plan[name] = subs_by_plan.get(name, 0) + int(n)

    billed = sum(v["total_cents"] for k, v in invoices.items() if k != "void")
    return {
        "customers_total": sum(_count_by(db, ctx, Customer, Customer.status).values()),
        "customers_by_country": _count_by(db, ctx, Customer, Customer.country),
        "subscriptions_by_status": _count_by(db, ctx, Subscription, Subscription.status),
        "subscriptions_by_plan": subs_by_plan,
        "invoices_by_status": invoices,
        "invoices_total_count": sum(v["count"] for v in invoices.values()),
        "total_billed_cents": billed,
        "total_billed_dollars": _dollars(billed),
        "paid_revenue_dollars": invoices.get("paid", {}).get("total_dollars", 0.0),
        "outstanding_unpaid_dollars": invoices.get("finalized", {}).get("total_dollars", 0.0),
        "payments_by_status": payments,
        "usage_totals": {t: int(q) for t, q in usage_rows},
    }


def _resolve_customers(db: Session, ctx: TenantContext, params: dict) -> list[Customer]:
    if params.get("customer_id"):
        row = db.execute(select(Customer).where(*_scope(Customer, ctx), Customer.id == params["customer_id"])).scalar_one_or_none()
        return [row] if row else []
    fragment = (params.get("name_contains") or "").strip().lower()
    if not fragment:
        return []
    stmt = select(Customer).where(*_scope(Customer, ctx), func.lower(Customer.name).contains(fragment)).limit(10)
    return list(db.execute(stmt).scalars())


def customer_overview(db: Session, ctx: TenantContext, params: dict) -> dict:
    matches = _resolve_customers(db, ctx, params)
    if not matches:
        return {"found": False, "note": "No customer in this workspace matches that name or id."}
    if len(matches) > 1:
        return {
            "found": False,
            "note": "Several customers match; ask the user which one they mean.",
            "candidates": [{"id": c.id, "name": c.name, "country": c.country} for c in matches],
        }
    c = matches[0]
    plan_names = {p.id: p.name for p in db.execute(select(PricePlan).where(*_scope(PricePlan, ctx))).scalars()}
    subs = list(db.execute(select(Subscription).where(*_scope(Subscription, ctx), Subscription.customer_id == c.id)).scalars())
    invoices = list(
        db.execute(
            select(Invoice).where(*_scope(Invoice, ctx), Invoice.customer_id == c.id).order_by(Invoice.period_start.desc())
        ).scalars()
    )
    payments = list(db.execute(select(Payment).where(*_scope(Payment, ctx), Payment.customer_id == c.id)).scalars())
    sub_ids = [s.id for s in subs]
    usage_rows = (
        db.execute(
            select(UsageAggregate.event_type, func.coalesce(func.sum(UsageAggregate.total_quantity), 0))
            .where(*_scope(UsageAggregate, ctx), UsageAggregate.subscription_id.in_(sub_ids))
            .group_by(UsageAggregate.event_type)
        ).all()
        if sub_ids
        else []
    )

    def by_status(items, amount_attr):
        out: dict[str, dict] = {}
        for it in items:
            slot = out.setdefault(it.status, {"count": 0, "total_cents": 0})
            slot["count"] += 1
            slot["total_cents"] += getattr(it, amount_attr)
        for slot in out.values():
            slot["total_dollars"] = _dollars(slot["total_cents"])
        return out

    return {
        "found": True,
        "customer": {"id": c.id, "name": c.name, "email": c.email, "country": c.country, "status": c.status},
        "subscriptions": [
            {"id": s.id, "plan": plan_names.get(s.price_plan_id, "unknown"), "status": s.status, "users": s.quantity_users}
            for s in subs
        ],
        "invoices_by_status": by_status(invoices, "subtotal_cents"),
        "invoices_total_billed_dollars": _dollars(sum(i.subtotal_cents for i in invoices if i.status != "void")),
        "recent_invoices": [
            {"id": i.id, "period": f"{i.period_start} to {i.period_end}", "status": i.status, "amount_dollars": _dollars(i.subtotal_cents)}
            for i in invoices[:5]
        ],
        "payments_by_status": by_status(payments, "amount_cents"),
        "usage_totals": {t: int(q) for t, q in usage_rows},
    }
