from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.models import WorkspaceType
from app.usage.models import UsageAggregate, UsageEvent
from app.usage.publisher import UsageEventRecord, get_usage_publisher
from app.usage.schemas import UsageEventCreate, UsageSummaryItem


def record_usage(db: Session, tenant_id: str, workspace_type: WorkspaceType, data: UsageEventCreate) -> UsageEvent:
    """Idempotent on event_id: republishing the same event_id is a no-op, not a double count.

    The raw event is written to Postgres synchronously (transactional outbox: durable +
    immediately queryable), then published for aggregation — either in-process (sync
    pipeline) or via Kafka to the worker (kafka pipeline). See app.usage.publisher.
    """
    existing = db.execute(select(UsageEvent).where(UsageEvent.event_id == data.event_id)).scalar_one_or_none()
    if existing is not None:
        return existing

    event = UsageEvent(
        tenant_id=tenant_id,
        workspace_type=workspace_type,
        event_id=data.event_id,
        customer_id=data.customer_id,
        subscription_id=data.subscription_id,
        event_type=data.event_type,
        quantity=data.quantity,
        occurred_at=data.occurred_at,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    get_usage_publisher().publish(
        db,
        tenant_id,
        workspace_type,
        UsageEventRecord(
            event_id=data.event_id,
            customer_id=data.customer_id,
            subscription_id=data.subscription_id,
            event_type=data.event_type,
            quantity=data.quantity,
            occurred_at=data.occurred_at,
        ),
    )

    return event


def get_usage_summary(
    db: Session,
    tenant_id: str,
    workspace_type: WorkspaceType,
    subscription_id: str,
    period_start: date,
    period_end: date,
) -> list[UsageSummaryItem]:
    stmt = (
        select(UsageAggregate.event_type, func.sum(UsageAggregate.total_quantity))
        .where(
            UsageAggregate.tenant_id == tenant_id,
            UsageAggregate.workspace_type == workspace_type,
            UsageAggregate.subscription_id == subscription_id,
            UsageAggregate.period_date >= period_start,
            UsageAggregate.period_date <= period_end,
        )
        .group_by(UsageAggregate.event_type)
    )
    rows = db.execute(stmt).all()
    return [UsageSummaryItem(event_type=event_type, total_quantity=total or 0) for event_type, total in rows]
