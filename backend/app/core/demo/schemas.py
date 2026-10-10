from pydantic import BaseModel


class DemoGenerateRequest(BaseModel):
    size: str = "medium"  # small | medium | large
    include_uci: bool = False


class DemoGenerateResponse(BaseModel):
    size: str
    customers: int
    usage_events_target: int
    include_uci: bool
