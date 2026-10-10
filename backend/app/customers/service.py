from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import WorkspaceType
from app.customers.models import Customer
from app.customers.schemas import CustomerCreate


def create_customer(db: Session, tenant_id: str, workspace_type: WorkspaceType, data: CustomerCreate) -> Customer:
    customer = Customer(
        tenant_id=tenant_id,
        workspace_type=workspace_type,
        name=data.name,
        email=data.email,
        country=data.country,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def get_customer(db: Session, tenant_id: str, workspace_type: WorkspaceType, customer_id: str) -> Customer:
    stmt = select(Customer).where(
        Customer.id == customer_id,
        Customer.tenant_id == tenant_id,
        Customer.workspace_type == workspace_type,
    )
    customer = db.execute(stmt).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def list_customers(db: Session, tenant_id: str, workspace_type: WorkspaceType) -> list[Customer]:
    stmt = select(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.workspace_type == workspace_type,
    )
    return list(db.execute(stmt).scalars().all())
