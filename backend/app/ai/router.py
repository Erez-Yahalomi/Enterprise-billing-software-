from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai import gateway, orchestrator
from app.ai.schemas import (
    ApprovalRead,
    ChatRequest,
    ChatResponse,
    ToolInvokeRequest,
    ToolInvokeResponse,
)
from app.core.actor import ActorContext, get_actor_context
from app.core.db import get_db
from app.core.tenancy import TenantContext, get_tenant_context

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
    actor: ActorContext = Depends(get_actor_context),
) -> ChatResponse:
    return orchestrator.run_chat(db, ctx, actor, data.message, data.context)


@router.post("/tools/{tool_name}", response_model=ToolInvokeResponse)
def invoke_tool(
    tool_name: str,
    data: ToolInvokeRequest,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
    actor: ActorContext = Depends(get_actor_context),
) -> ToolInvokeResponse:
    result = gateway.invoke_tool(db, ctx, actor, tool_name, data.parameters)
    return ToolInvokeResponse(status=result.status, data=result.data, approval_id=result.approval_id)


@router.get("/approvals", response_model=list[ApprovalRead])
def list_approvals(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[ApprovalRead]:
    approvals = gateway.list_pending_approvals(db, ctx)
    return [ApprovalRead.model_validate(a) for a in approvals]


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalRead)
def approve_request(
    approval_id: str,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
    actor: ActorContext = Depends(get_actor_context),
) -> ApprovalRead:
    approval = gateway.approve(db, ctx, actor, approval_id)
    return ApprovalRead.model_validate(approval)


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalRead)
def reject_request(
    approval_id: str,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
    actor: ActorContext = Depends(get_actor_context),
) -> ApprovalRead:
    approval = gateway.reject(db, ctx, actor, approval_id)
    return ApprovalRead.model_validate(approval)
