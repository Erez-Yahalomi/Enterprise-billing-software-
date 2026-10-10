from datetime import date

from pydantic import BaseModel


class UsageByDayItem(BaseModel):
    day: date
    event_type: str
    total_quantity: int
