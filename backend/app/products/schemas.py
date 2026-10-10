from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    name: str
    code: str


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    code: str


class PricePlanCreate(BaseModel):
    product_id: str
    name: str
    monthly_price_cents: int
    included_users: int = 0
    additional_user_price_cents: int = 0
    included_api_calls: int = 0
    overage_api_price_cents_per_unit: int = 0
    ai_token_price_cents_per_1k: int = 0
    storage_gb_price_cents: int = 0


class PricePlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    name: str
    version: int
    monthly_price_cents: int
    included_users: int
    additional_user_price_cents: int
    included_api_calls: int
    overage_api_price_cents_per_unit: int
    ai_token_price_cents_per_1k: int
    storage_gb_price_cents: int
    is_active: bool
