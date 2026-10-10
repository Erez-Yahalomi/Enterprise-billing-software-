from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.tenancy import TenantContext, get_tenant_context
from app.payments import service
from app.payments.schemas import PaymentCreate, PaymentRead

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", response_model=PaymentRead, status_code=201)
def record_payment(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> PaymentRead:
    payment = service.record_payment(db, ctx.tenant_id, ctx.workspace_type, data)
    return PaymentRead.model_validate(payment)


@router.get("", response_model=list[PaymentRead])
def list_payments(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[PaymentRead]:
    payments = service.list_payments(db, ctx.tenant_id, ctx.workspace_type)
    return [PaymentRead.model_validate(p) for p in payments]
