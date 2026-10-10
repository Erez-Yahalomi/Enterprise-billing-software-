from datetime import date, datetime, timezone

from sqlalchemy import select

from app.ledger.models import LedgerEntry


def test_full_billing_flow(client):
    customer = client.post(
        "/customers", json={"name": "ACME Corporation", "email": "billing@acme.example", "country": "US"}
    ).json()

    product = client.post("/products", json={"name": "Billing Platform", "code": "core"}).json()

    plan = client.post(
        "/price-plans",
        json={
            "product_id": product["id"],
            "name": "professional",
            "monthly_price_cents": 29900,
            "included_users": 50,
            "additional_user_price_cents": 2000,
            "included_api_calls": 1_000_000,
            "overage_api_price_cents_per_unit": 1,
            "ai_token_price_cents_per_1k": 50,
            "storage_gb_price_cents": 100,
        },
    ).json()

    subscription = client.post(
        "/subscriptions",
        json={"customer_id": customer["id"], "price_plan_id": plan["id"], "quantity_users": 55},
    ).json()
    assert subscription["status"] == "active"

    period_start = date(2026, 9, 1)
    period_end = date(2026, 9, 30)
    occurred_at = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc).isoformat()

    usage_events = [
        {"event_id": "evt-api-1", "event_type": "api_request", "quantity": 700_000},
        {"event_id": "evt-api-2", "event_type": "api_request", "quantity": 500_000},
        {"event_id": "evt-ai-1", "event_type": "ai_tokens", "quantity": 200_000},
        {"event_id": "evt-storage-1", "event_type": "storage_gb", "quantity": 10},
    ]
    for evt in usage_events:
        resp = client.post(
            "/usage",
            json={
                "event_id": evt["event_id"],
                "customer_id": customer["id"],
                "subscription_id": subscription["id"],
                "event_type": evt["event_type"],
                "quantity": evt["quantity"],
                "occurred_at": occurred_at,
            },
        )
        assert resp.status_code == 201

    # Re-publishing the same event_id must be a no-op (idempotent), not a double count.
    dup = client.post(
        "/usage",
        json={
            "event_id": "evt-api-1",
            "customer_id": customer["id"],
            "subscription_id": subscription["id"],
            "event_type": "api_request",
            "quantity": 700_000,
            "occurred_at": occurred_at,
        },
    )
    assert dup.status_code == 201

    invoice = client.post(
        "/invoices/generate",
        json={
            "subscription_id": subscription["id"],
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        },
    ).json()

    # base 29900 + 5 extra users * 2000 = 10000 + api overage 200_000 * 1 = 200000
    # + ai tokens 200_000/1000 * 50 = 10000 + storage 10 * 100 = 1000
    expected_subtotal = 29900 + 10000 + 200000 + 10000 + 1000
    assert invoice["subtotal_cents"] == expected_subtotal
    assert invoice["status"] == "finalized"
    kinds = {li["kind"] for li in invoice["line_items"]}
    assert kinds == {"subscription_fee", "users", "api_usage", "ai_usage", "storage"}

    payment = client.post(
        "/payments",
        json={
            "payment_intent_id": "pi-1",
            "invoice_id": invoice["id"],
            "amount_cents": expected_subtotal,
        },
    ).json()
    assert payment["status"] == "succeeded"

    paid_invoice = client.get(f"/invoices/{invoice['id']}").json()
    assert paid_invoice["status"] == "paid"

    # Duplicate payment intent must not double-post to the ledger.
    dup_payment = client.post(
        "/payments",
        json={
            "payment_intent_id": "pi-1",
            "invoice_id": invoice["id"],
            "amount_cents": expected_subtotal,
        },
    ).json()
    assert dup_payment["id"] == payment["id"]

    with client.session_factory() as db:
        entries = db.execute(select(LedgerEntry)).scalars().all()
        debit_total = sum(e.amount_cents for e in entries if e.direction == "debit")
        credit_total = sum(e.amount_cents for e in entries if e.direction == "credit")
        assert debit_total == credit_total
        # 2 entries for invoice issue + 2 for payment = 4, not doubled by the retried calls above.
        assert len(entries) == 4
