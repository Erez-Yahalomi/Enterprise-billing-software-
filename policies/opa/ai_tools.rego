package billing.ai

import future.keywords.if
import future.keywords.in

# Mirrors app/ai/policy.py's LocalPolicyEngine exactly, so the embedded fallback used in
# tests/dev and this real OPA sidecar (used in the docker-compose demo) enforce identical
# rules. This is the policy actually evaluated when OPA_MODE=http.

tier_rank := {"A": 0, "B": 1, "C": 2}

role_max_tier := {
	"support": "B",
	"billing": "C",
	"approver": "C",
	"admin": "C",
}

default allow := false

allow if {
	max_tier := role_max_tier[input.role]
	tier_rank[input.tier] <= tier_rank[max_tier]
}

default can_approve := false

can_approve if input.role in {"admin", "approver"}
