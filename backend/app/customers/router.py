from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.tenancy import TenantContext, get_tenant_context
from app.customers import service
from app.customers.schemas import CustomerCreate, CustomerRead

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerRead, status_code=201)
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> CustomerRead:
    customer = service.create_customer(db, ctx.tenant_id, ctx.workspace_type, data)
    return CustomerRead.model_validate(customer)


@router.get("", response_model=list[CustomerRead])
def list_customers(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[CustomerRead]:
    customers = service.list_customers(db, ctx.tenant_id, ctx.workspace_type)
    return [CustomerRead.model_validate(c) for c in customers]


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> CustomerRead:
    customer = service.get_customer(db, ctx.tenant_id, ctx.workspace_type, customer_id)
    return CustomerRead.model_validate(customer)
