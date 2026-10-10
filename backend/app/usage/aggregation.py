"""Usage aggregation shared by the synchronous fallback path and the Kafka worker.

Kept as a single implementation (no duplicated business logic) so both code paths compute
identical numbers. The aggregate is recomputed from raw UsageEvent rows rather than
incremented, so it stays correct even if Kafka redelivers the same message (at-least-once
delivery semantics) — recompute is idempotent, increment is not.
"""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.models import WorkspaceType
from app.usage.models import UsageAggregate, UsageEvent


def apply_usage_to_aggregate(
    db: Session,
    tenant_id: str,
    workspace_type: WorkspaceType,
    subscription_id: str,
    event_type: str,
    period_date: date,
) -> None:
    period_start = datetime.combine(period_date, time.min, tzinfo=timezone.utc)
    period_end = period_start + timedelta(days=1)

    total = db.execute(
        select(func.sum(UsageEvent.quantity)).where(
            UsageEvent.subscription_id == subscription_id,
            UsageEvent.event_type == event_type,
            UsageEvent.occurred_at >= period_start,
            UsageEvent.occurred_at < period_end,
        )
    ).scalar() or 0

    stmt = select(UsageAggregate).where(
        UsageAggregate.subscription_id == subscription_id,
        UsageAggregate.event_type == event_type,
        UsageAggregate.period_date == period_date,
    )
    aggregate = db.execute(stmt).scalar_one_or_none()
    if aggregate is None:
        aggregate = UsageAggregate(
            tenant_id=tenant_id,
            workspace_type=workspace_type,
            subscription_id=subscription_id,
            event_type=event_type,
            period_date=period_date,
            total_quantity=total,
        )
        db.add(aggregate)
    else:
        aggregate.total_quantity = total

    db.commit()
