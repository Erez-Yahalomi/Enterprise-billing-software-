"""The AI agent's tool registry.

Every tool the agent can ever call is declared here, tagged with a guardrail tier:

- Tier A: read-only, executes automatically.
- Tier B: low-risk write, executes automatically but is always audit-logged.
- Tier C: protected — the gateway never runs the handler directly; it creates an
  ApprovalRequest instead, and the handler only runs once a human approves it.

There is deliberately no Tier D entry for SQL execution, shell access, secrets, or direct
ledger/audit mutation: those tools simply do not exist here, so the gateway rejects them
before authorization is even consulted (see app.ai.gateway).

`parameters` is a JSON-schema dict (OpenAPI-style) describing each tool's arguments. It is
used to build the function-calling declarations handed to a real LLM (Gemini) so the model
can only ever construct calls into this exact, fixed list of functions — it cannot invent
a tool name or an argument that isn't declared here. The deterministic keyword-based
planner (app.ai.providers.plan, used for Ollama/Mock) calls the same handlers directly.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.ai import analysis, overview
from app.audit.models import SupportCase
from app.billing import service as billing_service
from app.billing.schemas import InvoiceGenerateRequest, InvoiceRead
from app.core.tenancy import TenantContext
from app.customers import service as customers_service
from app.customers.schemas import CustomerRead
from app.products import service as products_service
from app.products.schemas import PricePlanRead
from app.subscriptions import service as subscriptions_service
from app.subscriptions.schemas import SubscriptionRead
from app.usage import service as usage_service

ToolHandler = Callable[[Session, TenantContext, dict], dict]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    tier: str  # "A" | "B" | "C"
    handler: ToolHandler
    description: str
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})


# ---------------------------------------------------------------------------
# Read-only lookups (Tier A)
# ---------------------------------------------------------------------------


def _get_customer(db: Session, ctx: TenantContext, params: dict) -> dict:
    customer = customers_service.get_customer(db, ctx.tenant_id, ctx.workspace_type, params["customer_id"])
    return CustomerRead.model_validate(customer).model_dump(mode="json")


def _find_customers(db: Session, ctx: TenantContext, params: dict) -> dict:
    """Lets the agent resolve a name mentioned in free text (e.g. "gadi") to a real
    customer id, instead of guessing or inventing one."""
    name_contains = params.get("name_contains", "").lower()
    customers = customers_service.list_customers(db, ctx.tenant_id, ctx.workspace_type)
    matches = [c for c in customers if name_contains in c.name.lower()]
    return {"customers": [CustomerRead.model_validate(c).model_dump(mode="json") for c in matches]}


def _get_subscription(db: Session, ctx: TenantContext, params: dict) -> dict:
    subscription = subscriptions_service.get_subscription(
        db, ctx.tenant_id, ctx.workspace_type, params["subscription_id"]
    )
    return SubscriptionRead.model_validate(subscription).model_dump(mode="json")


def _list_customer_subscriptions(db: Session, ctx: TenantContext, params: dict) -> dict:
    subs = subscriptions_service.list_subscriptions(db, ctx.tenant_id, ctx.workspace_type)
    matching = [s for s in subs if s.customer_id == params["customer_id"]]
    return {"subscriptions": [SubscriptionRead.model_validate(s).model_dump(mode="json") for s in matching]}


def _get_invoice(db: Session, ctx: TenantContext, params: dict) -> dict:
    invoice = billing_service.get_invoice(db, ctx.tenant_id, ctx.workspace_type, params["invoice_id"])
    return InvoiceRead.model_validate(invoice).model_dump(mode="json")


def _list_customer_invoices(db: Session, ctx: TenantContext, params: dict) -> dict:
    invoices = billing_service.list_invoices(db, ctx.tenant_id, ctx.workspace_type)
    matching = [i for i in invoices if i.customer_id == params["customer_id"]]
    return {"invoices": [InvoiceRead.model_validate(i).model_dump(mode="json") for i in matching]}


def _get_usage_summary(db: Session, ctx: TenantContext, params: dict) -> dict:
    items = usage_service.get_usage_summary(
        db,
        ctx.tenant_id,
        ctx.workspace_type,
        params["subscription_id"],
        date.fromisoformat(params["period_start"]),
        date.fromisoformat(params["period_end"]),
    )
    return {"items": [i.model_dump(mode="json") for i in items]}


def _compare_invoices(db: Session, ctx: TenantContext, params: dict) -> dict:
    return billing_service.compare_invoices(
        db, ctx.tenant_id, ctx.workspace_type, params["invoice_id_a"], params["invoice_id_b"]
    )


def _list_price_plans(db: Session, ctx: TenantContext, params: dict) -> dict:
    plans = products_service.list_price_plans(db, ctx.tenant_id, ctx.workspace_type)
    return {"price_plans": [PricePlanRead.model_validate(p).model_dump(mode="json") for p in plans]}


def _get_current_period(db: Session, ctx: TenantContext, params: dict) -> dict:
    """So the agent never has to guess or compute "this month" itself."""
    today = datetime.now(timezone.utc).date()
    start = today.replace(day=1)
    end = date(start.year + 1, 1, 1) - timedelta(days=1) if start.month == 12 else date(start.year, start.month + 1, 1) - timedelta(days=1)
    return {"today": today.isoformat(), "period_start": start.isoformat(), "period_end": end.isoformat()}


# ---------------------------------------------------------------------------
# Low-risk writes (Tier B) — execute automatically, always audit-logged
# ---------------------------------------------------------------------------


def _create_support_case(db: Session, ctx: TenantContext, params: dict) -> dict:
    case = SupportCase(
        tenant_id=ctx.tenant_id,
        workspace_type=ctx.workspace_type,
        customer_id=params["customer_id"],
        subject=params["subject"],
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return {"id": case.id, "customer_id": case.customer_id, "subject": case.subject, "status": case.status}


def _update_customer_contact_details(db: Session, ctx: TenantContext, params: dict) -> dict:
    customer = customers_service.get_customer(db, ctx.tenant_id, ctx.workspace_type, params["customer_id"])
    if params.get("email"):
        customer.email = params["email"]
    if params.get("country"):
        customer.country = params["country"]
    db.commit()
    db.refresh(customer)
    return CustomerRead.model_validate(customer).model_dump(mode="json")


def _generate_invoice(db: Session, ctx: TenantContext, params: dict) -> dict:
    request = InvoiceGenerateRequest(
        subscription_id=params["subscription_id"],
        period_start=date.fromisoformat(params["period_start"]),
        period_end=date.fromisoformat(params["period_end"]),
    )
    invoice = billing_service.generate_invoice(db, ctx.tenant_id, ctx.workspace_type, request)
    return InvoiceRead.model_validate(invoice).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Protected changes (Tier C) — gateway always routes these to human approval
# ---------------------------------------------------------------------------


def _pause_subscription(db: Session, ctx: TenantContext, params: dict) -> dict:
    subscription = subscriptions_service.pause_subscription(db, ctx.tenant_id, ctx.workspace_type, params["subscription_id"])
    return SubscriptionRead.model_validate(subscription).model_dump(mode="json")


def _reactivate_subscription(db: Session, ctx: TenantContext, params: dict) -> dict:
    subscription = subscriptions_service.reactivate_subscription(
        db, ctx.tenant_id, ctx.workspace_type, params["subscription_id"]
    )
    return SubscriptionRead.model_validate(subscription).model_dump(mode="json")


def _change_subscription_plan(db: Session, ctx: TenantContext, params: dict) -> dict:
    subscription = subscriptions_service.change_subscription_plan(
        db, ctx.tenant_id, ctx.workspace_type, params["subscription_id"], params["new_price_plan_id"]
    )
    return SubscriptionRead.model_validate(subscription).model_dump(mode="json")


TOOL_REGISTRY: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in [
        # Tier A — read-only, automatic
        ToolSpec(
            "get_customer", "A", _get_customer, "Look up a customer by its exact id.",
            {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]},
        ),
        ToolSpec(
            "find_customers", "A", _find_customers,
            "Search customers by a name fragment (case-insensitive). Use this to resolve a "
            "customer mentioned by name in the user's message into their real customer_id "
            "before calling any other tool that needs one — never invent a customer_id.",
            {"type": "object", "properties": {"name_contains": {"type": "string"}}, "required": ["name_contains"]},
        ),
        ToolSpec(
            "get_subscription", "A", _get_subscription, "Look up a subscription by its exact id.",
            {"type": "object", "properties": {"subscription_id": {"type": "string"}}, "required": ["subscription_id"]},
        ),
        ToolSpec(
            "list_customer_subscriptions", "A", _list_customer_subscriptions,
            "List a customer's subscriptions (with their ids and status). Use this to find "
            "the subscription_id needed by other tools once you have a customer_id.",
            {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]},
        ),
        ToolSpec(
            "get_invoice", "A", _get_invoice, "Look up an invoice by its exact id.",
            {"type": "object", "properties": {"invoice_id": {"type": "string"}}, "required": ["invoice_id"]},
        ),
        ToolSpec(
            "list_customer_invoices", "A", _list_customer_invoices,
            "List a customer's invoices (with their ids, period, status, amount). Use this "
            "to find an invoice_id once you have a customer_id.",
            {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]},
        ),
        ToolSpec(
            "get_usage_summary", "A", _get_usage_summary, "Usage totals for a subscription in a date range.",
            {
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "period_start": {"type": "string", "description": "YYYY-MM-DD"},
                    "period_end": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["subscription_id", "period_start", "period_end"],
            },
        ),
        ToolSpec(
            "compare_invoices", "A", _compare_invoices, "Line-item diff between two invoices.",
            {
                "type": "object",
                "properties": {"invoice_id_a": {"type": "string"}, "invoice_id_b": {"type": "string"}},
                "required": ["invoice_id_a", "invoice_id_b"],
            },
        ),
        ToolSpec(
            "list_price_plans", "A", _list_price_plans,
            "List all active price plans (with their ids and names). Use this to resolve a "
            "plan mentioned by name (e.g. \"professional\") into the price_plan_id needed by "
            "change_subscription_plan.",
            {"type": "object", "properties": {}},
        ),
        ToolSpec(
            "analyze_data", "A", analysis.analyze_data,
            "Run a read-only aggregation over the workspace's data to answer analytical "
            "questions (rankings, totals, averages, breakdowns, counts). Compose the request "
            "from the user's question; you never write SQL. "
            "datasets and their options: "
            "customers (group_by: country|status); "
            "subscriptions (group_by: plan|status|customer|country; field: quantity_users); "
            "invoices (group_by: customer|status|plan|month|country; field: subtotal_cents); "
            "payments (group_by: customer|status|month|country; field: amount_cents); "
            "usage (group_by: event_type|customer|plan|month|country; field: total_quantity). "
            "metric: count (default, no field needed) | sum | avg | max | min (need a field). "
            "filters: optional exact-match object using the same names as group_by, e.g. "
            "{\"status\": \"failed\"} or {\"month\": \"2026-09\"}. Exact status values: invoices "
            "draft|finalized|paid|void (\"finalized\" = issued but UNPAID/outstanding); payments "
            "pending|succeeded|failed; subscriptions active|trialing|paused|canceled. If a result "
            "carries a 'warning' or 'available_values', your filter was wrong — correct it and retry "
            "rather than telling the user there is no data. Revenue means invoices "
            "subtotal_cents (optionally filtered to status paid); failed payments means "
            "payments filtered to status failed. order: desc (default) or asc; top_n up to 50. "
            "Money values come back in cents plus value_dollars.",
            {
                "type": "object",
                "properties": {
                    "dataset": {"type": "string"},
                    "group_by": {"type": "string"},
                    "metric": {"type": "string"},
                    "field": {"type": "string"},
                    "filters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                            "month": {"type": "string", "description": "YYYY-MM"},
                            "country": {"type": "string"},
                            "plan": {"type": "string"},
                            "customer": {"type": "string"},
                            "event_type": {"type": "string"},
                        },
                    },
                    "order": {"type": "string"},
                    "top_n": {"type": "integer"},
                },
                "required": ["dataset"],
            },
        ),
        ToolSpec(
            "business_overview", "A", overview.business_overview,
            "Whole-workspace snapshot: customer/subscription/invoice/payment counts and dollar "
            "totals (billed, paid, outstanding), and usage totals. Use for general questions such "
            "as \"how is the business doing\" or \"give me a summary\", and to cross-check totals.",
            {"type": "object", "properties": {}},
        ),
        ToolSpec(
            "customer_overview", "A", overview.customer_overview,
            "Full profile of ONE customer by name fragment or id: plan(s), invoices and payments "
            "by status with dollar totals, recent invoices, and usage totals. Use this for any "
            "question about a specific named customer (what they owe, pay, use, subscribe to).",
            {
                "type": "object",
                "properties": {"name_contains": {"type": "string"}, "customer_id": {"type": "string"}},
            },
        ),
        ToolSpec(
            "get_current_period", "A", _get_current_period,
            "Get today's date and the current calendar month's start/end dates. Use this "
            "instead of guessing dates whenever the user says things like \"this month\".",
            {"type": "object", "properties": {}},
        ),
        # Tier B — low-risk write, automatic + audited
        ToolSpec(
            "create_support_case", "B", _create_support_case, "Open a support case for a customer.",
            {
                "type": "object",
                "properties": {"customer_id": {"type": "string"}, "subject": {"type": "string"}},
                "required": ["customer_id", "subject"],
            },
        ),
        ToolSpec(
            "update_customer_contact_details", "B", _update_customer_contact_details,
            "Update a customer's email and/or country.",
            {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "email": {"type": "string"},
                    "country": {"type": "string"},
                },
                "required": ["customer_id"],
            },
        ),
        ToolSpec(
            "generate_invoice", "B", _generate_invoice,
            "Generate an invoice for a subscription's billing period, from its recorded usage. "
            "If the user doesn't specify a period, call get_current_period first and use that.",
            {
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "period_start": {"type": "string", "description": "YYYY-MM-DD"},
                    "period_end": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["subscription_id", "period_start", "period_end"],
            },
        ),
        # Tier C — protected, requires human approval. Calling these NEVER applies the
        # change immediately — the gateway always converts the call into a pending
        # approval, regardless of what the model intended.
        ToolSpec(
            "pause_subscription", "C", _pause_subscription, "Pause a customer's subscription.",
            {"type": "object", "properties": {"subscription_id": {"type": "string"}}, "required": ["subscription_id"]},
        ),
        ToolSpec(
            "reactivate_subscription", "C", _reactivate_subscription, "Reactivate a paused subscription.",
            {"type": "object", "properties": {"subscription_id": {"type": "string"}}, "required": ["subscription_id"]},
        ),
        ToolSpec(
            "change_subscription_plan", "C", _change_subscription_plan, "Move a subscription to a new price plan.",
            {
                "type": "object",
                "properties": {"subscription_id": {"type": "string"}, "new_price_plan_id": {"type": "string"}},
                "required": ["subscription_id", "new_price_plan_id"],
            },
        ),
    ]
}
