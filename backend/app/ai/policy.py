"""Authorization for AI tool calls.

Two backends, selected by settings.opa_mode:
- LocalPolicyEngine (default; used in tests/CI and local dev without the opa container):
  the identical rule set expressed in Python.
- OpaPolicyEngine (docker-compose demo): calls the real OPA sidecar so the architecture
  is genuinely demonstrated end-to-end. The Rego source is policies/opa/ai_tools.rego and
  encodes the same rules — Python here is the fallback, not a divergent implementation.

Either way, this is defense-in-depth *after* the tool gateway has already rejected any
tool name that isn't in TOOL_REGISTRY (Tier D tools don't exist at all).
"""

from abc import ABC, abstractmethod

import httpx

from app.core.config import get_settings

# Roles below tier A can only ever read; "support" cannot request protected changes.
ROLE_MAX_TIER = {
    "support": "B",
    "billing": "C",
    "approver": "C",
    "admin": "C",
}
TIER_ORDER = {"A": 0, "B": 1, "C": 2}


class PolicyEngine(ABC):
    @abstractmethod
    def is_allowed(self, *, tool: str, tier: str, role: str, tenant_id: str, workspace_type: str) -> bool: ...

    @abstractmethod
    def can_approve(self, *, role: str) -> bool: ...


class LocalPolicyEngine(PolicyEngine):
    def is_allowed(self, *, tool: str, tier: str, role: str, tenant_id: str, workspace_type: str) -> bool:
        max_tier = ROLE_MAX_TIER.get(role)
        if max_tier is None:
            return False
        return TIER_ORDER[tier] <= TIER_ORDER[max_tier]

    def can_approve(self, *, role: str) -> bool:
        return role in ("admin", "approver")


class OpaPolicyEngine(PolicyEngine):
    def is_allowed(self, *, tool: str, tier: str, role: str, tenant_id: str, workspace_type: str) -> bool:
        settings = get_settings()
        payload = {"input": {"tool": tool, "tier": tier, "role": role, "tenant_id": tenant_id, "workspace_type": workspace_type}}
        for _ in range(2):  # one retry absorbs a transient blip without weakening fail-closed
            try:
                response = httpx.post(f"{settings.opa_url}/v1/data/billing/ai/allow", json=payload, timeout=3.0)
                response.raise_for_status()
                return bool(response.json().get("result", False))
            except httpx.HTTPError:
                continue
        # Fail closed: if OPA stays unreachable, deny rather than silently falling back.
        return False

    def can_approve(self, *, role: str) -> bool:
        settings = get_settings()
        try:
            response = httpx.post(
                f"{settings.opa_url}/v1/data/billing/ai/can_approve",
                json={"input": {"role": role}},
                timeout=2.0,
            )
            response.raise_for_status()
            return bool(response.json().get("result", False))
        except httpx.HTTPError:
            return False


_local_engine = LocalPolicyEngine()
_opa_engine: OpaPolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    settings = get_settings()
    if settings.opa_mode == "http":
        global _opa_engine
        if _opa_engine is None:
            _opa_engine = OpaPolicyEngine()
        return _opa_engine
    return _local_engine
