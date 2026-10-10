from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.models import TenantScopedMixin, TimestampMixin, gen_id


class ApprovalRequest(Base, TenantScopedMixin, TimestampMixin):
    """A Tier C (protected) tool call proposed by the AI agent, awaiting human approval
    before the underlying business service actually executes it."""

    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("appr"))
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)  # pending|approved|rejected
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
