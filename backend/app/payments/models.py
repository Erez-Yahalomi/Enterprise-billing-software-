from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.models import TenantScopedMixin, TimestampMixin, gen_id


class Payment(Base, TenantScopedMixin, TimestampMixin):
    """payment_intent_id is the idempotency key so a retried/duplicate request never double-charges."""

    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("payment_intent_id", name="uq_payment_intent_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("pay"))
    payment_intent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    invoice_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    # pending | succeeded | failed
    provider: Mapped[str] = mapped_column(String(32), default="mock", nullable=False)
