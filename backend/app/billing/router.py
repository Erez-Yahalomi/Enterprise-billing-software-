from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.billing import service
from app.billing.schemas import InvoiceGenerateRequest, InvoiceRead
from app.core.db import get_db
from app.core.tenancy import TenantContext, get_tenant_context

router = APIRouter(tags=["billing"])


@router.post("/invoices/generate", response_model=InvoiceRead, status_code=201)
def generate_invoice(
    data: InvoiceGenerateRequest,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> InvoiceRead:
    invoice = service.generate_invoice(db, ctx.tenant_id, ctx.workspace_type, data)
    return InvoiceRead.model_validate(invoice)


@router.get("/invoices", response_model=list[InvoiceRead])
def list_invoices(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[InvoiceRead]:
    invoices = service.list_invoices(db, ctx.tenant_id, ctx.workspace_type)
    return [InvoiceRead.model_validate(i) for i in invoices]


@router.get("/invoices/{invoice_id}", response_model=InvoiceRead)
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> InvoiceRead:
    invoice = service.get_invoice(db, ctx.tenant_id, ctx.workspace_type, invoice_id)
    return InvoiceRead.model_validate(invoice)
