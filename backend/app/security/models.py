from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.models import TimestampMixin, WorkspaceType, gen_id


class Tenant(Base, TimestampMixin):
    """A tenant is either the fixed DEMO tenant or one real-user tenant (workspace_type=production)."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workspace_type: Mapped[WorkspaceType] = mapped_column(nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: gen_id("usr"))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="admin", nullable=False)
    # admin | billing | support | approver
    active_tenant_id: Mapped[str] = mapped_column(String(64), default="DEMO", nullable=False)
    active_workspace_type: Mapped[WorkspaceType] = mapped_column(default=WorkspaceType.demo, nullable=False)
