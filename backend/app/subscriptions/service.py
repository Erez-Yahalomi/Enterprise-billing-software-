from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import WorkspaceType
from app.products import service as products_service
from app.subscriptions.models import Entitlement, Subscription
from app.subscriptions.schemas import SubscriptionCreate


def create_subscription(
    db: Session, tenant_id: str, workspace_type: WorkspaceType, data: SubscriptionCreate
) -> Subscription:
    plan = products_service.get_price_plan(db, tenant_id, workspace_type, data.price_plan_id)

    subscription = Subscription(
        tenant_id=tenant_id,
        workspace_type=workspace_type,
        customer_id=data.customer_id,
        price_plan_id=plan.id,
        quantity_users=data.quantity_users,
        started_at=data.started_at or datetime.now(timezone.utc),
    )
    db.add(subscription)
    db.flush()

    entitlement = Entitlement(
        tenant_id=tenant_id,
        workspace_type=workspace_type,
        subscription_id=subscription.id,
        included_users=plan.included_users,
        included_api_calls=plan.included_api_calls,
    )
    db.add(entitlement)
    db.commit()
    db.refresh(subscription)
    return subscription


def get_subscription(db: Session, tenant_id: str, workspace_type: WorkspaceType, subscription_id: str) -> Subscription:
    stmt = select(Subscription).where(
        Subscription.id == subscription_id,
        Subscription.tenant_id == tenant_id,
        Subscription.workspace_type == workspace_type,
    )
    subscription = db.execute(stmt).scalar_one_or_none()
    if subscription is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription


def list_subscriptions(db: Session, tenant_id: str, workspace_type: WorkspaceType) -> list[Subscription]:
    stmt = select(Subscription).where(Subscription.tenant_id == tenant_id, Subscription.workspace_type == workspace_type)
    return list(db.execute(stmt).scalars().all())


def cancel_subscription(db: Session, tenant_id: str, workspace_type: WorkspaceType, subscription_id: str) -> Subscription:
    subscription = get_subscription(db, tenant_id, workspace_type, subscription_id)
    subscription.status = "canceled"
    subscription.canceled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(subscription)
    return subscription


def pause_subscription(db: Session, tenant_id: str, workspace_type: WorkspaceType, subscription_id: str) -> Subscription:
    """Protected operation — only ever called by the AI gateway after human approval."""
    subscription = get_subscription(db, tenant_id, workspace_type, subscription_id)
    subscription.status = "paused"
    db.commit()
    db.refresh(subscription)
    return subscription


def reactivate_subscription(
    db: Session, tenant_id: str, workspace_type: WorkspaceType, subscription_id: str
) -> Subscription:
    subscription = get_subscription(db, tenant_id, workspace_type, subscription_id)
    subscription.status = "active"
    db.commit()
    db.refresh(subscription)
    return subscription


def change_subscription_plan(
    db: Session, tenant_id: str, workspace_type: WorkspaceType, subscription_id: str, new_price_plan_id: str
) -> Subscription:
    """Protected operation — only ever called by the AI gateway after human approval."""
    subscription = get_subscription(db, tenant_id, workspace_type, subscription_id)
    plan = products_service.get_price_plan(db, tenant_id, workspace_type, new_price_plan_id)
    subscription.price_plan_id = plan.id
    db.commit()
    db.refresh(subscription)
    return subscription
