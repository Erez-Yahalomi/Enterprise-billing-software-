from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.models import TenantScopedMixin, TimestampMixin, gen_id


class Product(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("prod"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)


class PricePlan(Base, TenantScopedMixin, TimestampMixin):
    """Versioned pricing. Finalized invoices reference the plan version active at billing time."""

    __tablename__ = "price_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("plan"))
    product_id: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)  # starter | professional | enterprise
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    monthly_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    included_users: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    additional_user_price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    included_api_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overage_api_price_cents_per_unit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_token_price_cents_per_1k: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_gb_price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
