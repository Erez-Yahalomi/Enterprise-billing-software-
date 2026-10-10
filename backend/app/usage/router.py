from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.tenancy import TenantContext, get_tenant_context
from app.usage import service
from app.usage.schemas import UsageEventCreate, UsageEventRead, UsageSummaryItem

router = APIRouter(prefix="/usage", tags=["usage"])


@router.post("", response_model=UsageEventRead, status_code=201)
def record_usage(
    data: UsageEventCreate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> UsageEventRead:
    event = service.record_usage(db, ctx.tenant_id, ctx.workspace_type, data)
    return UsageEventRead.model_validate(event)


@router.get("/summary", response_model=list[UsageSummaryItem])
def usage_summary(
    subscription_id: str,
    period_start: date,
    period_end: date,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[UsageSummaryItem]:
    return service.get_usage_summary(db, ctx.tenant_id, ctx.workspace_type, subscription_id, period_start, period_end)
