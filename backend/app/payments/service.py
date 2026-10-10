from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing import service as billing_service
from app.core.models import WorkspaceType
from app.ledger import service as ledger_service
from app.payments.models import Payment
from app.payments.provider import get_payment_provider
from app.payments.schemas import PaymentCreate


def record_payment(db: Session, tenant_id: str, workspace_type: WorkspaceType, data: PaymentCreate) -> Payment:
    """Idempotent on payment_intent_id: retried/duplicated requests never double-charge or
    double-post to the ledger."""
    existing = db.execute(
        select(Payment).where(Payment.payment_intent_id == data.payment_intent_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    invoice = billing_service.get_invoice(db, tenant_id, workspace_type, data.invoice_id)
    provider = get_payment_provider()
    status = provider.charge(data.amount_cents)

    payment = Payment(
        tenant_id=tenant_id,
        workspace_type=workspace_type,
        payment_intent_id=data.payment_intent_id,
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        amount_cents=data.amount_cents,
        status=status,
        provider="mock",
    )
    db.add(payment)
    db.flush()

    if status == "succeeded":
        if data.amount_cents >= invoice.subtotal_cents:
            invoice.status = "paid"
        ledger_service.post_payment_received(
            db, tenant_id, workspace_type, payment.id, invoice.id, data.amount_cents
        )

    db.commit()
    db.refresh(payment)
    return payment


def list_payments(db: Session, tenant_id: str, workspace_type: WorkspaceType) -> list[Payment]:
    stmt = select(Payment).where(Payment.tenant_id == tenant_id, Payment.workspace_type == workspace_type)
    return list(db.execute(stmt).scalars().all())
