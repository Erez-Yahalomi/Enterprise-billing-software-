from datetime import date

from fastapi import APIRouter, Depends

from app.analytics import service
from app.analytics.schemas import UsageByDayItem
from app.core.tenancy import TenantContext, get_tenant_context

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/usage-by-day", response_model=list[UsageByDayItem])
def usage_by_day(
    subscription_id: str,
    period_start: date,
    period_end: date,
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[UsageByDayItem]:
    return service.query_usage_by_day(ctx.tenant_id, subscription_id, period_start, period_end)
