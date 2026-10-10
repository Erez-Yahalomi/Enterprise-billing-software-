"""AI providers for the final natural-language reply.

Tool *selection* is always deterministic (see plan() below) regardless of provider —
that is the part that must be reliable and testable, so it is plain Python, not an LLM
call. Only the final phrasing of the answer varies by provider, and it is always grounded:
the prompt given to a real model contains nothing but the JSON facts the tools returned.

MockProvider is used automatically for all planning, and as the final fallback for
summarizing if the configured provider is unavailable (no API key, network error, Ollama
not running) — this is also what CI/tests use exclusively, so no network or paid API key
is ever required to run the test suite.
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.billing import service as billing_service
from app.core.actor import ActorContext
from app.core.config import get_settings
from app.core.tenancy import TenantContext
from app.customers import service as customers_service
from app.subscriptions import service as subscriptions_service

log = logging.getLogger("ai")

CHANGE_KEYWORDS = ("why", "compare", "increase", "change", "higher", "lower", "differ")
GENERATE_INVOICE_KEYWORDS = ("generate an invoice", "generate invoice", "create an invoice", "create invoice")
GENERATE_INVOICE_NAME_MARKERS = ("invoice to ", "invoice for ", "bill for ", "bill ")


def _current_month_bounds() -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    start = today.replace(day=1)
    end = date(start.year + 1, 1, 1) - timedelta(days=1) if start.month == 12 else date(start.year, start.month + 1, 1) - timedelta(days=1)
    return start, end


def _extract_customer_name(msg: str) -> str | None:
    for marker in GENERATE_INVOICE_NAME_MARKERS:
        idx = msg.find(marker)
        if idx != -1:
            fragment = msg[idx + len(marker):].strip().rstrip(".!?")
            if fragment:
                return fragment
    return None


def _plan_generate_invoice(db: Session, ctx: TenantContext, msg: str) -> list[tuple[str, dict]]:
    """Handles free-text requests like "generate an invoice to gadi" or "bill acme corp" —
    resolves a customer by (partial, case-insensitive) name to their active subscription,
    then calls the same generate_invoice tool the Invoices page's button uses."""
    name_fragment = _extract_customer_name(msg)
    if not name_fragment:
        return []
    customers = customers_service.list_customers(db, ctx.tenant_id, ctx.workspace_type)
    matches = [c for c in customers if name_fragment in c.name.lower()]
    if len(matches) != 1:
        return []
    customer = matches[0]
    active_subs = [
        s
        for s in subscriptions_service.list_subscriptions(db, ctx.tenant_id, ctx.workspace_type)
        if s.customer_id == customer.id and s.status == "active"
    ]
    if not active_subs:
        return []
    period_start, period_end = _current_month_bounds()
    return [
        (
            "generate_invoice",
            {
                "subscription_id": active_subs[0].id,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
        )
    ]


_STOP_TOKENS = {"corporation", "company", "demo", "inc", "ltd", "llc", "group", "analytics", "the", "and"}
_COUNTRY_NAMES = {
    "united states": "us", "usa": "us", "america": "us", "united kingdom": "gb", "britain": "gb", "uk": "gb",
    "england": "gb", "germany": "de", "france": "fr", "canada": "ca", "australia": "au", "india": "in", "brazil": "br",
}
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
_UNPAID_WORDS = ("unpaid", "open invoice", "outstanding", "overdue", "not paid", "owe", "owed", "due")


def _words(msg: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", msg))


def _find_customer_name(db: Session, ctx: TenantContext, msg: str) -> str | None:
    """Resolve a customer mentioned in free text to a name fragment: the longest full name that
    appears in the message, else a distinctive name word (e.g. "acme" -> ACME Corporation)."""
    numbered = re.search(r"demo company\s*0*(\d+)", msg)
    if numbered:
        return f"demo company {int(numbered.group(1)):05d}"
    names = [c.name.lower() for c in customers_service.list_customers(db, ctx.tenant_id, ctx.workspace_type)]
    full = [n for n in names if n in msg]
    if full:
        return max(full, key=len)
    msg_words = _words(msg)
    hits = {
        n for n in names
        if any(len(tok) >= 3 and tok not in _STOP_TOKENS and tok in msg_words for tok in re.findall(r"[a-z0-9]+", n))
    }
    if len(hits) == 1:
        return next(iter(hits))
    if 1 < len(hits) <= 10:  # ambiguous: let customer_overview list the candidates
        common = {tok for tok in re.findall(r"[a-z0-9]+", next(iter(hits))) if tok in msg_words and tok not in _STOP_TOKENS}
        return sorted(common)[0] if common else None
    return None


def _month_filter(msg: str) -> str | None:
    today = datetime.now(timezone.utc).date()
    explicit = re.search(r"\b(20\d\d)-(0[1-9]|1[0-2])\b", msg)
    if explicit:
        return f"{explicit.group(1)}-{explicit.group(2)}"
    if "this month" in msg or "current month" in msg:
        return today.strftime("%Y-%m")
    if "last month" in msg or "previous month" in msg:
        year, month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
        return f"{year}-{month:02d}"
    for i, name in enumerate(_MONTHS, start=1):
        if re.search(rf"\b{name}\b", msg):
            year = today.year if i <= today.month else today.year - 1
            year_hint = re.search(rf"{name}\s+(20\d\d)", msg)
            return f"{int(year_hint.group(1)) if year_hint else year}-{i:02d}"
    return None


def _country_filter(db: Session, ctx: TenantContext, msg: str) -> str | None:
    countries = {(c.country or "").lower() for c in customers_service.list_customers(db, ctx.tenant_id, ctx.workspace_type)}
    countries.discard("")
    msg_words = _words(msg)
    for phrase, code in _COUNTRY_NAMES.items():
        if code in countries and re.search(rf"\b{phrase}\b", msg):
            return code
    for code in countries:
        if len(code) == 2 and code in msg_words and re.search(rf"\b(in|from|for)\s+{code}\b", msg):
            return code
        if len(code) > 2 and code in msg:
            return code
    return None


def _plan_filter(db: Session, ctx: TenantContext, msg: str) -> str | None:
    from app.products import service as products_service

    msg_words = _words(msg)
    for p in products_service.list_price_plans(db, ctx.tenant_id, ctx.workspace_type):
        if p.name.lower() in msg_words:
            return p.name.lower()
    return None


def _plan_analysis(db: Session, ctx: TenantContext, msg: str) -> list[tuple[str, dict]]:
    """Deterministic coverage of analytical questions (used whenever Gemini isn't available,
    e.g. its free quota is spent). Builds one bounded analyze_data request from the question's
    dataset, metric, grouping and filters, so any phrasing that names those gets a correct answer.
    With Gemini the model composes the same requests itself."""
    words = _words(msg)
    top = re.search(r"\b(?:top|best|biggest|largest|highest|first)\s+(\d+)", msg)
    top_n = int(top.group(1)) if top else 5
    ranking = bool(top) or any(w in msg for w in ("which customer", "who ", "top ", "biggest", "largest", "highest", "most ", "lowest", "smallest", "least "))
    ascending = any(w in msg for w in ("lowest", "smallest", "least ", "fewest", "bottom"))

    # ---- dataset ----
    filters: dict = {}
    if "payment" in msg or "paid" in words and "invoice" not in msg:
        dataset, field = "payments", "amount_cents"
        if "fail" in msg or "declin" in msg:
            filters["status"] = "failed"
        elif "success" in msg or "succeeded" in msg or "paid" in words:
            filters["status"] = "succeeded"
        elif "pending" in msg:
            filters["status"] = "pending"
    elif any(w in msg for w in _UNPAID_WORDS) or "invoice" in msg or any(
        w in msg for w in ("revenue", "spend", "spent", "billed", "billing", "invoiced", "sales", "earn", "income", "money")
    ):
        dataset, field = "invoices", "subtotal_cents"
        if any(w in msg for w in _UNPAID_WORDS):
            filters["status"] = "finalized"
        elif "paid" in words:
            filters["status"] = "paid"
        elif "draft" in words:
            filters["status"] = "draft"
        elif "void" in words:
            filters["status"] = "void"
    elif any(w in msg for w in ("usage", "token", "api", "storage", "consum")):
        dataset, field = "usage", "total_quantity"
        for key, event in (("token", "ai_tokens"), ("api", "api_request"), ("storage", "storage_gb")):
            if key in msg:
                filters["event_type"] = event
                break
    elif "subscription" in msg or "plan" in words or "plans" in words or "seat" in msg or "users" in words:
        dataset, field = "subscriptions", "quantity_users"
        for status in ("active", "trialing", "paused", "canceled", "cancelled"):
            if status in words:
                filters["status"] = status
                break
    elif "customer" in msg or "client" in msg or "compan" in msg:
        dataset, field = "customers", None
    else:
        return []

    # ---- metric ----
    metric = "count"
    if any(w in msg for w in ("average", "avg", "mean")):
        metric = "avg"
    elif field and any(w in msg for w in ("how much", "total", "sum", "revenue", "spend", "spent", "billed", "worth", "amount", "usage", "tokens", "seats", "in all", "overall", "outstanding", "owe", "owed")):
        metric = "sum"
    elif field and any(w in msg for w in ("largest", "biggest", "highest", "max")) and not ranking:
        metric = "max"
    elif field and any(w in msg for w in ("smallest", "lowest", "min")) and not ranking:
        metric = "min"
    if dataset == "usage" and metric == "count":
        metric = "sum"
    if dataset == "subscriptions" and "seat" in msg or (dataset == "subscriptions" and "users" in words):
        metric = "sum" if metric == "count" else metric
    elif dataset == "subscriptions" and metric != "avg":
        metric, field = "count", None
    if ranking and dataset in ("invoices", "payments") and metric == "count" and "how many" not in msg:
        metric = "sum"
    if metric == "count":
        field = None

    # ---- grouping ----
    group_by = None
    explicit = re.search(r"\b(?:by|per|each|every|across|for each)\s+(customer|plan|month|country|status|type|event type)", msg)
    if explicit:
        group_by = {"type": "event_type", "event type": "event_type"}.get(explicit.group(1), explicit.group(1))
    elif ranking and dataset != "customers":
        group_by = "customer"
    elif ranking and dataset == "customers":
        group_by = "country"
    elif any(w in msg for w in ("distribution", "breakdown", "split")):
        group_by = {"subscriptions": "plan", "usage": "event_type"}.get(dataset, "status")
    elif "monthly" in msg or "trend" in msg:
        group_by = "month"
    elif dataset == "usage" and "api" not in msg and "token" not in msg and "storage" not in msg and metric == "sum" and "customer" in msg:
        group_by = "customer"
    valid = {
        "customers": ("country", "status"), "subscriptions": ("plan", "status", "customer", "country"),
        "invoices": ("customer", "status", "plan", "month", "country"), "payments": ("customer", "status", "month", "country"),
        "usage": ("event_type", "customer", "plan", "month", "country"),
    }[dataset]
    if group_by not in valid:
        group_by = None
    if group_by == "status" and "status" in filters:
        filters.pop("status")  # asked for the split; don't pre-filter to one status

    # ---- extra filters ----
    month = _month_filter(msg)
    if month and dataset in ("invoices", "payments", "usage") and group_by != "month":
        filters["month"] = month
    country = _country_filter(db, ctx, msg)
    if country and group_by != "country":
        filters["country"] = country
    plan_name = _plan_filter(db, ctx, msg) if dataset != "customers" else None
    if plan_name and group_by != "plan" and dataset in ("subscriptions", "invoices", "usage"):
        filters["plan"] = plan_name

    params = {"dataset": dataset, "metric": metric, "filters": filters, "top_n": top_n if group_by else 10}
    if field:
        params["field"] = field
    if group_by:
        params["group_by"] = group_by
    if ascending:
        params["order"] = "asc"
    return [("analyze_data", params)]


def _plan_lookup(db: Session, ctx: TenantContext, msg: str, context: dict) -> list[tuple[str, dict]]:
    """Questions about one named customer, the price list, or the business as a whole."""
    aggregate_hint = any(w in msg for w in ("top ", "which customer", "how many customers", "all customers", "each customer", "per customer", "by customer", "average", "in total", "overall"))
    name = None if aggregate_hint else _find_customer_name(db, ctx, msg)
    if name:
        return [("customer_overview", {"name_contains": name})]
    if not aggregate_hint and context.get("customer_id") and any(w in msg for w in ("this customer", "they", "their", "them", "he ", "she ", "summar", "overview", "tell me about")):
        return [("customer_overview", {"customer_id": context["customer_id"]})]
    if any(w in msg for w in ("price plan", "pricing", "plans cost", "plan cost", "what plans", "which plans", "available plans", "list plans", "list the plans", "plan prices", "how much is the")) and "subscri" not in msg:
        return [("list_price_plans", {})]
    if any(w in msg for w in ("overview", "summary", "summarize", "summarise", "how is the business", "how are we doing", "state of", "kpi", "dashboard", "snapshot", "health of")):
        return [("business_overview", {})]
    return []

def plan(db: Session, ctx: TenantContext, actor: ActorContext, message: str, context: dict) -> list[tuple[str, dict]]:
    """Deterministic tool-selection. See module docstring for why this isn't LLM-driven."""
    msg = message.lower()
    invoice_id = context.get("invoice_id")
    subscription_id = context.get("subscription_id")
    customer_id = context.get("customer_id")
    calls: list[tuple[str, dict]] = []

    if any(k in msg for k in GENERATE_INVOICE_KEYWORDS):
        invoice_calls = _plan_generate_invoice(db, ctx, msg)
        if invoice_calls:
            return invoice_calls

    if invoice_id and any(k in msg for k in CHANGE_KEYWORDS):
        try:
            invoice = billing_service.get_invoice(db, ctx.tenant_id, ctx.workspace_type, invoice_id)
        except HTTPException:
            return calls
        siblings = [
            inv
            for inv in billing_service.list_invoices(db, ctx.tenant_id, ctx.workspace_type)
            if inv.subscription_id == invoice.subscription_id and inv.period_end < invoice.period_start
        ]
        siblings.sort(key=lambda inv: inv.period_end, reverse=True)
        if siblings:
            previous = siblings[0]
            calls.append(("get_customer", {"customer_id": invoice.customer_id}))
            calls.append(("compare_invoices", {"invoice_id_a": previous.id, "invoice_id_b": invoice.id}))
            calls.append(
                (
                    "get_usage_summary",
                    {
                        "subscription_id": invoice.subscription_id,
                        "period_start": invoice.period_start.isoformat(),
                        "period_end": invoice.period_end.isoformat(),
                    },
                )
            )
            return calls
        calls.append(("get_invoice", {"invoice_id": invoice_id}))
        return calls

    lookup_calls = _plan_lookup(db, ctx, msg, context)
    if lookup_calls:
        return lookup_calls
\n    analysis_calls = _plan_analysis(db, ctx, msg)
    if analysis_calls:
        return analysis_calls

    if invoice_id:
        calls.append(("get_invoice", {"invoice_id": invoice_id}))
    elif subscription_id:
        calls.append(("get_subscription", {"subscription_id": subscription_id}))
    elif customer_id:
        calls.append(("get_customer", {"customer_id": customer_id}))
    return calls


class SummaryProvider(ABC):
    @abstractmethod
    def summarize(self, message: str, context: dict, tool_results: list[dict]) -> str: ...


def _grounding_json(tool_results: list[dict]) -> str:
    payload = [
        {"tool": r["tool"], "status": r["result"].status, "data": r["result"].data} for r in tool_results
    ]
    return json.dumps(payload, default=str)


class MockProvider(SummaryProvider):
    """Deterministic, template-based. No network calls — safe for tests/CI."""

    def summarize(self, message: str, context: dict, tool_results: list[dict]) -> str:
        by_tool = {r["tool"]: r["result"] for r in tool_results}

        if "compare_invoices" in by_tool and by_tool["compare_invoices"].data:
            cmp = by_tool["compare_invoices"].data
            diff = cmp["total_diff_cents"]
            direction = "higher" if diff > 0 else "lower" if diff < 0 else "the same as"
            changed = [d for d in cmp["line_item_diffs"] if d["diff_cents"] != 0]
            lines = [f"{d['kind']} {'+' if d['diff_cents'] >= 0 else ''}${d['diff_cents'] / 100:.2f}" for d in changed]
            detail = ("Main differences: " + "; ".join(lines)) if lines else ""
            return f"This invoice is ${abs(diff) / 100:.2f} {direction} the previous one. {detail}".strip()

        if "analyze_data" in by_tool and by_tool["analyze_data"].data:
            data = by_tool["analyze_data"].data
            if "error" in data:
                return f"I couldn't run that analysis: {data['error']}"
            unit_money = "value_dollars" in (data["results"][0] if data["results"] else {})
            lines = []
            for g in data["results"]:
                value = f"${g['value_dollars']:,.2f}" if unit_money else f"{g['value']:,.0f}" if float(g["value"]).is_integer() else f"{g['value']:,.2f}"
                lines.append(f"{g['group']}: {value}")
            label = f"{data['metric']} of {data['field']}" if data["field"] else "count"
            head = f"{data['dataset']} ({label}" + (f" by {data['group_by']}" if data["group_by"] else "") + f", {data['rows_considered']} rows considered)"
            return head + ": " + "; ".join(lines) if lines else head + ": no matching data."

        if not tool_results:
            return "I don't have enough context to answer that yet — open a customer, subscription, or invoice first."

        first = tool_results[0]["result"]
        if first.status == "pending_approval":
            return "That action changes billing terms, so I've submitted it for approval before it takes effect."
        return f"Here's what I found: {json.dumps(first.data, default=str)}"


class GeminiProvider(SummaryProvider):
    def summarize(self, message: str, context: dict, tool_results: list[dict]) -> str:
        import google.generativeai as genai

        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        prompt = (
            "You are a billing assistant. Answer the user's question using ONLY the JSON facts "
            "below; never invent numbers that aren't present in them.\n\n"
            f"Question: {message}\n\nFacts:\n{_grounding_json(tool_results)}"
        )
        response = model.generate_content(prompt)
        return response.text


class OllamaProvider(SummaryProvider):
    def summarize(self, message: str, context: dict, tool_results: list[dict]) -> str:
        settings = get_settings()
        prompt = (
            "You are a billing assistant. Answer the user's question using ONLY the JSON facts "
            "below; never invent numbers that aren't present in them.\n\n"
            f"Question: {message}\n\nFacts:\n{_grounding_json(tool_results)}"
        )
        response = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            # keep_alive here too: belt-and-suspenders alongside OLLAMA_KEEP_ALIVE on the
            # container, in case that env var isn't picked up in some deployment.
            json={"model": settings.ollama_model, "prompt": prompt, "stream": False, "keep_alive": -1},
            # A cold model load can take 60-100s on CPU; a warm one answers in a couple of
            # seconds. 180s covers the worst case without hanging the UI forever.
            timeout=180.0,
        )
        response.raise_for_status()
        return response.json()["response"]


_PROVIDER_CHAINS = {
    "gemini": [GeminiProvider, OllamaProvider, MockProvider],
    "ollama": [OllamaProvider, MockProvider],
    "mock": [MockProvider],
}


def summarize_with_fallback(message: str, context: dict, tool_results: list[dict]) -> str:
    settings = get_settings()
    chain = _PROVIDER_CHAINS.get(settings.ai_provider, [MockProvider])
    for provider_cls in chain:
        try:
            return provider_cls().summarize(message, context, tool_results)
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any provider failure falls back
            log.warning("AI provider %s failed (%s), falling back", provider_cls.__name__, exc)
            continue
    return MockProvider().summarize(message, context, tool_results)
