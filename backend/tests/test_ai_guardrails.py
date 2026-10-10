from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException

from app.ai import gateway
from app.ai.models import ApprovalRequest
from app.billing.schemas import InvoiceGenerateRequest
from app.billing.service import generate_invoice
from app.core.actor import ActorContext
from app.core.models import WorkspaceType
from app.core.tenancy import TenantContext
from app.customers.schemas import CustomerCreate
from app.customers.service import create_customer
from app.products.schemas import PricePlanCreate, ProductCreate
from app.products.service import create_price_plan, create_product
from app.subscriptions.schemas import SubscriptionCreate
from app.subscriptions.service import create_subscription

CTX = TenantContext(tenant_id="DEMO", workspace_type=WorkspaceType.demo)


def _make_invoice(db):
    customer = create_customer(db, CTX.tenant_id, CTX.workspace_type, CustomerCreate(name="ACME", email="a@acme.example"))
    product = create_product(db, CTX.tenant_id, CTX.workspace_type, ProductCreate(name="Core", code="core"))
    plan = create_price_plan(
        db, CTX.tenant_id, CTX.workspace_type,
        PricePlanCreate(product_id=product.id, name="starter", monthly_price_cents=4900),
    )
    subscription = create_subscription(
        db, CTX.tenant_id, CTX.workspace_type,
        SubscriptionCreate(customer_id=customer.id, price_plan_id=plan.id, started_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
    )
    return generate_invoice(
        db, CTX.tenant_id, CTX.workspace_type,
        InvoiceGenerateRequest(subscription_id=subscription.id, period_start=date(2026, 9, 1), period_end=date(2026, 9, 30)),
    )


def test_unknown_tool_is_rejected(db_session):
    actor = ActorContext(user_id="u1", role="admin")
    with pytest.raises(HTTPException) as exc:
        gateway.invoke_tool(db_session, CTX, actor, "execute_arbitrary_sql", {"query": "DROP TABLE invoices"})
    assert exc.value.status_code == 403


def test_tier_a_executes_immediately_for_any_role(db_session):
    invoice = _make_invoice(db_session)
    actor = ActorContext(user_id="u1", role="support")
    result = gateway.invoke_tool(db_session, CTX, actor, "get_invoice", {"invoice_id": invoice.id})
    assert result.status == "executed"
    assert result.data["id"] == invoice.id


def test_tier_c_requires_approval_and_support_role_cannot_request_it(db_session):
    invoice = _make_invoice(db_session)
    params = {"subscription_id": invoice.subscription_id}
    support_actor = ActorContext(user_id="u1", role="support")
    with pytest.raises(HTTPException) as exc:
        gateway.invoke_tool(db_session, CTX, support_actor, "pause_subscription", params)
    assert exc.value.status_code == 403

    billing_actor = ActorContext(user_id="u2", role="billing")
    result = gateway.invoke_tool(db_session, CTX, billing_actor, "pause_subscription", params)
    assert result.status == "pending_approval"
    assert result.approval_id is not None

    approval = db_session.get(ApprovalRequest, result.approval_id)
    assert approval.status == "pending"
    # The subscription must be untouched until a human approves.
    assert approval.result is None


def test_only_admin_or_approver_can_approve_and_approval_executes_the_handler(db_session):
    invoice = _make_invoice(db_session)
    billing_actor = ActorContext(user_id="u2", role="billing")
    result = gateway.invoke_tool(
        db_session, CTX, billing_actor, "pause_subscription", {"subscription_id": invoice.subscription_id}
    )

    with pytest.raises(HTTPException) as exc:
        gateway.approve(db_session, CTX, billing_actor, result.approval_id)
    assert exc.value.status_code == 403

    admin_actor = ActorContext(user_id="u3", role="admin")
    approval = gateway.approve(db_session, CTX, admin_actor, result.approval_id)
    assert approval.status == "approved"
    assert approval.result["status"] == "paused"
