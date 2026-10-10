from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.billing.models import Invoice, InvoiceLineItem
from app.billing.schemas import InvoiceGenerateRequest
from app.core.models import WorkspaceType
from app.ledger import service as ledger_service
from app.products import service as products_service
from app.subscriptions import service as subscriptions_service
from app.usage import service as usage_service


def generate_invoice(
    db: Session, tenant_id: str, workspace_type: WorkspaceType, data: InvoiceGenerateRequest
) -> Invoice:
    subscription = subscriptions_service.get_subscription(db, tenant_id, workspace_type, data.subscription_id)
    plan = products_service.get_price_plan(db, tenant_id, workspace_type, subscription.price_plan_id)
    usage_items = {
        item.event_type: item.total_quantity
        for item in usage_service.get_usage_summary(
            db, tenant_id, workspace_type, subscription.id, data.period_start, data.period_end
        )
    }

    invoice = Invoice(
        tenant_id=tenant_id,
        workspace_type=workspace_type,
        customer_id=subscription.customer_id,
        subscription_id=subscription.id,
        period_start=data.period_start,
        period_end=data.period_end,
        status="finalized",
    )
    db.add(invoice)
    db.flush()

    line_items: list[InvoiceLineItem] = []

    def add_line(description: str, kind: str, amount_cents: int) -> None:
        if amount_cents <= 0:
            return
        line_items.append(
            InvoiceLineItem(
                tenant_id=tenant_id,
                workspace_type=workspace_type,
                invoice_id=invoice.id,
                description=description,
                kind=kind,
                amount_cents=amount_cents,
            )
        )

    add_line("Base subscription", "subscription_fee", plan.monthly_price_cents)

    extra_users = max(0, subscription.quantity_users - plan.included_users)
    add_line(f"Additional users ({extra_users})", "users", extra_users * plan.additional_user_price_cents)

    api_calls = usage_items.get("api_request", 0)
    api_overage = max(0, api_calls - plan.included_api_calls)
    add_line(f"API usage overage ({api_overage} calls)", "api_usage", api_overage * plan.overage_api_price_cents_per_unit)

    ai_tokens = usage_items.get("ai_tokens", 0)
    add_line(
        f"AI token usage ({ai_tokens} tokens)",
        "ai_usage",
        round(ai_tokens / 1000 * plan.ai_token_price_cents_per_1k),
    )

    storage_gb = usage_items.get("storage_gb", 0)
    add_line(f"Storage ({storage_gb} GB)", "storage", storage_gb * plan.storage_gb_price_cents)

    db.add_all(line_items)
    invoice.subtotal_cents = sum(li.amount_cents for li in line_items)

    ledger_service.post_invoice_issued(db, tenant_id, workspace_type, invoice.id, invoice.subtotal_cents)

    db.commit()
    return get_invoice(db, tenant_id, workspace_type, invoice.id)


def get_invoice(db: Session, tenant_id: str, workspace_type: WorkspaceType, invoice_id: str) -> Invoice:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.line_items))
        .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id, Invoice.workspace_type == workspace_type)
    )
    invoice = db.execute(stmt).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


def list_invoices(db: Session, tenant_id: str, workspace_type: WorkspaceType) -> list[Invoice]:
    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.line_items))
        .where(Invoice.tenant_id == tenant_id, Invoice.workspace_type == workspace_type)
    )
    return list(db.execute(stmt).scalars().all())


def compare_invoices(
    db: Session, tenant_id: str, workspace_type: WorkspaceType, invoice_id_a: str, invoice_id_b: str
) -> dict:
    invoice_a = get_invoice(db, tenant_id, workspace_type, invoice_id_a)
    invoice_b = get_invoice(db, tenant_id, workspace_type, invoice_id_b)

    kinds = {li.kind for li in invoice_a.line_items} | {li.kind for li in invoice_b.line_items}
    amounts_a = {li.kind: li.amount_cents for li in invoice_a.line_items}
    amounts_b = {li.kind: li.amount_cents for li in invoice_b.line_items}

    line_item_diffs = [
        {
            "kind": kind,
            "amount_a_cents": amounts_a.get(kind, 0),
            "amount_b_cents": amounts_b.get(kind, 0),
            "diff_cents": amounts_b.get(kind, 0) - amounts_a.get(kind, 0),
        }
        for kind in sorted(kinds)
    ]

    return {
        "invoice_id_a": invoice_a.id,
        "invoice_id_b": invoice_b.id,
        "subtotal_a_cents": invoice_a.subtotal_cents,
        "subtotal_b_cents": invoice_b.subtotal_cents,
        "total_diff_cents": invoice_b.subtotal_cents - invoice_a.subtotal_cents,
        "line_item_diffs": line_item_diffs,
    }
