from pydantic import BaseModel, ConfigDict


class PaymentCreate(BaseModel):
    payment_intent_id: str
    invoice_id: str
    amount_cents: int


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    payment_intent_id: str
    invoice_id: str
    customer_id: str
    amount_cents: int
    status: str
    provider: str
