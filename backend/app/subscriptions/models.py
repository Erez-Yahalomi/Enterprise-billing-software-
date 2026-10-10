from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.models import TenantScopedMixin, TimestampMixin, gen_id


class Subscription(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("sub"))
    customer_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    price_plan_id: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    # active | trialing | paused | canceled
    quantity_users: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Entitlement(Base, TenantScopedMixin, TimestampMixin):
    """Snapshot of what a subscription currently grants, derived from its price plan."""

    __tablename__ = "entitlements"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("ent"))
    subscription_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    included_users: Mapped[int] = mapped_column(Integer, nullable=False)
    included_api_calls: Mapped[int] = mapped_column(Integer, nullable=False)
