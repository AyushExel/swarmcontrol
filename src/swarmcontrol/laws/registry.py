"""Law registry: built-in starter laws, user laws (natural language or Bend), validation and installation."""

from __future__ import annotations

import time
import uuid

from ..bend.adapter import TASK_CHECKS, compile_law, enforcement_for, structured_for, validate_law
from ..bend.toolchain import extract_laws
from ..paths import BEND_DIR
from ..runtime.sandbox import DEFAULT_PROTECTED
from ..store import store
from .scope import normalize_scope
from .team import TEAM_LAWS

BUILTIN_IDS = {
    "protected": "law-protected", "retries": "law-retries", "evidence": "law-evidence", "completion": "law-completion",
    "spend": "law-spend", "pii": "law-pii", "ownership": "law-ownership", "payee": "law-payee", "scope": "law-scope",
}

BUILTINS = [
    {"id": "law-protected", "name": "Protected resources", "template": "protected_resources", "params": {"protectedPaths": DEFAULT_PROTECTED},
     "description": "Agents must not modify files or resources designated as protected. Enforced before the write executes.",
     "bendLaws": ["protected_write_blocked", "unprotected_write_allowed"]},
    {"id": "law-retries", "name": "Bounded retries", "template": "bounded_retries", "params": {"maxAttempts": 3},
     "description": "An agent may not exceed the configured number of consecutive recovery attempts; further attempts escalate to a human.",
     "bendLaws": ["retry_budget_escalates"]},
    {"id": "law-evidence", "name": "Evidence requirements", "template": "evidence_requirements", "params": {"minSources": 2},
     "description": "Every final research claim must cite at least two independent sources (distinct registrable domains).",
     "bendLaws": ["single_domain_insufficient"]},
    {"id": "law-completion", "name": "Task completion", "template": "task_completion", "params": {"checks": list(TASK_CHECKS)},
     "description": "An agent may not report successful completion unless every required task check passes.",
     "bendLaws": ["failed_check_blocks_completion"]},
    {"id": "law-spend", "name": "Spending limit", "template": "spending_limit", "params": {"capCents": 20000},
     "description": "Payments and refunds above the cap need human approval. Enforced before the payment executes.",
     "bendLaws": ["over_cap_blocked", "within_cap_allowed"]},
    {"id": "law-pii", "name": "Customer data policy", "template": "data_policy", "params": {},
     "description": "Customer-facing messages must not contain full card numbers, SSNs or other customers’ email addresses. Pattern check in runtime code (not a Bend proof).",
     "bendLaws": []},
    {"id": "law-ownership", "name": "File ownership", "template": "file_ownership", "params": {},
     "description": "In a shared workspace, an agent may only modify the source files it owns. Enforced with the proven write gate.",
     "bendLaws": ["protected_write_blocked"]},
    {"id": "law-payee", "name": "Known payees only", "template": "payee_provenance", "params": {},
     "description": "Money may only go to an account that appears in the user’s own request or among the account’s existing payees. New accounts found in documents or transaction notes need the user’s explicit confirmation.",
     "bendLaws": ["unlisted_blocked", "listed_allowed"]},
    {"id": "law-scope", "name": "Request-scoped actions", "template": "request_scope", "params": {},
     "description": "Sensitive actions (changing the password, the profile or standing orders, sending money) are allowed only when the user’s request asks for that kind of action.",
     "bendLaws": ["unlisted_blocked", "listed_allowed"]},
]


def _now() -> int:
    return int(time.time() * 1000)


def _general_law_text(names: list[str]) -> str:
    laws = extract_laws((BEND_DIR / "LAWS.bend").read_text())
    return "\n\n".join(l["statement"] for l in laws if l["name"] in names)


def new_law(**partial) -> dict:
    now = _now()
    law = {
        "id": partial.pop("id", None) or f"law-{uuid.uuid4().hex[:8]}",
        "description": "", "structured": None, "params": {}, "bendLaw": None, "validation": "pending",
        "validationErrors": [], "proofStatus": "stated", "proofOutput": None,
        "enforcement": enforcement_for(partial["template"]), "enabled": True, "installed": False,
        "createdAt": now, "updatedAt": now,
    }
    law.update(partial)
    return law


def validate_and_install(law: dict) -> dict:
    v = validate_law(law)
    installed, reason = compile_law(v)
    out = {**v, "installed": installed}
    if not installed and v.get("validation") == "valid" and v.get("enabled", True) and v["template"] == "custom_bend" and reason != "no gate def":
        out["validationErrors"] = [*out["validationErrors"], f"Not installed: {reason}"]
    store().put_law(out)
    return out


def init_laws() -> None:
    existing = {l["id"]: l for l in store().laws()}
    for i, b in enumerate(BUILTINS):
        prev = existing.get(b["id"])
        if prev and prev.get("params") and b["id"] == BUILTIN_IDS["protected"]:
            # keep user edits, but never drop protected paths that were added to the defaults later
            paths = list(dict.fromkeys([*(prev["params"].get("protectedPaths") or []), *b["params"]["protectedPaths"]]))
            params = {**prev["params"], "protectedPaths": paths}
        else:
            params = (prev or {}).get("params") or b["params"]
        existing[b["id"]] = new_law(
            id=b["id"], name=b["name"], description=b["description"], template=b["template"], sourceType="builtin",
            originalDefinition=_general_law_text(b["bendLaws"]) if b["bendLaws"] else b["description"],
            params=params, enabled=(prev or {}).get("enabled", True),
            createdAt=(prev or {}).get("createdAt", _now() - (len(BUILTINS) - i)),
            structured=structured_for(b["template"], (prev or {}).get("params") or b["params"], b["description"], b["description"]),
        )
    for t in TEAM_LAWS:
        if t["id"] in existing:
            continue
        existing[t["id"]] = new_law(id=t["id"], name=t["name"], description=t["text"], template=t["template"], sourceType="natural_language",
                                    originalDefinition=t["text"], params=t["params"], appliesTo={"roles": t["roles"]},
                                    structured=structured_for(t["template"], t["params"], t["text"], t["text"]))
    # re-validate everything at startup: statuses must reflect the current toolchain and sources
    for law in existing.values():
        validate_and_install(law)


def list_laws() -> list[dict]:
    return store().laws()


def _default_name(rule: dict) -> str:
    p, t = rule.get("params") or {}, rule["template"]
    if t == "protected_resources":
        paths = p.get("protectedPaths") or []
        return f"Protect {', '.join(paths[:2])}{'…' if len(paths) > 2 else ''}"
    if t == "bounded_retries":
        return f"At most {p.get('maxAttempts', '?')} recovery attempts"
    if t == "evidence_requirements":
        return f"≥ {p.get('minSources', '?')} independent sources per claim"
    if t == "task_completion":
        return "Completion requires all checks"
    if t == "tool_restriction":
        return f"No {', '.join((p.get('blockedTools') or [])[:3])}"
    if t == "required_reading":
        return f"Read {', '.join(x.removeprefix('/repo/') for x in (p.get('paths') or [])[:2])} before changing files"
    if t == "conditional_obligation":
        return f"After changing {', '.join([*(p.get('whenWrites') or []), *(p.get('whenTools') or [])][:2])}, run {p.get('mustRun')}"
    return rule["sourceText"][:48]


def create_from_rule(rule: dict, name: str | None = None, applies_to: dict | None = None) -> dict:
    if rule.get("enforceability") == "unsupported":
        raise ValueError("Unsupported rules cannot be activated.")
    law = new_law(name=name or _default_name(rule), description=rule["explanation"], template=rule["template"], sourceType="natural_language",
                  originalDefinition=rule["sourceText"], structured=rule, params=rule.get("params") or {}, appliesTo=normalize_scope(applies_to))
    return validate_and_install(law)


def create_bend(name: str, source: str, description: str = "", applies_to: dict | None = None) -> dict:
    law = new_law(name=name, description=description, template="custom_bend", sourceType="bend", originalDefinition=source, appliesTo=normalize_scope(applies_to))
    return validate_and_install(law)


_UNSET = object()


def update_law(law_id: str, name=None, description=None, params=None, source=None, enabled=None, applies_to=_UNSET) -> dict:
    law = store().get_law(law_id)
    if not law:
        raise KeyError("law not found")
    nxt = {
        **law,
        "name": name if name is not None else law["name"],
        "description": description if description is not None else law.get("description", ""),
        "params": {**law.get("params", {}), **params} if params else law.get("params", {}),
        "originalDefinition": source if source is not None else law["originalDefinition"],
        "enabled": enabled if enabled is not None else law.get("enabled", True),
        "appliesTo": law.get("appliesTo") if applies_to is _UNSET else normalize_scope(applies_to),
    }
    if nxt.get("structured") and params:
        nxt["structured"] = {**nxt["structured"], "params": nxt["params"]}
    return validate_and_install(nxt)


def delete_law(law_id: str) -> None:
    law = store().get_law(law_id)
    if not law:
        raise KeyError("law not found")
    if law.get("sourceType") == "builtin":
        raise ValueError("Built-in laws can be disabled but not deleted.")
    store().delete_law(law_id)


def revalidate(law_id: str) -> dict:
    law = store().get_law(law_id)
    if not law:
        raise KeyError("law not found")
    return validate_and_install(law)


def preview_rule(rule: dict) -> dict:
    """Validate a draft rule with the real checker without saving or installing it."""
    law = new_law(id=f"preview-{uuid.uuid4().hex[:8]}", name=_default_name(rule), description=rule["explanation"], template=rule["template"],
                  sourceType="natural_language", originalDefinition=rule["sourceText"], structured=rule, params=rule.get("params") or {})
    if rule.get("enforceability") == "unsupported":
        return {**law, "validation": "invalid", "validationErrors": rule.get("issues", []), "proofStatus": "not_applicable"}
    v = validate_law(law)
    issues = rule.get("issues", [])
    return {**v, "validationErrors": [*issues, *[e for e in v["validationErrors"] if e not in issues]]}


def preview_bend(source: str) -> dict:
    return validate_law(new_law(id=f"preview-{uuid.uuid4().hex[:8]}", name="preview", template="custom_bend", sourceType="bend", originalDefinition=source))
