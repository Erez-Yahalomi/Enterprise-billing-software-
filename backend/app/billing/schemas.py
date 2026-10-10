from datetime import date

from pydantic import BaseModel, ConfigDict


class InvoiceGenerateRequest(BaseModel):
    subscription_id: str
    period_start: date
    period_end: date


class InvoiceLineItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    description: str
    kind: str
    amount_cents: int


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    subscription_id: str
    period_start: date
    period_end: date
    status: str
    subtotal_cents: int
    line_items: list[InvoiceLineItemRead]
