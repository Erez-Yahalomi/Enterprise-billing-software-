import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WorkspaceType(str, enum.Enum):
    demo = "demo"
    production = "production"


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantScopedMixin:
    """Every business record carries tenant_id + workspace_type for isolation.

    DEMO data always uses tenant_id="DEMO", workspace_type=demo. Real users get a
    generated tenant_id and workspace_type=production. OPA + service-layer checks
    both enforce that requests never cross this boundary.
    """

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    workspace_type: Mapped[WorkspaceType] = mapped_column(
        Enum(WorkspaceType, name="workspace_type"), index=True, nullable=False
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
