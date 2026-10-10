from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.core.models import WorkspaceType


def log(
    db: Session,
    tenant_id: str,
    workspace_type: WorkspaceType,
    actor: str,
    action: str,
    target_type: str,
    target_id: str,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            workspace_type=workspace_type,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
        )
    )
    db.commit()
