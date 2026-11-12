"""Natural language -> structured rules. A deterministic template matcher is always available; with a model key
configured, the LLM produces the same structured schema. Either way the output is a draft: it's shown to the user
and validated (including by Bend) before it can be activated."""

from __future__ import annotations

import re

from ..bend.adapter import structured_for
from ..llm import DEFAULT_MODEL, llm_available, translate_rules_with_llm
from ..runtime.sandbox import DEFAULT_PROTECTED

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                 "once": 1, "twice": 2, "single": 1}


def _find_number(s: str) -> int | None:
    m = re.search(r"\b(\d+)\b", s)
    if m:
        return int(m.group(1))
    for w, n in _NUMBER_WORDS.items():
        if re.search(rf"\b{w}\b", s, re.I):
            return n
    return None


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.;!?])\s+|\n+", text) if len(s.strip()) > 3]


def _is_requirement(s: str) -> bool:
    return bool(re.search(r"\b(must|should|shall|never|always|only|may not|cannot|can't|do not|don't|required?)\b", s, re.I))


def _clean(params: dict) -> dict:
    """Unset values are left out, never stored as null."""
    return {k: v for k, v in params.items() if v is not None}


def translate_deterministic(text: str) -> list[dict]:
    rules: list[dict] = []
    for s in _split_sentences(text):
        lower = s.lower()
        issues: list[str] = []

        then = re.search(r"\bmust\s+(?:also\s+)?run\s+[`\"']?(.+?)[`\"']?\s+before\s+(?:finishing|stopping|they\s+(?:finish|stop)|reporting\s+done|declaring\s+done|being\s+done|done)\b", s, re.I)
        if then and re.search(r"\b(if|when|whenever|that|who|after)\b", s, re.I):
            rest = s.replace(then.group(0), " ")
            when_writes = [re.sub(r"\.$", "", m.group(1)) for m in re.finditer(r"(/[\w.\-/*]+)", rest)]
            when_tools = [] if when_writes else [m.group(1) for m in re.finditer(r"\b(?:uses?|calls?)\s+(?:the\s+)?([A-Z][\w*]+)", s)]
            if not when_writes and not when_tools:
                issues.append('No trigger found: name the paths (e.g. /repo/test/) or tools (e.g. "uses Bash") that start the obligation.')
            cmd = then.group(1).strip()
            what = f"writes under {', '.join(when_writes)}" if when_writes else f"uses {', '.join(when_tools)}"
            rules.append(structured_for("conditional_obligation", {"whenWrites": when_writes, "whenTools": when_tools, "mustRun": cmd}, s,
                                        f'If the agent {what}, a shell command containing "{cmd}" must run after its last such change, before it may finish.', issues))
            continue

        tools = re.search(r"\b(?:must not|mustn't|may not|cannot|can't|never|not allowed to|do not|don't)\s+(?:ever\s+)?(?:use|call|run)\s+(?:the\s+)?(.+?)(?:\s+tools?)?\s*\.?$", s, re.I)
        if tools:
            blocked = [re.sub(r"\s+tools?$", "", re.sub(r"^(the|any)\s+", "", x, flags=re.I), flags=re.I).strip()
                       for x in re.split(r"\s*(?:,|\bor\b|\band\b|/)\s*", tools.group(1), flags=re.I)]
            blocked = [b for b in blocked if b]
            rules.append(structured_for("tool_restriction", {"blockedTools": blocked}, s, f"Before any tool call executes, block it if the tool is: {', '.join(blocked)}.", issues))
            continue

        if re.search(r"(protected|read-?only|off-?limits)", lower) or (re.search(r"\b(modify|write|edit|change|delete|overwrite|touch)\b", lower) and re.search(r"\b(file|resource|config|secret|path)", lower)):
            paths = [m.group(1) for m in re.finditer(r"(/[\w.\-/]+)", s)]
            if not paths:
                paths = list(DEFAULT_PROTECTED)
                issues.append(f"No paths named; using the sandbox's designated protected set ({', '.join(DEFAULT_PROTECTED)}). Edit the paths if that is not what you meant.")
            rules.append(structured_for("protected_resources", {"protectedPaths": paths}, s, f"Before any write executes, block it if the target is under: {', '.join(paths)}.", issues))
            continue

        if re.search(r"\b(source|sources|evidence|citation|cite|reference)", lower):
            n = _find_number(lower)
            if n is None:
                issues.append("No minimum number of sources stated.")
            if not re.search(r"independent|distinct|different|separate", lower):
                issues.append('"Independent" was not stated; sources will still be counted by distinct registrable domain.')
            rules.append(structured_for("evidence_requirements", _clean({"minSources": n}), s,
                                        f"Reject a claim unless it cites at least {n if n is not None else '?'} sources from different registrable domains.", issues))
            continue

        if re.search(r"\b(retr(y|ies)|attempts?|consecutive|tries)\b", lower) or (re.search(r"\bfail", lower) and re.search(r"\b(stop|after|more than|exceed)", lower)):
            n = _find_number(lower)
            if n is None:
                issues.append('No attempt limit stated; specify a number (e.g. "three").')
            elif re.search(r"\bless than\b|\bfewer than\b", lower):
                n -= 1
            rules.append(structured_for("bounded_retries", _clean({"maxAttempts": n}), s,
                                        f"Allow at most {n if n is not None else '?'} consecutive recovery attempts, then escalate to a human.", issues))
            continue

        if re.search(r"\b(complete|completion|done|finished|success)", lower) and re.search(r"\b(check|checks|validation|verified|pass)", lower):
            rules.append(structured_for("task_completion", {}, s, "Block any completion report unless every required task check passes.", issues))
            continue

        if _is_requirement(s):
            rules.append(structured_for("contextual", {}, s, "This requirement needs contextual judgment; no deterministic template matches it.",
                                        ["Not enforceable deterministically. It would need an LLM evaluator, which this build does not enforce."]))
        else:
            rules.append({"template": "contextual", "params": {}, "explanation": "Not recognized as a requirement.", "checkpoint": None, "evaluator": "none",
                          "enforceability": "unsupported", "sourceText": s, "issues": ["No supported law template matches this sentence."]})
    return rules


def translate(text: str, use_llm: bool) -> dict:
    if use_llm and llm_available():
        try:
            value, _ = translate_rules_with_llm(text)
            rules = []
            for r in value.rules:
                params: dict = {}
                issues = list(r.issues)
                if r.template == "protected_resources":
                    params["protectedPaths"] = r.protected_paths or list(DEFAULT_PROTECTED)
                    if not r.protected_paths:
                        issues.append(f"No paths named; using the designated protected set ({', '.join(DEFAULT_PROTECTED)}).")
                if r.template == "bounded_retries" and r.max_attempts is not None:
                    params["maxAttempts"] = r.max_attempts
                if r.template == "evidence_requirements" and r.min_sources is not None:
                    params["minSources"] = r.min_sources
                if r.template == "unsupported":
                    rules.append({"template": "contextual", "params": params, "explanation": r.explanation, "checkpoint": None, "evaluator": "none",
                                  "enforceability": "unsupported", "sourceText": r.source_text, "issues": issues})
                else:
                    rules.append(structured_for(r.template, params, r.source_text, r.explanation, issues))
            return {"rules": rules, "translator": f"llm:{DEFAULT_MODEL}"}
        except Exception as e:  # noqa: BLE001
            return {"rules": translate_deterministic(text), "translator": "deterministic",
                    "error": f"LLM translation failed ({e}); used the deterministic translator."}
    return {"rules": translate_deterministic(text), "translator": "deterministic"}
