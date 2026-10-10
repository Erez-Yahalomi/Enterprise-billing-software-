from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubscriptionCreate(BaseModel):
    customer_id: str
    price_plan_id: str
    quantity_users: int = 1
    started_at: datetime | None = None


class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    price_plan_id: str
    status: str
    quantity_users: int
    started_at: datetime
    canceled_at: datetime | None
