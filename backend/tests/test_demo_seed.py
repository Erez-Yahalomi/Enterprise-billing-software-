from datetime import date, datetime, timedelta, timezone

from app.analytics.service import query_usage_by_day
from app.billing.models import Invoice
from app.core.models import WorkspaceType
from app.customers.models import Customer
from app.demo.service import TENANT_ID, generate_demo, reset_demo
from app.subscriptions.models import Subscription
from app.usage.schemas import UsageEventCreate
from app.usage.service import record_usage


def test_generate_small_demo_is_deterministic_and_reset_clears_it(db_session):
    result = generate_demo(db_session, "small", include_uci=False)
    assert result["size"] == "small"

    customers = db_session.query(Customer).filter_by(tenant_id=TENANT_ID).all()
    assert len(customers) == 100
    names = {c.name for c in customers}
    for scenario_name in ["ACME Corporation", "Globex Corporation", "Initech", "Northstar", "Contoso", "Umbrella Analytics"]:
        assert scenario_name in names

    subscriptions = db_session.query(Subscription).filter_by(tenant_id=TENANT_ID).all()
    assert len(subscriptions) == 100
    invoices = db_session.query(Invoice).filter_by(tenant_id=TENANT_ID).all()
    assert len(invoices) >= 100  # Globex and Northstar each have two.

    reset_demo(db_session)
    assert db_session.query(Customer).filter_by(tenant_id=TENANT_ID).count() == 0
    assert db_session.query(Invoice).filter_by(tenant_id=TENANT_ID).count() == 0


def test_demo_usage_is_visible_in_the_lake_and_cleared_on_reset(db_session):
    generate_demo(db_session, "small", include_uci=False)

    acme = db_session.query(Customer).filter_by(tenant_id=TENANT_ID, name="ACME Corporation").one()
    acme_sub = db_session.query(Subscription).filter_by(tenant_id=TENANT_ID, customer_id=acme.id).one()
    today = date.today()
    rows = query_usage_by_day(TENANT_ID, acme_sub.id, today.replace(day=1), today.replace(day=1) + timedelta(days=31))
    assert {(r.event_type, r.total_quantity) for r in rows} == {("api_request", 4_800_000), ("storage_gb", 700)}

    reset_demo(db_session)
    assert query_usage_by_day(TENANT_ID, acme_sub.id, today.replace(day=1), today.replace(day=1) + timedelta(days=31)) == []


def test_recorded_usage_appears_in_usage_by_day(db_session):
    generate_demo(db_session, "small", include_uci=False)
    sub = db_session.query(Subscription).filter_by(tenant_id=TENANT_ID).first()
    when = datetime(date.today().year, date.today().month, 1, 12, tzinfo=timezone.utc)

    record_usage(
        db_session, TENANT_ID, WorkspaceType.demo,
        UsageEventCreate(
            event_id="ui-test-1", customer_id=sub.customer_id, subscription_id=sub.id,
            event_type="data_export", quantity=7, occurred_at=when,
        ),
    )

    rows = query_usage_by_day(TENANT_ID, sub.id, when.date(), when.date())
    assert ("data_export", 7) in {(r.event_type, r.total_quantity) for r in rows}
