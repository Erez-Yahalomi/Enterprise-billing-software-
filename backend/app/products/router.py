from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.tenancy import TenantContext, get_tenant_context
from app.products import service
from app.products.schemas import PricePlanCreate, PricePlanRead, ProductCreate, ProductRead

router = APIRouter(tags=["products"])


@router.post("/products", response_model=ProductRead, status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> ProductRead:
    product = service.create_product(db, ctx.tenant_id, ctx.workspace_type, data)
    return ProductRead.model_validate(product)


@router.get("/products", response_model=list[ProductRead])
def list_products(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[ProductRead]:
    products = service.list_products(db, ctx.tenant_id, ctx.workspace_type)
    return [ProductRead.model_validate(p) for p in products]


@router.post("/price-plans", response_model=PricePlanRead, status_code=201)
def create_price_plan(
    data: PricePlanCreate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> PricePlanRead:
    plan = service.create_price_plan(db, ctx.tenant_id, ctx.workspace_type, data)
    return PricePlanRead.model_validate(plan)


@router.get("/price-plans", response_model=list[PricePlanRead])
def list_price_plans(
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[PricePlanRead]:
    plans = service.list_price_plans(db, ctx.tenant_id, ctx.workspace_type)
    return [PricePlanRead.model_validate(p) for p in plans]
