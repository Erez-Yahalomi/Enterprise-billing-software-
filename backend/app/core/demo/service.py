"""Deterministic demo data generator (spec sections 12-14).

Uses a fixed random seed so the same size tier always produces the same data — this
makes AI demo Q&A and automated tests repeatable. Always targets the fixed DEMO tenant;
it never touches a real user's "My Workspace" data (spec section 15-16).
"""

import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ai.models import ApprovalRequest
from app.audit.models import AuditLog, SupportCase
from app.billing.models import Invoice, InvoiceLineItem
from app.billing.schemas import InvoiceGenerateRequest
from app.billing import service as billing_service
from app.core.config import get_settings
from app.core.models import WorkspaceType
from app.customers.models import Customer
from app.customers.schemas import CustomerCreate
from app.customers import service as customers_service
from app.ledger.models import LedgerEntry
from app.payments.models import Payment
from app.payments.schemas import PaymentCreate
from app.payments import service as payments_service
from app.products.models import PricePlan, Product
from app.products.schemas import PricePlanCreate, ProductCreate
from app.products import service as products_service
from app.subscriptions.models import Entitlement, Subscription
from app.subscriptions.schemas import SubscriptionCreate
from app.subscriptions import service as subscriptions_service
from app.usage.aggregation import apply_usage_to_aggregate
from app.usage.lake import delete_lake_files, write_usage_events_batch
from app.usage.models import UsageAggregate, UsageEvent

TENANT_ID = "DEMO"
LAKE_FILE_PREFIX = "demo-"
WORKSPACE = WorkspaceType.demo

SIZE_TIERS = {
    "small": {"customers": 100, "usage_events": 10_000},
    "medium": {"customers": 1_000, "usage_events": 100_000},
    "large": {"customers": 10_000, "usage_events": 1_000_000},
}

PLAN_DEFS = [
    dict(
        name="starter", monthly_price_cents=4900, included_users=10, additional_user_price_cents=500,
        included_api_calls=100_000, overage_api_price_cents_per_unit=2, ai_token_price_cents_per_1k=100,
        storage_gb_price_cents=50,
    ),
    dict(
        name="professional", monthly_price_cents=29900, included_users=50, additional_user_price_cents=300,
        included_api_calls=1_000_000, overage_api_price_cents_per_unit=1, ai_token_price_cents_per_1k=50,
        storage_gb_price_cents=30,
    ),
    dict(
        name="enterprise", monthly_price_cents=250_000, included_users=200, additional_user_price_cents=200,
        included_api_calls=10_000_000, overage_api_price_cents_per_unit=1, ai_token_price_cents_per_1k=20,
        storage_gb_price_cents=15,
    ),
]


def _month_bounds(base: date, months_back: int) -> tuple[date, date]:
    year, month = base.year, base.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    start = date(year, month, 1)
    end = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return start, end


def reset_demo(db: Session) -> None:
    for model in (
        InvoiceLineItem, Invoice, Payment, LedgerEntry, UsageEvent, UsageAggregate,
        Entitlement, Subscription, SupportCase, AuditLog, ApprovalRequest,
        Customer, PricePlan, Product,
    ):
        db.execute(delete(model).where(model.tenant_id == TENANT_ID))
    db.commit()
    delete_lake_files(LAKE_FILE_PREFIX)


def _export_usage_to_lake(db: Session) -> None:
    """Mirrors the seeded UsageEvents into the Parquet lake (what the Usage page reads).

    One file per (subscription, day) rather than per event, so the large tier stays fast.
    """
    stmt = (
        select(UsageEvent)
        .where(UsageEvent.tenant_id == TENANT_ID)
        .order_by(UsageEvent.subscription_id, func.date(UsageEvent.occurred_at))
        .execution_options(yield_per=5000)
    )
    group_key: tuple | None = None
    batch: list[dict] = []

    def flush() -> None:
        if batch:
            write_usage_events_batch(
                file_key=f"{LAKE_FILE_PREFIX}{group_key[0]}-{group_key[1].isoformat()}", events=batch
            )
            batch.clear()

    for event in db.execute(stmt).scalars():
        occurred_at = event.occurred_at if event.occurred_at.tzinfo else event.occurred_at.replace(tzinfo=timezone.utc)
        key = (event.subscription_id, occurred_at.date())
        if key != group_key:
            flush()
            group_key = key
        batch.append(
            dict(
                tenant_id=TENANT_ID, workspace_type=WORKSPACE.value, event_id=event.event_id,
                customer_id=event.customer_id, subscription_id=event.subscription_id,
                event_type=event.event_type, quantity=event.quantity, occurred_at=occurred_at,
            )
        )
    flush()


def _create_customer_with_subscription(db, name, email, country, plan, quantity_users, started_at):
    customer = customers_service.create_customer(
        db, TENANT_ID, WORKSPACE, CustomerCreate(name=name, email=email, country=country)
    )
    subscription = subscriptions_service.create_subscription(
        db, TENANT_ID, WORKSPACE,
        SubscriptionCreate(customer_id=customer.id, price_plan_id=plan.id, quantity_users=quantity_users, started_at=started_at),
    )
    return customer, subscription


def _record_usage(db, subscription_id, customer_id, event_type, quantity, occurred_on: date, seq: int) -> None:
    db.add(
        UsageEvent(
            tenant_id=TENANT_ID, workspace_type=WORKSPACE,
            event_id=f"demo-{subscription_id}-{event_type}-{seq}",
            customer_id=customer_id, subscription_id=subscription_id,
            event_type=event_type, quantity=quantity,
            occurred_at=datetime.combine(occurred_on, datetime.min.time(), tzinfo=timezone.utc),
        )
    )


def _finalize(db, subscription_id, event_types, period_date) -> None:
    db.flush()
    for event_type in event_types:
        apply_usage_to_aggregate(db, TENANT_ID, WORKSPACE, subscription_id, event_type, period_date)


def _invoice(db, subscription_id, period_start, period_end):
    return billing_service.generate_invoice(
        db, TENANT_ID, WORKSPACE, InvoiceGenerateRequest(subscription_id=subscription_id, period_start=period_start, period_end=period_end)
    )


def _pay(db, invoice, amount_cents=None, tag="pay") -> None:
    payments_service.record_payment(
        db, TENANT_ID, WORKSPACE,
        PaymentCreate(
            payment_intent_id=f"demo-{tag}-{invoice.id}",
            invoice_id=invoice.id,
            amount_cents=invoice.subtotal_cents if amount_cents is None else amount_cents,
        ),
    )


def _seed_named_scenarios(db: Session, plans: dict[str, PricePlan], prev_start, prev_end, cur_start, cur_end) -> None:
    starter, professional, enterprise = plans["starter"], plans["professional"], plans["enterprise"]
    month_start = lambda d: datetime(d.year, d.month, 1, tzinfo=timezone.utc)  # noqa: E731

    # ACME — normal enterprise account, comfortably within allowance, paid on time.
    acme, acme_sub = _create_customer_with_subscription(db, "ACME Corporation", "billing@acme.example", "US", enterprise, 80, month_start(cur_start))
    _record_usage(db, acme_sub.id, acme.id, "api_request", 4_800_000, cur_start + timedelta(days=10), 1)
    _record_usage(db, acme_sub.id, acme.id, "storage_gb", 700, cur_start + timedelta(days=10), 2)
    _finalize(db, acme_sub.id, ["api_request", "storage_gb"], cur_start + timedelta(days=10))
    _pay(db, _invoice(db, acme_sub.id, cur_start, cur_end))

    # Globex — large usage increase this month vs. last.
    globex, globex_sub = _create_customer_with_subscription(db, "Globex Corporation", "ap@globex.example", "US", professional, 40, month_start(prev_start))
    _record_usage(db, globex_sub.id, globex.id, "api_request", 500_000, prev_start + timedelta(days=10), 1)
    _finalize(db, globex_sub.id, ["api_request"], prev_start + timedelta(days=10))
    _pay(db, _invoice(db, globex_sub.id, prev_start, prev_end))
    _record_usage(db, globex_sub.id, globex.id, "api_request", 1_900_000, cur_start + timedelta(days=10), 2)
    _finalize(db, globex_sub.id, ["api_request"], cur_start + timedelta(days=10))
    _pay(db, _invoice(db, globex_sub.id, cur_start, cur_end))

    # Initech — failed payment.
    initech, initech_sub = _create_customer_with_subscription(db, "Initech", "ap@initech.example", "US", enterprise, 120, month_start(cur_start))
    _record_usage(db, initech_sub.id, initech.id, "api_request", 3_000_000, cur_start + timedelta(days=5), 1)
    _finalize(db, initech_sub.id, ["api_request"], cur_start + timedelta(days=5))
    initech_invoice = _invoice(db, initech_sub.id, cur_start, cur_end)
    _pay(db, initech_invoice, amount_cents=0, tag="pay-fail")

    # Northstar — recently upgraded Professional -> Enterprise.
    northstar, northstar_sub = _create_customer_with_subscription(db, "Northstar", "finance@northstar.example", "CA", professional, 45, month_start(prev_start))
    _record_usage(db, northstar_sub.id, northstar.id, "api_request", 400_000, prev_start + timedelta(days=10), 1)
    _finalize(db, northstar_sub.id, ["api_request"], prev_start + timedelta(days=10))
    _pay(db, _invoice(db, northstar_sub.id, prev_start, prev_end))
    subscriptions_service.change_subscription_plan(db, TENANT_ID, WORKSPACE, northstar_sub.id, enterprise.id)
    _record_usage(db, northstar_sub.id, northstar.id, "api_request", 900_000, cur_start + timedelta(days=10), 2)
    _finalize(db, northstar_sub.id, ["api_request"], cur_start + timedelta(days=10))
    _pay(db, _invoice(db, northstar_sub.id, cur_start, cur_end))

    # Contoso — exceeded its Starter API allowance.
    contoso, contoso_sub = _create_customer_with_subscription(db, "Contoso", "ap@contoso.example", "US", starter, 8, month_start(cur_start))
    _record_usage(db, contoso_sub.id, contoso.id, "api_request", 260_000, cur_start + timedelta(days=10), 1)
    _finalize(db, contoso_sub.id, ["api_request"], cur_start + timedelta(days=10))
    _pay(db, _invoice(db, contoso_sub.id, cur_start, cur_end))

    # Umbrella Analytics — heavy AI-token usage.
    umbrella, umbrella_sub = _create_customer_with_subscription(db, "Umbrella Analytics", "ap@umbrella.example", "US", professional, 30, month_start(cur_start))
    _record_usage(db, umbrella_sub.id, umbrella.id, "ai_tokens", 9_500_000, cur_start + timedelta(days=10), 1)
    _record_usage(db, umbrella_sub.id, umbrella.id, "api_request", 300_000, cur_start + timedelta(days=10), 2)
    _finalize(db, umbrella_sub.id, ["ai_tokens", "api_request"], cur_start + timedelta(days=10))
    _pay(db, _invoice(db, umbrella_sub.id, cur_start, cur_end))


def _seed_random_customers(db: Session, rnd: random.Random, plans: dict[str, PricePlan], count: int, target_events: int, cur_start, cur_end) -> None:
    if count <= 0:
        return
    plan_list = list(plans.values())
    events_per_customer = max(1, target_events // count)
    countries = ["US", "GB", "DE", "FR", "CA", "AU", "IN", "BR"]
    span_days = max(0, (cur_end - cur_start).days)

    for i in range(count):
        plan = rnd.choice(plan_list)
        customer = customers_service.create_customer(
            db, TENANT_ID, WORKSPACE,
            CustomerCreate(name=f"Demo Company {i + 1:05d}", email=f"ap+{i + 1}@democo{i + 1}.example", country=rnd.choice(countries)),
        )
        quantity_users = max(1, plan.included_users + rnd.randint(-3, 10))
        subscription = subscriptions_service.create_subscription(
            db, TENANT_ID, WORKSPACE,
            SubscriptionCreate(
                customer_id=customer.id, price_plan_id=plan.id, quantity_users=quantity_users,
                started_at=datetime(cur_start.year, cur_start.month, 1, tzinfo=timezone.utc),
            ),
        )

        occurred_day = cur_start + timedelta(days=rnd.randint(0, span_days))
        for e in range(events_per_customer):
            db.add(
                UsageEvent(
                    tenant_id=TENANT_ID, workspace_type=WORKSPACE,
                    event_id=f"demo-{subscription.id}-api-{e}",
                    customer_id=customer.id, subscription_id=subscription.id,
                    event_type="api_request", quantity=rnd.randint(50, 5000),
                    occurred_at=datetime.combine(occurred_day, datetime.min.time(), tzinfo=timezone.utc),
                )
            )
        _finalize(db, subscription.id, ["api_request"], occurred_day)

        invoice = _invoice(db, subscription.id, cur_start, cur_end)
        roll = rnd.random()
        if roll < 0.85:
            _pay(db, invoice)
        elif roll < 0.93:
            _pay(db, invoice, amount_cents=0, tag="pay-fail")
        # else: left open/unpaid, so "open invoices" analytics has something to show.

        if (i + 1) % 200 == 0:
            db.commit()
    db.commit()


def generate_demo(db: Session, size: str, include_uci: bool) -> dict:
    settings = get_settings()
    rnd = random.Random(settings.demo_random_seed)

    reset_demo(db)

    product = products_service.create_product(db, TENANT_ID, WORKSPACE, ProductCreate(name="Billing Platform", code="core"))
    plans = {
        pd["name"]: products_service.create_price_plan(db, TENANT_ID, WORKSPACE, PricePlanCreate(product_id=product.id, **pd))
        for pd in PLAN_DEFS
    }

    today = datetime.now(timezone.utc).date()
    cur_start, cur_end = _month_bounds(today, 0)
    prev_start, prev_end = _month_bounds(today, 1)

    _seed_named_scenarios(db, plans, prev_start, prev_end, cur_start, cur_end)

    tier = SIZE_TIERS[size]
    _seed_random_customers(db, rnd, plans, max(0, tier["customers"] - 6), tier["usage_events"], cur_start, cur_end)

    _export_usage_to_lake(db)

    if include_uci:
        from app.demo.uci_import import import_uci_sample

        import_uci_sample(db)

    return {"size": size, "customers": tier["customers"], "usage_events_target": tier["usage_events"], "include_uci": include_uci}
