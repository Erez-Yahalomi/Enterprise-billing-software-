from dataclasses import dataclass

from fastapi import Header


@dataclass
class ActorContext:
    user_id: str
    role: str


def get_actor_context(
    x_user_id: str = Header(default="demo-user"),
    x_user_role: str = Header(default="admin"),
) -> ActorContext:
    """Resolves the acting user. Phase 2/4 read this from headers so the API and AI
    guardrails can be built and tested without full auth. Phase 5 wires this to the
    logged-in user's id/role instead of trusting client-supplied headers."""
    return ActorContext(user_id=x_user_id, role=x_user_role)
