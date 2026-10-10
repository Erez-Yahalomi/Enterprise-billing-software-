from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import WorkspaceType
from app.products.models import PricePlan, Product
from app.products.schemas import PricePlanCreate, ProductCreate


def create_product(db: Session, tenant_id: str, workspace_type: WorkspaceType, data: ProductCreate) -> Product:
    product = Product(tenant_id=tenant_id, workspace_type=workspace_type, name=data.name, code=data.code)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def list_products(db: Session, tenant_id: str, workspace_type: WorkspaceType) -> list[Product]:
    stmt = select(Product).where(Product.tenant_id == tenant_id, Product.workspace_type == workspace_type)
    return list(db.execute(stmt).scalars().all())


def create_price_plan(
    db: Session, tenant_id: str, workspace_type: WorkspaceType, data: PricePlanCreate
) -> PricePlan:
    """Pricing is versioned: superseding a plan with the same name deactivates the old
    version rather than mutating it, so invoices already billed under it stay correct."""
    stmt = select(PricePlan).where(
        PricePlan.tenant_id == tenant_id,
        PricePlan.workspace_type == workspace_type,
        PricePlan.product_id == data.product_id,
        PricePlan.name == data.name,
        PricePlan.is_active.is_(True),
    )
    previous = db.execute(stmt).scalar_one_or_none()
    next_version = 1
    if previous is not None:
        previous.is_active = False
        next_version = previous.version + 1

    plan = PricePlan(
        tenant_id=tenant_id,
        workspace_type=workspace_type,
        product_id=data.product_id,
        name=data.name,
        version=next_version,
        monthly_price_cents=data.monthly_price_cents,
        included_users=data.included_users,
        additional_user_price_cents=data.additional_user_price_cents,
        included_api_calls=data.included_api_calls,
        overage_api_price_cents_per_unit=data.overage_api_price_cents_per_unit,
        ai_token_price_cents_per_1k=data.ai_token_price_cents_per_1k,
        storage_gb_price_cents=data.storage_gb_price_cents,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def get_price_plan(db: Session, tenant_id: str, workspace_type: WorkspaceType, price_plan_id: str) -> PricePlan:
    stmt = select(PricePlan).where(
        PricePlan.id == price_plan_id,
        PricePlan.tenant_id == tenant_id,
        PricePlan.workspace_type == workspace_type,
    )
    plan = db.execute(stmt).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Price plan not found")
    return plan


def list_price_plans(db: Session, tenant_id: str, workspace_type: WorkspaceType) -> list[PricePlan]:
    stmt = select(PricePlan).where(
        PricePlan.tenant_id == tenant_id,
        PricePlan.workspace_type == workspace_type,
        PricePlan.is_active.is_(True),
    )
    return list(db.execute(stmt).scalars().all())
