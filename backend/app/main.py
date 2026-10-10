from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import model_registry  # noqa: F401  (registers all models for metadata/migrations)
from app.ai.router import router as ai_router
from app.analytics.router import router as analytics_router
from app.billing.router import router as billing_router
from app.core.db import get_db
from app.customers.router import router as customers_router
from app.demo.router import router as demo_router
from app.payments.router import router as payments_router
from app.products.router import router as products_router
from app.subscriptions.router import router as subscriptions_router
from app.usage.router import router as usage_router

app = FastAPI(title="Corporate Billing Platform API")

app.include_router(customers_router)
app.include_router(products_router)
app.include_router(subscriptions_router)
app.include_router(usage_router)
app.include_router(billing_router)
app.include_router(payments_router)
app.include_router(analytics_router)
app.include_router(ai_router)
app.include_router(demo_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
