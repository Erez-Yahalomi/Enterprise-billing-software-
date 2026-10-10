from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.models import ApprovalRequest
from app.ai.policy import get_policy_engine
from app.ai.tools import TOOL_REGISTRY
from app.audit import service as audit_service
from app.core.actor import ActorContext
from app.core.tenancy import TenantContext


@dataclass
class ToolInvocationResult:
    status: str  # executed | pending_approval
    data: dict | None
    approval_id: str | None


def invoke_tool(db: Session, ctx: TenantContext, actor: ActorContext, tool_name: str, parameters: dict) -> ToolInvocationResult:
    spec = TOOL_REGISTRY.get(tool_name)
    if spec is None:
        # Unknown tool (including anything Tier D-shaped like execute_arbitrary_sql or
        # run_shell_command) is rejected here, before authorization is even consulted.
        raise HTTPException(status_code=403, detail=f"Tool '{tool_name}' is not permitted")

    engine = get_policy_engine()
    if not engine.is_allowed(
        tool=tool_name, tier=spec.tier, role=actor.role, tenant_id=ctx.tenant_id, workspace_type=ctx.workspace_type.value
    ):
        raise HTTPException(status_code=403, detail=f"Role '{actor.role}' is not authorized to call '{tool_name}'")

    if spec.tier == "C":
        approval = ApprovalRequest(
            tenant_id=ctx.tenant_id,
            workspace_type=ctx.workspace_type,
            tool=tool_name,
            parameters=parameters,
            requested_by=actor.user_id,
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)
        audit_service.log(
            db, ctx.tenant_id, ctx.workspace_type, "ai_agent", f"ai.tool.requested:{tool_name}",
            "approval_request", approval.id, parameters,
        )
        return ToolInvocationResult(status="pending_approval", data=None, approval_id=approval.id)

    result = spec.handler(db, ctx, parameters)
    audit_service.log(
        db, ctx.tenant_id, ctx.workspace_type,
        actor.user_id if spec.tier == "B" else "ai_agent",
        f"ai.tool.executed:{tool_name}", "tool", tool_name, parameters,
    )
    return ToolInvocationResult(status="executed", data=result, approval_id=None)


def _get_approval(db: Session, ctx: TenantContext, approval_id: str) -> ApprovalRequest:
    stmt = select(ApprovalRequest).where(
        ApprovalRequest.id == approval_id,
        ApprovalRequest.tenant_id == ctx.tenant_id,
        ApprovalRequest.workspace_type == ctx.workspace_type,
    )
    approval = db.execute(stmt).scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return approval


def list_pending_approvals(db: Session, ctx: TenantContext) -> list[ApprovalRequest]:
    stmt = select(ApprovalRequest).where(
        ApprovalRequest.tenant_id == ctx.tenant_id,
        ApprovalRequest.workspace_type == ctx.workspace_type,
        ApprovalRequest.status == "pending",
    )
    return list(db.execute(stmt).scalars().all())


def approve(db: Session, ctx: TenantContext, actor: ActorContext, approval_id: str) -> ApprovalRequest:
    if not get_policy_engine().can_approve(role=actor.role):
        raise HTTPException(status_code=403, detail=f"Role '{actor.role}' cannot approve protected actions")
    approval = _get_approval(db, ctx, approval_id)
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval request is already {approval.status}")

    spec = TOOL_REGISTRY[approval.tool]
    result = spec.handler(db, ctx, approval.parameters)

    approval.status = "approved"
    approval.resolved_by = actor.user_id
    approval.resolved_at = datetime.now(timezone.utc)
    approval.result = result
    db.commit()
    db.refresh(approval)

    audit_service.log(
        db, ctx.tenant_id, ctx.workspace_type, actor.user_id, f"ai.tool.approved:{approval.tool}",
        "approval_request", approval.id, {"parameters": approval.parameters, "result": result},
    )
    return approval


def reject(db: Session, ctx: TenantContext, actor: ActorContext, approval_id: str) -> ApprovalRequest:
    if not get_policy_engine().can_approve(role=actor.role):
        raise HTTPException(status_code=403, detail=f"Role '{actor.role}' cannot reject protected actions")
    approval = _get_approval(db, ctx, approval_id)
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail=f"Approval request is already {approval.status}")

    approval.status = "rejected"
    approval.resolved_by = actor.user_id
    approval.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(approval)

    audit_service.log(
        db, ctx.tenant_id, ctx.workspace_type, actor.user_id, f"ai.tool.rejected:{approval.tool}",
        "approval_request", approval.id, {"parameters": approval.parameters},
    )
    return approval
