from datetime import date, datetime, timezone


def _setup_subscription_with_two_invoices(client):
    customer = client.post("/customers", json={"name": "ACME Corporation", "email": "billing@acme.example"}).json()
    product = client.post("/products", json={"name": "Billing Platform", "code": "core"}).json()
    plan = client.post(
        "/price-plans",
        json={
            "product_id": product["id"],
            "name": "professional",
            "monthly_price_cents": 29900,
            "included_users": 50,
            "included_api_calls": 1_000_000,
            "overage_api_price_cents_per_unit": 1,
        },
    ).json()
    subscription = client.post(
        "/subscriptions",
        json={"customer_id": customer["id"], "price_plan_id": plan["id"], "quantity_users": 50},
    ).json()

    # August: no overage.
    client.post(
        "/usage",
        json={
            "event_id": "aug-api-1",
            "customer_id": customer["id"],
            "subscription_id": subscription["id"],
            "event_type": "api_request",
            "quantity": 500_000,
            "occurred_at": datetime(2026, 8, 15, tzinfo=timezone.utc).isoformat(),
        },
    )
    august_invoice = client.post(
        "/invoices/generate",
        json={"subscription_id": subscription["id"], "period_start": "2026-08-01", "period_end": "2026-08-31"},
    ).json()

    # September: significant overage, so the invoice is meaningfully higher.
    client.post(
        "/usage",
        json={
            "event_id": "sep-api-1",
            "customer_id": customer["id"],
            "subscription_id": subscription["id"],
            "event_type": "api_request",
            "quantity": 1_300_000,
            "occurred_at": datetime(2026, 9, 15, tzinfo=timezone.utc).isoformat(),
        },
    )
    september_invoice = client.post(
        "/invoices/generate",
        json={"subscription_id": subscription["id"], "period_start": "2026-09-01", "period_end": "2026-09-30"},
    ).json()

    return customer, subscription, august_invoice, september_invoice


def test_ai_explains_why_invoice_increased(client):
    customer, subscription, august_invoice, september_invoice = _setup_subscription_with_two_invoices(client)
    assert september_invoice["subtotal_cents"] > august_invoice["subtotal_cents"]

    response = client.post(
        "/ai/chat",
        json={
            "message": "Why did ACME's September invoice increase?",
            "context": {"invoice_id": september_invoice["id"]},
        },
    ).json()

    tool_names = [c["tool"] for c in response["tool_calls"]]
    assert "compare_invoices" in tool_names
    assert "higher" in response["reply"]
    assert "api_usage" in response["reply"]


def test_ai_protected_action_requires_approval_end_to_end(client):
    customer, subscription, august_invoice, september_invoice = _setup_subscription_with_two_invoices(client)

    invoke = client.post(
        "/ai/tools/pause_subscription",
        json={"parameters": {"subscription_id": subscription["id"]}},
        headers={"X-User-Role": "billing"},
    ).json()
    assert invoke["status"] == "pending_approval"
    approval_id = invoke["approval_id"]

    pending = client.get("/ai/approvals").json()
    assert any(a["id"] == approval_id for a in pending)

    # A support-tier user cannot approve a protected action.
    denied = client.post(f"/ai/approvals/{approval_id}/approve", headers={"X-User-Role": "support"})
    assert denied.status_code == 403

    approved = client.post(f"/ai/approvals/{approval_id}/approve", headers={"X-User-Role": "admin"}).json()
    assert approved["status"] == "approved"
    assert approved["result"]["status"] == "paused"

    subscription_after = client.get(f"/subscriptions/{subscription['id']}").json()
    assert subscription_after["status"] == "paused"


def test_ai_rejects_unknown_and_prohibited_tools(client):
    resp = client.post("/ai/tools/execute_arbitrary_sql", json={"parameters": {"query": "DROP TABLE invoices"}})
    assert resp.status_code == 403
    resp = client.post("/ai/tools/run_shell_command", json={"parameters": {"cmd": "rm -rf /"}})
    assert resp.status_code == 403
