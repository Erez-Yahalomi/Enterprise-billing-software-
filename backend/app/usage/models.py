from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.models import TenantScopedMixin, TimestampMixin, gen_id


class UsageEvent(Base, TenantScopedMixin, TimestampMixin):
    """Raw usage event. event_id is the idempotency key: republishing the same event is a no-op."""

    __tablename__ = "usage_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_usage_event_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("use"))
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    subscription_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # api_request | storage_gb | ai_tokens | document_processed | report_generated | data_export | user_login
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UsageAggregate(Base, TenantScopedMixin, TimestampMixin):
    """Daily rollup per subscription/event_type, upserted by the worker."""

    __tablename__ = "usage_aggregates"
    __table_args__ = (
        UniqueConstraint("subscription_id", "event_type", "period_date", name="uq_usage_agg_period"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("uag"))
    subscription_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
