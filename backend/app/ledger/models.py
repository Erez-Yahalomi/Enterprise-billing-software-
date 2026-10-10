from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.models import TenantScopedMixin, TimestampMixin, gen_id


class LedgerEntry(Base, TenantScopedMixin, TimestampMixin):
    """Append-only double-entry ledger row. Never updated or deleted after creation.

    Corrections are made by inserting new adjustment/debit-note/credit-note entries,
    never by editing or deleting existing rows (see spec section 7).
    """

    __tablename__ = "ledger_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("led"))
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reference_type: Mapped[str] = mapped_column(String(32), nullable=False)  # invoice | payment | adjustment
    reference_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    account: Mapped[str] = mapped_column(String(64), nullable=False)
    # accounts_receivable | revenue | cash | credit_balance
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # debit | credit
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
