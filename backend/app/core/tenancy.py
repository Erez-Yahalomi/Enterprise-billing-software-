from dataclasses import dataclass

from fastapi import Header

from app.core.models import WorkspaceType


@dataclass
class TenantContext:
    tenant_id: str
    workspace_type: WorkspaceType


def get_tenant_context(
    x_tenant_id: str = Header(default="DEMO"),
    x_workspace_type: WorkspaceType = Header(default=WorkspaceType.demo),
) -> TenantContext:
    """Resolves the active tenant/workspace for a request.

    Phase 2 reads this from headers so the business flow can be built and tested
    end-to-end without full auth. Phase 5 wires this to the logged-in user's
    active_tenant_id/active_workspace_type instead of trusting client-supplied headers.
    """
    return TenantContext(tenant_id=x_tenant_id, workspace_type=x_workspace_type)
