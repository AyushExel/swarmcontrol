"""Who a law governs. No scope (or an empty one) = every agent. A role-scoped law governs agents with one of those
roles; an agent-scoped law governs the named agents. An agent can carry several names and roles: an attached
session's SC_AGENT, and a subagent's own type plus its parent's names and roles (laws inherit down to subagents)."""

from __future__ import annotations


def law_applies_to(law: dict, agent_ids: str | list[str], roles: str | list[str]) -> bool:
    s = law.get("appliesTo")
    if not s or (not s.get("roles") and not s.get("agents")):
        return True
    ids = [agent_ids] if isinstance(agent_ids, str) else agent_ids
    rs = [roles] if isinstance(roles, str) else roles
    return any(r in (s.get("roles") or []) for r in rs) or any(i in (s.get("agents") or []) for i in ids)


def normalize_scope(s: dict | None) -> dict | None:
    """Trim, de-duplicate and drop empty lists; an empty scope means a global law."""
    def clean(xs: list[str] | None) -> list[str]:
        return list(dict.fromkeys(x.strip() for x in xs or [] if x and x.strip()))

    roles, agents = clean((s or {}).get("roles")), clean((s or {}).get("agents"))
    if not roles and not agents:
        return None
    out: dict = {}
    if roles:
        out["roles"] = roles
    if agents:
        out["agents"] = agents
    return out
