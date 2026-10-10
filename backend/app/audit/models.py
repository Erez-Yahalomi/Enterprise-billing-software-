from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.models import TenantScopedMixin, TimestampMixin, gen_id


class AuditLog(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("aud"))
    actor: Mapped[str] = mapped_column(String(64), nullable=False)  # user_id or "ai_agent"
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class SupportCase(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "support_cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("case"))
    customer_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
