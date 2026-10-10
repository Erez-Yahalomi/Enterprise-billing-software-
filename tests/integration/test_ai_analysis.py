DEMO_HEADERS = {"X-Tenant-Id": "DEMO", "X-Workspace-Type": "demo"}


def _seed_small_demo(client):
    assert client.post("/demo/generate", json={"size": "small", "include_uci": False}).status_code == 200


def test_analyze_data_tool_ranks_customers_by_revenue_on_demo_data(client):
    _seed_small_demo(client)
    resp = client.post(
        "/ai/tools/analyze_data",
        json={"parameters": {"dataset": "invoices", "metric": "sum", "field": "subtotal_cents", "group_by": "customer", "top_n": 3}},
        headers=DEMO_HEADERS,
    ).json()
    assert resp["status"] == "executed"
    results = resp["data"]["results"]
    assert len(results) == 3
    assert results[0]["value"] >= results[1]["value"] >= results[2]["value"]
    assert results[0]["value_dollars"] == round(results[0]["value"] / 100, 2)


def test_free_text_analysis_question_is_answered_from_demo_data(client):
    _seed_small_demo(client)
    reply = client.post(
        "/ai/chat", json={"message": "Show me the top 3 customers by revenue", "context": {}}, headers=DEMO_HEADERS
    ).json()
    assert [c["tool"] for c in reply["tool_calls"]] == ["analyze_data"]
    assert "customer" in reply["reply"] and "$" in reply["reply"]

    failed = client.post(
        "/ai/chat", json={"message": "How many failed payments do we have?", "context": {}}, headers=DEMO_HEADERS
    ).json()
    assert [c["tool"] for c in failed["tool_calls"]] == ["analyze_data"]


def test_analysis_only_sees_the_callers_workspace(client):
    _seed_small_demo(client)
    mine = client.post(
        "/ai/tools/analyze_data",
        json={"parameters": {"dataset": "customers"}},
        headers={"X-Tenant-Id": "TENANT_MINE", "X-Workspace-Type": "production"},
    ).json()
    assert mine["data"]["results"][0]["value"] == 0


def _analyze(client, **params):
    return client.post("/ai/tools/analyze_data", json={"parameters": params}, headers=DEMO_HEADERS).json()["data"]


def test_everyday_status_words_map_to_real_statuses(client):
    """Regression: the model filtered invoices on status 'unpaid' (real value: 'finalized'),
    got zero rows, and told the user there were no unpaid invoices."""
    _seed_small_demo(client)
    real = _analyze(client, dataset="invoices", filters={"status": "finalized"})
    for word in ("unpaid", "Outstanding", "open", "overdue"):
        aliased = _analyze(client, dataset="invoices", filters={"status": word})
        assert aliased["results"][0]["value"] == real["results"][0]["value"] > 0


def test_filter_matching_nothing_returns_a_warning_with_valid_values_not_silent_zero(client):
    _seed_small_demo(client)
    data = _analyze(client, dataset="invoices", filters={"status": "banana"})
    assert data["results"] == []
    assert "warning" in data
    assert "finalized" in data["available_values"]["status"]

    unknown_column = _analyze(client, dataset="invoices", filters={"colour": "red"})
    assert "error" in unknown_column


def test_analysis_rejects_unsupported_requests_instead_of_running_them(client):
    bad = client.post(
        "/ai/tools/analyze_data", json={"parameters": {"dataset": "users"}}, headers=DEMO_HEADERS
    ).json()
    assert "error" in bad["data"]
    bad_group = client.post(
        "/ai/tools/analyze_data",
        json={"parameters": {"dataset": "customers", "group_by": "password"}},
        headers=DEMO_HEADERS,
    ).json()
    assert "error" in bad_group["data"]


def _ask(client, text, context=None):
    return client.post("/ai/chat", json={"message": text, "context": context or {}}, headers=DEMO_HEADERS).json()


def test_assistant_answers_a_wide_range_of_data_questions_correctly(client):
    _seed_small_demo(client)
    truth = lambda **p: _analyze(client, **p)["results"]  # noqa: E731

    # Named customer -> exact figures from the customer's own records.
    acme = _ask(client, "How much has ACME Corporation been billed and what is their plan?")
    assert [c["tool"] for c in acme["tool_calls"]] == ["customer_overview"]
    assert "ACME Corporation" in acme["reply"] and "enterprise" in acme["reply"] and "$" in acme["reply"]

    # Unpaid invoices total == finalized invoices total.
    unpaid = _ask(client, "What is the total value of unpaid invoices?")
    expected = truth(dataset="invoices", metric="sum", field="subtotal_cents", filters={"status": "finalized"})[0]["value_dollars"]
    assert f"${expected:,.2f}" in unpaid["reply"]

    # Count with a filter.
    failed = _ask(client, "how many failed payments are there?")
    n = truth(dataset="payments", filters={"status": "failed"})[0]["value"]
    assert f": {n:,.0f}" in failed["reply"]

    # Average / grouping / month filter / plan filter.
    assert "avg" in _ask(client, "what is the average invoice amount by plan?")["reply"]
    assert "usage" in _ask(client, "api usage by month")["reply"]
    assert "plan=starter" in _ask(client, "how many starter subscriptions are active?")["reply"]

    # Whole-business overview and price list.
    overview = _ask(client, "Give me a business overview")
    assert [c["tool"] for c in overview["tool_calls"]] == ["business_overview"]
    assert "outstanding" in overview["reply"]
    assert "starter" in _ask(client, "what are the price plans?")["reply"]

    # Unknown customer / unrelated question -> honest answer, never a made-up one.
    assert "No customer" in _ask(client, "tell me about Zzyzx Industries")["reply"] or "couldn't match" in _ask(client, "tell me about Zzyzx Industries")["reply"]
    assert "couldn't match" in _ask(client, "what's the weather?")["reply"]


def test_assistant_uses_real_workspace_data_too(client):
    headers = {"X-Tenant-Id": "TENANT_MINE", "X-Workspace-Type": "production"}
    client.post("/customers", json={"name": "Wayne Enterprises", "email": "a@wayne.example", "country": "US"}, headers=headers)
    reply = client.post("/ai/chat", json={"message": "how many customers do we have?", "context": {}}, headers=headers).json()
    assert ": 1" in reply["reply"]
    who = client.post("/ai/chat", json={"message": "tell me about wayne", "context": {}}, headers=headers).json()
    assert "Wayne Enterprises" in who["reply"]


def test_every_capability_listed_on_the_ai_page_works_from_chat(client):
    _seed_small_demo(client)
    ask = lambda t, ctx=None: _ask(client, t, ctx)  # noqa: E731

    # --- analysis examples quoted on the page ---
    assert "customer" in ask("top 5 customers by revenue")["reply"]
    plan_unpaid = ask("which plan has the most unpaid invoices?")
    assert plan_unpaid["tool_calls"][0]["tool"] == "analyze_data" and "by plan" in plan_unpaid["reply"]
    assert "by country" in ask("average invoice by country")["reply"]
    ai_usage = ask("how much AI usage did each plan have this month?")["reply"]
    assert "by plan" in ai_usage and "event_type=ai_tokens" in ai_usage and "month=" in ai_usage
    assert "no usage data" in ask("how much AI usage did each plan have last month?")["reply"].lower()

    # --- routine requests (run immediately) ---
    case = ask("Open a support case for Contoso about a billing dispute")
    assert case["tool_calls"] == [{"tool": "create_support_case", "status": "executed"}]
    assert "billing dispute" in case["reply"]
    contact = ask("Update Contoso's email to ap@contoso-new.example")
    assert contact["tool_calls"][0]["status"] == "executed" and "ap@contoso-new.example" in contact["reply"]
    country = ask("change Contoso country to Canada")
    assert "CA" in country["reply"]
    inv = ask("Generate an invoice for Umbrella Analytics")
    assert inv["tool_calls"][0]["tool"] == "generate_invoice"

    # --- protected changes: only ever become pending approvals ---
    for text, tool in [
        ("Pause Globex Corporation's subscription", "pause_subscription"),
        ("Move Contoso to the professional plan", "change_subscription_plan"),
    ]:
        r = ask(text)
        assert r["tool_calls"] == [{"tool": tool, "status": "pending_approval"}], (text, r)
        assert r["pending_approval_id"] and "NOT applied" in r["reply"]

    approvals = client.get("/ai/approvals", headers=DEMO_HEADERS).json()
    assert {a["tool"] for a in approvals} >= {"pause_subscription", "change_subscription_plan"}
    # Nothing was applied before approval: Globex is still active.
    globex = _analyze(client, dataset="subscriptions", group_by="customer", filters={"status": "paused"})
    assert not any(g["group"] == "Globex Corporation" for g in globex["results"])

    # Approving actually applies it, then reactivating works the same way.
    pause = next(a for a in approvals if a["tool"] == "pause_subscription")
    assert client.post(f"/ai/approvals/{pause['id']}/approve", headers=DEMO_HEADERS).status_code == 200
    paused = _analyze(client, dataset="subscriptions", group_by="customer", filters={"status": "paused"})
    assert any(g["group"] == "Globex Corporation" for g in paused["results"])
    assert ask("Resume Globex Corporation's subscription")["tool_calls"][0]["tool"] == "reactivate_subscription"

    # --- unclear requests ask instead of guessing ---
    assert "Which customer" in ask("open a support case")["reply"]
    assert "Which plan" in ask("upgrade Contoso")["reply"] or "Which plan" in ask("change Contoso plan")["reply"]


def test_why_did_this_invoice_increase_uses_the_open_invoices_context(client):
    _seed_small_demo(client)
    globex = client.get("/customers", headers=DEMO_HEADERS).json()
    gid = next(c["id"] for c in globex if c["name"] == "Globex Corporation")
    invoices = sorted(
        (i for i in client.get("/invoices", headers=DEMO_HEADERS).json() if i["customer_id"] == gid),
        key=lambda i: i["period_end"],
    )
    assert len(invoices) == 2
    reply = _ask(client, "Why did this invoice increase?", {"invoice_id": invoices[1]["id"]})
    assert [c["tool"] for c in reply["tool_calls"]] == ["get_customer", "compare_invoices", "get_usage_summary"]
    assert "higher" in reply["reply"]
