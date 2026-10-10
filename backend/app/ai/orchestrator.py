import logging

from sqlalchemy.orm import Session

from app.ai import gateway, gemini_agent, providers
from app.ai.schemas import ChatContext, ChatResponse, ChatToolCall
from app.core.actor import ActorContext
from app.core.config import get_settings
from app.core.tenancy import TenantContext

log = logging.getLogger("ai")


def run_chat(db: Session, ctx: TenantContext, actor: ActorContext, message: str, context: ChatContext) -> ChatResponse:
    settings = get_settings()

    # When Gemini is configured, let the model itself decide which of the registered
    # tools to call from the user's free-form text (real function calling) — this is the
    # only path where tool *selection* isn't the deterministic planner below. If it's not
    # configured, or the call fails for any reason (network, quota, bad key), fall back to
    # the deterministic path so the assistant still answers rather than erroring out.
    if settings.ai_provider == "gemini" and gemini_agent.is_available():
        try:
            response = gemini_agent.run_chat(db, ctx, actor, message, context)
            response.answered_by = "gemini"
            # No tool was called, so the reply is not backed by the platform's data.
            response.answer_status = "answered" if response.tool_calls else "not_understood"
            return response
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any failure falls back
            log.warning("Gemini agent failed (%s), falling back to deterministic planner", exc)

    try:
        plan = providers.plan(db, ctx, actor, message, context.model_dump())
    except providers.NeedsClarification as ask:
        return ChatResponse(reply=str(ask), tool_calls=[], pending_approval_id=None, answered_by="rules", answer_status="needs_info")

    tool_results = []
    pending_approval_id: str | None = None
    for tool_name, params in plan:
        result = gateway.invoke_tool(db, ctx, actor, tool_name, params)
        tool_results.append({"tool": tool_name, "result": result, "params": params})
        if result.status == "pending_approval":
            pending_approval_id = result.approval_id

    reply, source = providers.summarize_with_source(message, context.model_dump(), tool_results)

    return ChatResponse(
        reply=reply,
        tool_calls=[ChatToolCall(tool=r["tool"], status=r["result"].status) for r in tool_results],
        pending_approval_id=pending_approval_id,
        answered_by=source,
        answer_status="not_understood" if reply == providers.HELP_TEXT else "answered",
    )
