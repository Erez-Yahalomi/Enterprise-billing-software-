from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatContext(BaseModel):
    customer_id: str | None = None
    subscription_id: str | None = None
    invoice_id: str | None = None


class ChatRequest(BaseModel):
    message: str
    context: ChatContext = ChatContext()


class ChatToolCall(BaseModel):
    tool: str
    status: str


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ChatToolCall]
    pending_approval_id: str | None = None
    # Verification for the UI: which engine wrote the reply (gemini | ollama | rules) and whether
    # the question was actually answered (answered | needs_info | not_understood).
    answered_by: str = "rules"
    answer_status: str = "answered"


class ToolInvokeRequest(BaseModel):
    parameters: dict = {}


class ToolInvokeResponse(BaseModel):
    status: str
    data: dict | list | None = None
    approval_id: str | None = None


class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tool: str
    parameters: dict
    status: str
    requested_by: str
    resolved_by: str | None
    resolved_at: datetime | None
    result: dict | None
