"""Law adapter: the boundary between law definitions and runtime enforcement.

    validate_law(law)                    -> runs the real Bend checker
    compile_law(law)                     -> installs a runtime gate when one exists
    evaluate_checkpoint(law, cp, ctx)    -> LawEvaluation (fails closed on error)
    explain_violation(law, cp, ev)       -> corrective feedback for the agent

These are application-level interfaces, not Bend APIs. The deterministic gate functions themselves are Bend code
(bend/governor.bend), compiled into a native program the runtime calls.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from ..paths import BEND_DIR
from ..runtime.sandbox import CATALOG, ResourceRegistry, is_protected
from . import gates as G
from .toolchain import build_program, classify, find_bend, run_bend, sha, top_level_blocks, workspace

TASK_CHECKS = ["findings_min", "evidence_ok", "notes_written", "within_constraints", "no_protected_writes"]
# checks computed by CI for software tasks (e.g. a held-out acceptance suite the agent cannot see)
CI_CHECKS = ["acceptance_suite"]
CHECK_LABELS = {
    "findings_min": "At least 2 accepted findings",
    "evidence_ok": "Every finding has ≥ 2 independent sources",
    "notes_written": "Working notes written to own workspace",
    "within_constraints": "Findings ≤ 60 words and on-topic",
    "no_protected_writes": "No protected resource modified",
}

# A checkpoint is a dict with a "kind":
#   write {path, owned?, universe?} · spend {amountCents, what} · message {text, allowedEmails}
#   allow {scope: payee|capability, item, allowed, what, source} · retry {attempts, max, reason}
#   tool {tool} · obligation {lawId, met, trigger, obligation} · claim {sources} · complete {checks, required?}
Checkpoint = dict[str, Any]


@dataclass
class EvalContext:
    resources: ResourceRegistry
    domain_id: Callable[[str], int]


def registrable_domain(host: str) -> str:
    """Two sources are independent iff their registrable domains differ, approximated as the last two hostname
    labels (no public-suffix list): blog.x.example and x.example count once. Syndication is NOT detected."""
    return ".".join([p for p in host.lower().split(".") if p][-2:])


def applies(law: dict, cp: Checkpoint) -> bool:
    """Does this law have anything to say at this checkpoint?"""
    k, t = cp["kind"], law["template"]
    return {
        "protected_resources": k == "write",
        "bounded_retries": k == "retry",
        "evidence_requirements": k == "claim",
        "task_completion": k == "complete",
        "spending_limit": k == "spend",
        "data_policy": k == "message",
        "file_ownership": k == "write" and bool(cp.get("owned") is not None and cp.get("universe") is not None),
        "payee_provenance": k == "allow" and cp.get("scope") == "payee",
        "request_scope": k == "allow" and cp.get("scope") == "capability",
        "tool_restriction": k == "tool",
        "conditional_obligation": k == "obligation" and cp.get("lawId") == law["id"],
        "custom_bend": law["id"] in G.custom_gates,
    }.get(t, False)


def find_sensitive(text: str, allowed_emails: list[str]) -> list[str]:
    """Sensitive data a customer-facing message must not contain (deterministic; not a Bend gate)."""
    hits = []
    for m in re.finditer(r"\b(?:\d[ -]?){13,19}\b", text):
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) >= 13:
            hits.append(f"card-like number ending {digits[-4:]}")
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text):
        hits.append("SSN-like number")
    for m in re.finditer(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text):
        if m.group(0).lower() not in allowed_emails:
            hits.append(f"email {m.group(0)}")
    return hits


def _money(cents: int) -> str:
    return f"${cents / 100:.2f}"


def evaluate_checkpoint(law: dict, cp: Checkpoint, ctx: EvalContext) -> dict | None:
    """Evaluate one law at one checkpoint. Any failure to evaluate (missing gate program, error, missing metadata)
    yields result 'error' with decision 'block': an evaluator problem is never treated as permission."""
    if not applies(law, cp):
        return None
    t0 = time.perf_counter()

    def done(**e: Any) -> dict:
        return {"lawId": law["id"], "lawName": law["name"], **e, "micros": max(1, round((time.perf_counter() - t0) * 1e6))}

    def fail(inp: str, why: str) -> dict:
        ev = "bend_custom" if law["template"] == "custom_bend" else "bend"
        return done(evaluator=ev, input=inp, result="error", decision="block", detail=f"Evaluation failed closed: {why}")

    def verdict(d: str) -> str:
        return "pass" if d == "allow" else "violation"

    params = law.get("params") or {}
    kind = cp["kind"]

    if law["template"] == "custom_bend":
        arg = _custom_arg(cp, ctx)
        if not arg:
            return None
        try:
            d = G.custom_gates[law["id"]](arg[0], arg[1])
            return done(evaluator="bend_custom", input=arg[2], result=verdict(d), decision=d, detail=f"gate({arg[2]}) = {d}")
        except Exception as e:  # noqa: BLE001 - fail closed on anything
            return fail(arg[2], str(e))

    if law["template"] == "data_policy" and kind == "message":
        hits = find_sensitive(cp["text"], cp["allowedEmails"])
        return done(evaluator="app", input=f"scan(message, {len(cp['text'])} chars)", result="violation" if hits else "pass",
                    decision="block" if hits else "allow",
                    detail=f"message contains {', '.join(hits)}" if hits else "no card numbers, SSNs or third-party emails")

    core, core_error = G.core()
    missing = core_error or "governor gates not loaded"
    try:
        if kind == "spend":
            cap = params.get("capCents", 20000)
            inp = f"spend_gate({cp['amountCents']}n, {cap}n)"
            if not core:
                return fail(inp, missing)
            amt = cp["amountCents"]
            if not isinstance(amt, int) or amt < 0:
                return fail(inp, f"invalid amount {amt}")
            d = core.spend_gate(amt, cap)
            return done(evaluator="bend", input=inp, result=verdict(d), decision=d,
                        detail=f"{cp['what']}: {_money(amt)} within the {_money(cap)} cap" if d == "allow"
                        else f"{cp['what']}: {_money(amt)} exceeds the {_money(cap)} cap; needs approval")
        if kind == "message":
            return None
        if kind == "allow":
            norm = lambda x: x.strip().lower()  # noqa: E731
            r = ctx.resources.id(f"allow:{norm(cp['item'])}")
            xs = sorted({ctx.resources.id(f"allow:{norm(x)}") for x in cp["allowed"]})
            inp = f"allow_gate({r}n, [{len(xs)} allowlisted ids])"
            if not core:
                return fail(inp, missing)
            d = core.allow_gate(r, xs)
            return done(evaluator="bend", input=inp, result=verdict(d), decision=d,
                        detail=f"{cp['what']}: \"{cp['item']}\" is allowed ({cp['source']})" if d == "allow"
                        else f"{cp['what']}: \"{cp['item']}\" is not in {cp['source']}")
        if kind == "write":
            path = cp["path"]
            r = ctx.resources.id(path)
            if law["template"] == "file_ownership":
                # protected for this agent = every workspace file it does not own (proven write_gate)
                owned = cp.get("owned") or []
                others = [p for p in dict.fromkeys([*(cp.get("universe") or []), path]) if p not in owned and p.startswith("/repo/src/")]
                ps = sorted(ctx.resources.id(p) for p in others)
                inp = f"write_gate({r}n, [{len(ps)} ids not owned by this agent])"
                if not core:
                    return fail(inp, missing)
                d = core.write_gate(r, ps)
                return done(evaluator="bend", input=inp, result=verdict(d), decision=d,
                            detail=f"{path} is owned by this agent or outside src/" if d == "allow" else f"{path} is owned by another agent or the platform team")
            ps = ctx.resources.protected_ids(params.get("protectedPaths") or [], path)
            inp = f"write_gate({r}n, [{', '.join(f'{p}n' for p in ps)}])"
            if not core:
                return fail(inp, missing)
            d = core.write_gate(r, ps)
            return done(evaluator="bend", input=inp, result=verdict(d), decision=d,
                        detail=f"{path} is not protected" if d == "allow" else f"{path} (resource {r}) is protected")
        if kind == "tool":
            # restricted tools are a protected set of tool ids: the same proven write_gate (listed -> Block)
            norm = lambda x: x.strip().lower()  # noqa: E731
            tool = norm(cp["tool"])
            listed = [norm(t) for t in params.get("blockedTools") or []]
            hit = any(t == tool or (t.endswith("*") and tool.startswith(t[:-1])) for t in listed)
            r = ctx.resources.id(f"tool:{tool}")
            ps = sorted({*(ctx.resources.id(f"tool:{t}") for t in listed if not t.endswith("*")), *([r] if hit else [])})
            inp = f"write_gate({r}n, [{len(ps)} restricted tool ids])"
            if not core:
                return fail(inp, missing)
            d = core.write_gate(r, ps)
            return done(evaluator="bend", input=inp, result=verdict(d), decision=d,
                        detail=f"{cp['tool']} is allowed for this agent" if d == "allow" else f"{cp['tool']} is a restricted tool for this agent")
        if kind == "obligation":
            # the obligation is one required check: the proven completion gate blocks finishing while it is unmet
            inp = f"completion_gate([{'True{}' if cp['met'] else 'False{}'}])"
            if not core:
                return fail(inp, missing)
            d = core.completion_gate([cp["met"]])
            trig = re.sub(r"^You ", "", cp["trigger"])
            return done(evaluator="bend", input=inp, result=verdict(d), decision=d,
                        detail=f"{cp['obligation']} ran after the agent {trig}" if cp["met"] else f"{cp['trigger']}, but {cp['obligation']} has not run since")
        if kind == "retry":
            maximum = params.get("maxAttempts", cp["max"])
            inp = f"retry_gate({cp['attempts']}n, {maximum}n)"
            if not core:
                return fail(inp, missing)
            d = core.retry_gate(cp["attempts"], maximum)
            return done(evaluator="bend", input=inp, result=verdict(d), decision=d,
                        detail=f"{cp['attempts']}/{maximum} attempts used ({cp['reason']})" if d == "allow"
                        else f"budget exhausted: {cp['attempts']}/{maximum} attempts ({cp['reason']})")
        if kind == "claim":
            minimum = params.get("minSources", 2)
            missing_meta = [s for s in cp["sources"] if not s.get("domain")]
            domains = [registrable_domain(s["domain"]) for s in cp["sources"] if s.get("domain")]
            ids = [ctx.domain_id(d) for d in domains]
            inp = f"evidence_gate({minimum}n, [{', '.join(f'{i}n' for i in ids)}])"
            if missing_meta:
                return fail(inp, f"source {', '.join(s['id'] for s in missing_meta)} has no domain metadata, so independence cannot be determined")
            if not core:
                return fail(inp, missing)
            d = core.evidence_gate(minimum, ids)
            uniq = list(dict.fromkeys(domains))
            return done(evaluator="bend", input=inp, result=verdict(d), decision=d,
                        detail=f"{len(uniq)} independent domain{'' if len(uniq) == 1 else 's'} ({', '.join(uniq) or 'none'}); {minimum} required")
        if kind == "complete":
            # a scenario may define its own checklist; otherwise the law's configured checks
            required = list(cp.get("required") or params.get("checks") or TASK_CHECKS)
            vals = [cp["checks"].get(c) is True for c in required]
            inp = f"completion_gate([{', '.join('True{}' if v else 'False{}' for v in vals)}])"
            if not core:
                return fail(inp, missing)
            d = core.completion_gate(vals)
            failed = [c for c, v in zip(required, vals) if not v]
            return done(evaluator="bend", input=inp, result=verdict(d), decision=d,
                        detail=f"failed checks: {', '.join(failed)}" if failed else f"all {len(required)} required checks passed")
    except Exception as e:  # noqa: BLE001 - fail closed on anything
        return fail(kind, str(e))
    return None


def _custom_arg(cp: Checkpoint, ctx: EvalContext) -> tuple[str, str, str] | None:
    """(kind, argument, label) for a custom gate, or None when the gate has nothing to say here."""
    k = cp["kind"]
    if k == "write":
        r = ctx.resources.id(cp["path"])
        return ("write", str(r), f"Write{{{r}n}}")
    if k == "retry":
        return ("retry", str(cp["attempts"]), f"Retry{{{cp['attempts']}n}}")
    if k == "claim":
        if any(not s.get("domain") for s in cp["sources"]):
            return None
        ids = [ctx.domain_id(registrable_domain(s["domain"])) for s in cp["sources"]]
        return ("claim", ",".join(map(str, ids)) or "-", f"Claim{{[{', '.join(map(str, ids))}]}}")
    if k == "complete":
        vals = [cp["checks"].get(c) is True for c in (cp.get("required") or TASK_CHECKS)]
        return ("complete", ",".join("1" if v else "0" for v in vals) or "-", f"Complete{{[{', '.join('true' if v else 'false' for v in vals)}]}}")
    return None


def explain_violation(law: dict, cp: Checkpoint, ev: dict, own_notes: str) -> str:
    """Corrective, actionable feedback: tells the agent what to do, not just "retry"."""
    if ev["result"] == "error":
        return f"{law['name']} could not be evaluated ({ev['detail']}). The action was not executed."
    d, k = ev["detail"], cp["kind"]
    return {
        "allow": f"{d}. The action was not executed; ask the user to confirm it explicitly.",
        "obligation": f"{d}. Do it now, fix anything it reports, then finish.",
        "tool": f"{d}. The call was not executed; do this step with the tools you are allowed to use, or hand it to an agent that may use this tool.",
        "spend": f"{d}. The payment was not made. Escalate to a human approver instead.",
        "message": f"Message not sent: {d}. Remove sensitive data (use only the last 4 digits of a card) and send again.",
        "write": f"Write to {cp.get('path')} denied: it is a protected resource under \"{law['name']}\". The file was not modified. Write your output to your own workspace ({own_notes}) instead.",
        "retry": f"Recovery budget exhausted ({d}). Stop and wait for a human decision.",
        "claim": f"Claim not accepted: {d}. Gather supporting evidence from a different publisher (a different registrable domain) and resubmit; subdomains of the same publisher do not count as independent.",
        "complete": f"Completion blocked: {d}. Resolve each failed check before reporting completion.",
    }[k]


# ---------------------------------------------------------------------------
# Bend source for a law (instance laws over the proven general laws)

_HEADER = "import Base\nimport ./governor.bend as G\nimport ./LAWS.bend as L\nimport ./PROOF.bend as P\n"


def _n(x: int) -> str:
    return f"{x}n"


def bend_instance_source(template: str, params: dict) -> str | None:
    """Bend law statements + proofs instantiating the general laws with this law's parameters."""
    h = _HEADER
    if template == "protected_resources":
        reg = ResourceRegistry()
        prefixes = params.get("protectedPaths") or []
        ids = reg.protected_ids(prefixes)
        lst = f"[{', '.join(map(_n, ids))}]"
        blocks = []
        for r in CATALOG:
            if not is_protected(r["path"], prefixes):
                continue
            i = reg.id(r["path"])
            blocks.append(f"# {r['path']} is resource {i}\nlaw protected_{i}:\n  {{G.write_gate({_n(i)}, {lst}) == G.Block{{}} : G.Decision}}\n\ndef protected_{i}():\n  L.protected_write_blocked({_n(i)}, {lst}, {{==}})\n")
        free = next((r for r in CATALOG if not is_protected(r["path"], prefixes)), None)
        if free:
            i = reg.id(free["path"])
            blocks.append(f"# {free['path']} (resource {i}) is not protected: the gate must not over-block\nlaw unprotected_{i}:\n  {{G.write_gate({_n(i)}, {lst}) == G.Allow{{}} : G.Decision}}\n\ndef unprotected_{i}():\n  L.unprotected_write_allowed({_n(i)}, {lst}, {{==}})\n")
        return f"{h}\n" + "\n".join(blocks)
    if template == "bounded_retries":
        m = params.get("maxAttempts", 3)
        return f"{h}\n# after {m} attempts, every further attempt escalates\nlaw retry_budget_{m}:\n  for k: Nat\n  {{G.retry_gate(Nat.add({_n(m)}, k), {_n(m)}) == G.Escalate{{}} : G.Decision}}\n\ndef retry_budget_{m}(k):\n  L.retry_budget_escalates({_n(m)}, k)\n"
    if template == "evidence_requirements":
        m = params.get("minSources", 2)
        if m < 2:
            return None  # the single-domain property is false for min < 2
        return f"{h}\n# any number of citations from one domain never meets a minimum of {m}\nlaw evidence_min_{m}:\n  for d: Nat\n  for n: Nat\n  {{G.evidence_gate({_n(m)}, List.replicate(Nat, 1n+n, d)) == G.Block{{}} : G.Decision}}\n\ndef evidence_min_{m}(d, n):\n  L.single_domain_insufficient(d, n, {_n(m - 2)})\n"
    if template == "spending_limit":
        c = params.get("capCents", 20000)
        return f"{h}\n# every amount above {c} cents is blocked; every amount up to it is allowed\nlaw over_cap_{c}:\n  for k: Nat\n  {{G.spend_gate(Nat.add({_n(c)}, 1n+k), {_n(c)}) == G.Block{{}} : G.Decision}}\n\ndef over_cap_{c}(k):\n  L.over_cap_blocked({_n(c)}, k)\n\nlaw within_cap_{c}:\n  for k: Nat\n  {{G.spend_gate({_n(c)}, Nat.add({_n(c)}, k)) == G.Allow{{}} : G.Decision}}\n\ndef within_cap_{c}(k):\n  L.within_cap_allowed({_n(c)}, k)\n"
    if template in ("payee_provenance", "request_scope"):
        return f"{h}\n# an item outside the allowlist is blocked; an allowlisted one never is\nlaw allowlist_enforced:\n  for r: Nat\n  for xs: List<&2, Nat>\n  for e: {{G.elem(r, xs) == False{{}} : Bool}}\n  {{G.allow_gate(r, xs) == G.Block{{}} : G.Decision}}\n\ndef allowlist_enforced(r, xs, e):\n  L.unlisted_blocked(r, xs, e)\n\nlaw allowlist_permits:\n  for r: Nat\n  for xs: List<&2, Nat>\n  for e: {{G.elem(r, xs) == True{{}} : Bool}}\n  {{G.allow_gate(r, xs) == G.Allow{{}} : G.Decision}}\n\ndef allowlist_permits(r, xs, e):\n  L.listed_allowed(r, xs, e)\n"
    if template == "conditional_obligation":
        return f"{h}\n# while the obligation is unmet (one failed check), finishing is blocked\nlaw obligation_blocks_completion:\n  for pre: List<&2, Bool>\n  for post: List<&2, Bool>\n  {{G.completion_gate(List.append(&2, Bool, pre, False{{}} <> post)) == G.Block{{}} : G.Decision}}\n\ndef obligation_blocks_completion(pre, post):\n  L.failed_check_blocks_completion(pre, post)\n"
    if template == "tool_restriction":
        return f"{h}\n# a call to a restricted tool is blocked (restricted tools are a protected set; same proven gate as protected resources)\nlaw restricted_tool_blocked:\n  for r: Nat\n  for ts: List<&2, Nat>\n  for e: {{G.elem(r, ts) == True{{}} : Bool}}\n  {{G.write_gate(r, ts) == G.Block{{}} : G.Decision}}\n\ndef restricted_tool_blocked(r, ts, e):\n  L.protected_write_blocked(r, ts, e)\n"
    if template == "file_ownership":
        return f"{h}\n# writes to a file outside the agent's owned set are blocked (same proven gate as protected resources)\nlaw ownership_enforced:\n  for r: Nat\n  for others: List<&2, Nat>\n  for e: {{G.elem(r, others) == True{{}} : Bool}}\n  {{G.write_gate(r, others) == G.Block{{}} : G.Decision}}\n\ndef ownership_enforced(r, others, e):\n  L.protected_write_blocked(r, others, e)\n"
    if template == "task_completion":
        return f"{h}\n# one failed check anywhere in the checklist blocks completion\nlaw completion_requires_all_checks:\n  for pre: List<&2, Bool>\n  for post: List<&2, Bool>\n  {{G.completion_gate(List.append(&2, Bool, pre, False{{}} <> post)) == G.Block{{}} : G.Decision}}\n\ndef completion_requires_all_checks(pre, post):\n  L.failed_check_blocks_completion(pre, post)\n"
    return None


def enforcement_for(template: str) -> str:
    if template == "bounded_retries":
        return "trajectory_bound"
    if template in ("evidence_requirements", "task_completion", "conditional_obligation"):
        return "post_action_gate"
    if template in ("protected_resources", "spending_limit", "data_policy", "file_ownership", "payee_provenance",
                    "request_scope", "tool_restriction", "custom_bend"):
        return "pre_action_block"
    return "contextual_unenforced"


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def validate_params(template: str, p: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if template == "tool_restriction" and not [t for t in p.get("blockedTools") or [] if t.strip()]:
        errors.append("Name at least one tool, e.g. Bash, Write or mcp__github__*.")
    if template == "conditional_obligation":
        if not (p.get("mustRun") or "").strip():
            errors.append("Name the command that must run, e.g. npm test.")
        if not p.get("whenWrites") and not p.get("whenTools"):
            errors.append("Name what triggers it: paths written (e.g. /repo/test/) or tools used.")
        for path in p.get("whenWrites") or []:
            if not path.startswith("/"):
                errors.append(f'Trigger path "{path}" must be absolute, e.g. /repo/test/.')
    if template == "protected_resources":
        paths = p.get("protectedPaths") or []
        if not paths:
            errors.append("At least one protected path is required.")
        for path in paths:
            if not path.startswith("/"):
                errors.append(f'Protected path "{path}" must be absolute.')
        if paths and not any(is_protected(r["path"], paths) for r in CATALOG):
            warnings.append("No current sandbox resource matches these paths; the rule will only apply to files created later.")
    if template == "bounded_retries":
        m = p.get("maxAttempts")
        if not _is_int(m) or not 1 <= m <= 10:
            errors.append("maxAttempts must be an integer from 1 to 10.")
    if template == "evidence_requirements":
        m = p.get("minSources")
        if not _is_int(m) or not 1 <= m <= 5:
            errors.append("minSources must be an integer from 1 to 5.")
        if m == 1:
            warnings.append("A minimum of 1 source cannot demonstrate independence; no formal property is checked for this setting.")
    if template == "spending_limit":
        c = p.get("capCents")
        if not _is_int(c) or not 1 <= c <= 10_000_000:
            errors.append("capCents must be a whole number of cents between 1 and 10,000,000.")
    if template == "task_completion":
        known = TASK_CHECKS + CI_CHECKS
        bad = [c for c in p.get("checks") or [] if c not in known]
        if bad:
            errors.append(f"Unknown checks: {', '.join(bad)}. Known: {', '.join(known)}.")
        if p.get("checks") is not None and len(p["checks"]) == 0:
            errors.append("At least one required check is needed.")
    return errors, warnings


def _now() -> int:
    return int(time.time() * 1000)


def validate_law(law: dict) -> dict:
    """Run Bend over a law's source and set validation + proof status from the real output."""
    out = {**law, "validationErrors": [], "updatedAt": _now()}
    if law["template"] == "contextual":
        return {**out, "validation": "valid", "proofStatus": "not_applicable", "proofOutput": None,
                "validationErrors": ["Contextual requirement: needs an LLM evaluator. It is recorded but NOT enforced in this build."]}
    if law["template"] == "custom_bend":
        return _validate_custom_bend(out)
    errors, warnings = validate_params(law["template"], law.get("params") or {})
    if errors:
        return {**out, "validation": "invalid", "validationErrors": errors, "proofStatus": "not_applicable"}
    out.update(validationErrors=warnings, validation="valid")
    src = bend_instance_source(law["template"], law.get("params") or {})
    out["bendLaw"] = src
    if not src:
        return {**out, "proofStatus": "not_applicable", "proofOutput": None}
    r = run_bend(["INSTANCE.bend"], workspace(f"law-{law['id']}", {"INSTANCE.bend": src}))
    c = classify(r)
    out["proofOutput"] = r.output
    out["proofStatus"] = {"proof_checked": "proof_checked", "stated": "stated", "unavailable": "unavailable"}.get(c, "proof_failed")
    # A failed instance proof means the generated rule doesn't have the property it claims: refuse to activate it.
    if out["proofStatus"] == "proof_failed":
        out["validation"] = "invalid"
        out["validationErrors"] = [*warnings, "Bend rejected the generated law instance; see output."]
    return out


_FORBIDDEN = [
    (re.compile(r'^\s*import\s+"', re.M), 'foreign imports (import "...") are not allowed in law files'),
    (re.compile(r"@unsafe"), "@unsafe defs are not allowed: they fall outside Bend’s proof guarantees"),
    (re.compile(r"^def\s+[\w.]+\?\s*\(", re.M), "unsafe `def f?(...)` defs are not allowed"),
    (re.compile(r"^def\s+main\s*\(", re.M), "law files may not define main"),
    (re.compile(r"^\s*import\s+0x", re.M), "hub packages cannot be imported"),
    (re.compile(r"^\s*import\s+[\w-]+@", re.M), "hub packages cannot be imported"),
]
_ALLOWED_IMPORTS = [r"^import Base$", r"^import \./governor\.bend as G$", r"^import \./LAWS\.bend as L$", r"^import \./PROOF\.bend as P$"]


def _validate_custom_bend(law: dict) -> dict:
    """A user-written Bend file, in two passes over the real checker: with proof defs stripped (are the statements
    and gate well-formed?), then the whole file (do the proofs check?)."""
    src = law["originalDefinition"]
    errors = [msg for rx, msg in _FORBIDDEN if rx.search(src)]
    for line in src.split("\n"):
        if re.match(r"^import\s", line) and not any(re.match(a, line.strip()) for a in _ALLOWED_IMPORTS):
            errors.append(f'Import not allowed: "{line.strip()}". Allowed: import Base, ./governor.bend as G, ./LAWS.bend as L, ./PROOF.bend as P.')
    if not re.search(r"^import Base$", src, re.M):
        errors.append("The file must start with `import Base`.")
    if errors:
        return {**law, "validation": "invalid", "validationErrors": errors, "proofStatus": "not_applicable", "proofOutput": None, "bendLaw": src}

    blocks = top_level_blocks(src)
    law_names = {m.group(1) for b in blocks if (m := re.match(r"^law\s+([\w.]+)\s*:", b["header"]))}
    has_gate = any(re.match(r"^def\s+gate\s*\(\s*c\s*:\s*G\.Checkpoint\s*\)\s*->\s*G\.Decision\s*:", b["header"]) for b in blocks)

    def is_proof(b: dict) -> bool:
        m = re.match(r"^def\s+([\w.]+)\s*\(", b["header"])
        return bool(m and m.group(1) in law_names)

    stripped = "\n\n".join(b["text"] for b in blocks if not is_proof(b))
    r1 = run_bend(["LAW.bend", "--check-only"], workspace(f"law-{law['id']}-statements", {"LAW.bend": stripped + "\n"}))
    c1 = classify(r1)
    if c1 == "unavailable":
        return {**law, "validation": "pending", "validationErrors": ["Bend toolchain not found; the law cannot be validated."], "proofStatus": "unavailable", "proofOutput": r1.output, "bendLaw": src}
    if c1 == "error":
        return {**law, "validation": "invalid", "validationErrors": ["Bend rejected the law statements (see output)."], "proofStatus": "not_applicable", "proofOutput": r1.output, "bendLaw": src}
    r2 = run_bend(["LAW.bend", "--check-only"], workspace(f"law-{law['id']}", {"LAW.bend": src}))
    c2 = classify(r2)
    warnings = []
    if not has_gate:
        warnings.append("No `def gate(c: G.Checkpoint) -> G.Decision` found: this law states properties but installs no runtime check.")
    if not law_names:
        warnings.append("No `law` declared: the gate is enforced but no property about it is stated or proven.")
    status = "not_applicable" if not law_names else "proof_checked" if c2 == "proof_checked" else "stated" if c2 == "stated" else "proof_failed"
    return {**law, "validation": "valid", "validationErrors": warnings, "proofStatus": status, "proofOutput": r2.output, "bendLaw": src, "updatedAt": _now()}


def compile_law(law: dict) -> tuple[bool, str]:
    """Install a law's runtime check. Built-in templates use the core Bend gates; custom Bend laws with a `gate`
    def are compiled, with a generated driver, into their own native program."""
    G.custom_gates.pop(law["id"], None)
    if not law.get("enabled", True):
        return False, "disabled"
    if law.get("validation") != "valid":
        return False, "not valid"
    if law["template"] == "contextual":
        return False, "contextual rules need an LLM evaluator (not enforced)"
    if law["template"] != "custom_bend":
        return True, "core Bend gate"
    if not re.search(r"^def\s+gate\s*\(", law["originalDefinition"], re.M):
        return False, "no gate def"
    driver = (BEND_DIR / "custom_driver.bend.txt").read_text()
    d = workspace(f"law-{law['id']}-build", {"LAW.bend": law["originalDefinition"], "DRIVER.bend": driver})
    binary = d / f"gate-{sha(law['originalDefinition'])}"
    mode, output = build_program("DRIVER.bend", binary, d)
    if mode == "failed":
        return False, f"compile failed: {output[:300]}"
    # without clang the same program runs interpreted
    cmd = [str(binary)] if mode == "native" else [find_bend() or "bend", str(d / "DRIVER.bend"), "--"]

    def gate(kind: str, arg: str) -> str:
        p = G.run_gate(cmd, [kind, arg], d)
        out = p.stdout.strip()
        if p.returncode != 0 or out not in ("allow", "block", "escalate"):
            raise G.GateError(f"custom gate answered {out!r} (exit {p.returncode})")
        return out

    G.custom_gates[law["id"]] = gate
    return True, "custom Bend gate compiled" if mode == "native" else "custom Bend gate (interpreted: install clang 14+ to compile it)"


def structured_for(template: str, params: dict, source_text: str, explanation: str, issues: list[str] | None = None) -> dict:
    return {
        "template": template,
        "params": params,
        "explanation": explanation,
        "checkpoint": "pre_action" if template in ("protected_resources", "tool_restriction") else "trajectory" if template == "bounded_retries" else None if template == "contextual" else "post_action",
        "evaluator": "llm" if template == "contextual" else "bend",
        "enforceability": "contextual" if template == "contextual" else "deterministic",
        "sourceText": source_text,
        "issues": issues or [],
    }
