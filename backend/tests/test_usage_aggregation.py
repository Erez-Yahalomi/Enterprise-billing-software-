from datetime import date, datetime, timezone

from app.core.models import WorkspaceType
from app.usage.aggregation import apply_usage_to_aggregate
from app.usage.models import UsageAggregate, UsageEvent


def _add_event(db, quantity: int) -> None:
    db.add(
        UsageEvent(
            tenant_id="DEMO",
            workspace_type=WorkspaceType.demo,
            event_id=f"evt-{quantity}-{db.query(UsageEvent).count()}",
            customer_id="cus_1",
            subscription_id="sub_1",
            event_type="api_request",
            quantity=quantity,
            occurred_at=datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc),
        )
    )
    db.commit()


def test_aggregate_is_idempotent_under_redelivery(db_session):
    _add_event(db_session, 100)
    _add_event(db_session, 50)

    period = date(2026, 9, 15)
    apply_usage_to_aggregate(db_session, "DEMO", WorkspaceType.demo, "sub_1", "api_request", period)
    # Simulate Kafka redelivering the same message a second time.
    apply_usage_to_aggregate(db_session, "DEMO", WorkspaceType.demo, "sub_1", "api_request", period)

    aggregate = db_session.query(UsageAggregate).filter_by(subscription_id="sub_1", event_type="api_request").one()
    assert aggregate.total_quantity == 150
