from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.tenancy import TenantContext, get_tenant_context
from app.subscriptions import service
from app.subscriptions.schemas import SubscriptionCreate, SubscriptionRead

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.post("", response_model=SubscriptionRead, status_code=201)
def create_subscription(
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> SubscriptionRead:
    subscription = service.create_subscription(db, ctx.tenant_id, ctx.workspace_type, data)
    return SubscriptionRead.model_validate(subscription)


@router.get("", response_model=list[SubscriptionRead])
def list_subscriptions(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[SubscriptionRead]:
    subscriptions = service.list_subscriptions(db, ctx.tenant_id, ctx.workspace_type)
    return [SubscriptionRead.model_validate(s) for s in subscriptions]


@router.get("/{subscription_id}", response_model=SubscriptionRead)
def get_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> SubscriptionRead:
    subscription = service.get_subscription(db, ctx.tenant_id, ctx.workspace_type, subscription_id)
    return SubscriptionRead.model_validate(subscription)


@router.post("/{subscription_id}/cancel", response_model=SubscriptionRead)
def cancel_subscription(
    subscription_id: str,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> SubscriptionRead:
    subscription = service.cancel_subscription(db, ctx.tenant_id, ctx.workspace_type, subscription_id)
    return SubscriptionRead.model_validate(subscription)
