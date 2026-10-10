from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UsageEventCreate(BaseModel):
    event_id: str
    customer_id: str
    subscription_id: str
    event_type: str
    quantity: int
    occurred_at: datetime


class UsageEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    customer_id: str
    subscription_id: str
    event_type: str
    quantity: int
    occurred_at: datetime


class UsageSummaryItem(BaseModel):
    event_type: str
    total_quantity: int
