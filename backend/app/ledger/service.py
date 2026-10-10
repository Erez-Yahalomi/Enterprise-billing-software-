from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import WorkspaceType, gen_id
from app.ledger.models import LedgerEntry


def _already_posted(db: Session, event_id: str) -> bool:
    stmt = select(LedgerEntry.id).where(LedgerEntry.event_id == event_id).limit(1)
    return db.execute(stmt).scalar_one_or_none() is not None


def post_invoice_issued(
    db: Session, tenant_id: str, workspace_type: WorkspaceType, invoice_id: str, amount_cents: int
) -> None:
    """Accounts Receivable +amount / Revenue -amount. Idempotent per invoice."""
    event_id = f"invoice:{invoice_id}:issue"
    if _already_posted(db, event_id):
        return
    db.add_all(
        [
            LedgerEntry(
                tenant_id=tenant_id,
                workspace_type=workspace_type,
                event_id=event_id,
                reference_type="invoice",
                reference_id=invoice_id,
                account="accounts_receivable",
                direction="debit",
                amount_cents=amount_cents,
            ),
            LedgerEntry(
                tenant_id=tenant_id,
                workspace_type=workspace_type,
                event_id=event_id,
                reference_type="invoice",
                reference_id=invoice_id,
                account="revenue",
                direction="credit",
                amount_cents=amount_cents,
            ),
        ]
    )


def post_payment_received(
    db: Session,
    tenant_id: str,
    workspace_type: WorkspaceType,
    payment_id: str,
    invoice_id: str,
    amount_cents: int,
) -> None:
    """Cash +amount / Accounts Receivable -amount. Idempotent per payment."""
    event_id = f"payment:{payment_id}"
    if _already_posted(db, event_id):
        return
    db.add_all(
        [
            LedgerEntry(
                tenant_id=tenant_id,
                workspace_type=workspace_type,
                event_id=event_id,
                reference_type="payment",
                reference_id=payment_id,
                account="cash",
                direction="debit",
                amount_cents=amount_cents,
            ),
            LedgerEntry(
                tenant_id=tenant_id,
                workspace_type=workspace_type,
                event_id=event_id,
                reference_type="invoice",
                reference_id=invoice_id,
                account="accounts_receivable",
                direction="credit",
                amount_cents=amount_cents,
            ),
        ]
    )


def post_invoice_adjustment(
    db: Session, tenant_id: str, workspace_type: WorkspaceType, invoice_id: str, amount_cents: int
) -> None:
    """A correction (e.g. a discount) is a new adjustment entry — the original invoice-issue
    entries are never edited or deleted. Revenue -amount / Accounts Receivable -amount."""
    event_id = f"invoice:{invoice_id}:adjustment:{gen_id('adj')}"
    db.add_all(
        [
            LedgerEntry(
                tenant_id=tenant_id,
                workspace_type=workspace_type,
                event_id=event_id,
                reference_type="invoice",
                reference_id=invoice_id,
                account="revenue",
                direction="debit",
                amount_cents=amount_cents,
            ),
            LedgerEntry(
                tenant_id=tenant_id,
                workspace_type=workspace_type,
                event_id=event_id,
                reference_type="invoice",
                reference_id=invoice_id,
                account="accounts_receivable",
                direction="credit",
                amount_cents=amount_cents,
            ),
        ]
    )
