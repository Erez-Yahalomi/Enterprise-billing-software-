"""Real LLM-driven tool selection via Gemini function calling.

Unlike the deterministic keyword planner (app.ai.providers.plan), here the model itself
decides which tool(s) to call and with what arguments, based on free-form user text — this
is what lets phrasing the deterministic planner doesn't recognize still work. It can only
ever choose from the exact tools declared below, built directly from TOOL_REGISTRY — the
same fixed list every other entry point (chat, Quick Actions) is restricted to. So this is
"let the LLM decide *which* of the built-in actions to take," never "let the LLM do
anything": every call it makes still goes through app.ai.gateway.invoke_tool, which
independently re-checks role/tier authorization and still routes Tier C calls to human
approval regardless of what the model intended.
"""

import json
import logging
import time

from sqlalchemy.orm import Session

from app.ai import gateway
from app.ai.schemas import ChatContext, ChatResponse, ChatToolCall
from app.ai.tools import TOOL_REGISTRY
from app.core.actor import ActorContext
from app.core.config import get_settings
from app.core.tenancy import TenantContext

log = logging.getLogger("ai")

MAX_STEPS = 6
COOLDOWN_SECONDS = 600
_cooldown_until: dict[str, float] = {}
# retry=None: fail fast on 429s so we can move to the next model instead of the SDK's
# default multi-minute backoff on an exhausted free-tier quota.
REQUEST_OPTIONS = {"retry": None, "timeout": 90}

SYSTEM_INSTRUCTION = (
    "You are a billing assistant for a corporate billing platform. You can only act "
    "through the functions made available to you, and only using data those functions "
    "return — never state a number or fact that didn't come from a function result, and "
    "never claim to have done something you didn't call a function for. If a name in the "
    "user's message doesn't match any customer, or a lookup returns nothing, say so "
    "plainly instead of guessing. Some functions are protected: calling them submits the "
    "change for human approval rather than applying it immediately — if a function result "
    "says pending_approval, tell the user it's awaiting approval, not that it's done. "
    "For analytical questions (rankings, totals, averages, counts, breakdowns, comparisons "
    "across customers/plans/months/countries) use analyze_data, possibly several times, then "
    "explain the findings clearly with the exact figures returned, quoting dollars from "
    "value_dollars. The data you can see is only the user's currently selected workspace. "
    "For questions about one named customer use customer_overview; for general 'how is the "
    "business doing' questions use business_overview. Never say data doesn't exist without "
    "having queried it. "
    "Be efficient: the API is rate-limited, so make all independent function calls together in "
    "a single step rather than one at a time, and prefer one well-chosen analyze_data call over several. "
    "When the user says something like 'this month' and you need explicit dates, call "
    "get_current_period rather than computing or guessing dates yourself."
)


def _to_plain(value):
    """Gemini returns nested args as proto map/list wrappers; the gateway, audit log (JSON
    column) and tool handlers all expect plain dict/list/str/number values."""
    if hasattr(value, "items"):
        return {key: _to_plain(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)) or (hasattr(value, "__iter__") and not isinstance(value, (str, bytes))):
        return [_to_plain(v) for v in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _is_quota_error(exc: Exception) -> bool:
    return type(exc).__name__ in {"ResourceExhausted", "ServiceUnavailable", "NotFound", "TooManyRequests"}


def is_available() -> bool:
    return bool(get_settings().gemini_api_key)


def _json_schema_to_gemini(schema: dict):
    import google.generativeai as genai

    type_map = {
        "object": genai.protos.Type.OBJECT,
        "string": genai.protos.Type.STRING,
        "integer": genai.protos.Type.INTEGER,
        "number": genai.protos.Type.NUMBER,
        "boolean": genai.protos.Type.BOOLEAN,
        "array": genai.protos.Type.ARRAY,
    }
    kwargs: dict = {"type": type_map[schema.get("type", "object")]}
    if "description" in schema:
        kwargs["description"] = schema["description"]
    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        if properties:
            kwargs["properties"] = {key: _json_schema_to_gemini(val) for key, val in properties.items()}
        if schema.get("required"):
            kwargs["required"] = schema["required"]
    if schema.get("type") == "array" and "items" in schema:
        kwargs["items"] = _json_schema_to_gemini(schema["items"])
    return genai.protos.Schema(**kwargs)


def _build_tools():
    import google.generativeai as genai

    declarations = [
        genai.protos.FunctionDeclaration(
            name=spec.name,
            description=spec.description,
            parameters=_json_schema_to_gemini(spec.parameters),
        )
        for spec in TOOL_REGISTRY.values()
    ]
    return [genai.protos.Tool(function_declarations=declarations)]


def run_chat(
    db: Session, ctx: TenantContext, actor: ActorContext, message: str, context: ChatContext
) -> ChatResponse:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    last_error: Exception | None = None
    now = time.monotonic()
    candidates = [m for m in settings.gemini_model_list if _cooldown_until.get(m, 0) <= now]
    for model_name in candidates or settings.gemini_model_list:
        tool_calls: list[ChatToolCall] = []
        try:
            return _run_with_model(model_name, db, ctx, actor, message, context, tool_calls)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            # Skip a model that's out of quota / unavailable for a while instead of re-probing it.
            _cooldown_until[model_name] = time.monotonic() + COOLDOWN_SECONDS
            if any(TOOL_REGISTRY[c.tool].tier != "A" for c in tool_calls if c.tool in TOOL_REGISTRY):
                # A write (or approval request) already happened. Never retry on another
                # model — that could repeat it. Report what was done instead.
                done = ", ".join(f"{c.tool} ({c.status})" for c in tool_calls)
                log.exception("Gemini %s failed after a write tool ran", model_name)
                return ChatResponse(
                    reply=f"I carried out: {done}. I then hit an AI service limit before I could write "
                    "up the result — please check the affected pages, and retry in a bit if you need a summary.",
                    tool_calls=tool_calls,
                    pending_approval_id=None,
                )
            log.warning(
                "Gemini model %s failed (%s: %s); trying next",
                model_name, type(exc).__name__, str(exc)[:120], exc_info=not _is_quota_error(exc),
            )
    raise RuntimeError(f"All Gemini models failed: {last_error}")


def _run_with_model(
    model_name: str,
    db: Session,
    ctx: TenantContext,
    actor: ActorContext,
    message: str,
    context: ChatContext,
    tool_calls: list[ChatToolCall],
) -> ChatResponse:
    import google.generativeai as genai

    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(model_name, tools=_build_tools(), system_instruction=SYSTEM_INSTRUCTION)
    chat = model.start_chat()

    context_bits = {k: v for k, v in context.model_dump().items() if v}
    context_note = (
        f"Open record context: {json.dumps(context_bits)}" if context_bits else "No record is currently open."
    )
    response = chat.send_message(f"{context_note}\n\nUser: {message}", request_options=REQUEST_OPTIONS)

    pending_approval_id: str | None = None

    for _ in range(MAX_STEPS):
        function_calls = [part.function_call for part in response.parts if part.function_call]
        if not function_calls:
            break

        response_parts = []
        for fc in function_calls:
            tool_name = fc.name
            args = _to_plain(fc.args)
            try:
                result = gateway.invoke_tool(db, ctx, actor, tool_name, args)
                tool_calls.append(ChatToolCall(tool=tool_name, status=result.status))
                if result.status == "pending_approval":
                    pending_approval_id = result.approval_id
                    payload = {"status": "pending_approval", "note": "Submitted for human approval, not yet applied."}
                else:
                    payload = {"status": "executed", "result": result.data}
            except Exception as exc:  # noqa: BLE001 - surfaced to the model as a tool error, not a crash
                log.warning("Gemini tool call %s failed: %s", tool_name, exc)
                payload = {"status": "error", "error": str(exc)}

            payload = json.loads(json.dumps(payload, default=str))  # plain JSON only, for the proto Struct
            response_parts.append(
                genai.protos.Part(function_response=genai.protos.FunctionResponse(name=tool_name, response=payload))
            )

        response = chat.send_message(genai.protos.Content(parts=response_parts), request_options=REQUEST_OPTIONS)

    try:
        reply = response.text
    except ValueError:
        reply = "I ran out of steps before finishing — please try a more specific question."
    return ChatResponse(reply=reply, tool_calls=tool_calls, pending_approval_id=pending_approval_id)
