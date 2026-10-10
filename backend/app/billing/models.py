from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.models import TenantScopedMixin, TimestampMixin, gen_id


class Invoice(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("inv"))
    customer_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    subscription_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    # draft | finalized | paid | overdue | void
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    line_items: Mapped[list["InvoiceLineItem"]] = relationship(back_populates="invoice")


class InvoiceLineItem(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "invoice_line_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("ili"))
    invoice_id: Mapped[str] = mapped_column(String(32), ForeignKey("invoices.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    # subscription_fee | api_usage | ai_usage | storage | users | discount | credit
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="line_items")
