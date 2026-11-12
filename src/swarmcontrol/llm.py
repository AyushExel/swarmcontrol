"""Model provider. Used only when an Anthropic credential is configured; everything else runs without it."""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL") or "claude-opus-5-5"

# $ per million tokens, for cost estimates only (Anthropic pricing, Oct 2026; open models via OpenRouter)
PRICING = {
    "claude-fable-5-1": (10, 50),
    "claude-opus-5-5": (4, 20),
    "claude-sonnet-5-5": (2, 10),
    "claude-haiku-5-5": (0.1, 0.5),
    "claude-haiku-4-5": (1, 5),
    "qwen/qwen3-coder-30b-a3b-instruct": (0.07, 0.28),
}
# blended price used for simulated tokens, labelled as an estimate in the UI
SIMULATED_PRICE_PER_MTOK = 6


def price_for(model: str) -> tuple[float, float]:
    return PRICING.get(model, PRICING["claude-opus-5-5"])


def llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


_client = None


def client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()
    return _client


def structured(model: str, system: str, user: str, schema: dict, output: type[BaseModel], max_tokens: int = 4000) -> tuple[BaseModel, dict]:
    """One structured-output call: the response must match `schema`, then is validated by the Pydantic model.
    Refusals fall back server-side to another model."""
    res = client().beta.messages.create(
        model=model,
        max_tokens=max_tokens,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if res.stop_reason == "refusal":
        raise RuntimeError("model declined the request")
    if res.stop_reason == "max_tokens":
        raise RuntimeError("model output was truncated")
    text = next((b.text for b in res.content if b.type == "text"), None)
    if text is None:
        raise RuntimeError("model returned no output")
    value = output.model_validate(json.loads(text))
    p_in, p_out = price_for(res.model)
    usage = {"inputTokens": res.usage.input_tokens, "outputTokens": res.usage.output_tokens,
             "costUsd": (res.usage.input_tokens * p_in + res.usage.output_tokens * p_out) / 1e6}
    return value, usage


def _strict(props: dict[str, Any]) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


# ---------------------------------------------------------------------------
# Natural-language law translation

class _Rule(BaseModel):
    template: str
    source_text: str
    explanation: str
    protected_paths: list[str] | None
    max_attempts: int | None
    min_sources: int | None
    issues: list[str]


class Rules(BaseModel):
    rules: list[_Rule]


_NULLABLE_INT = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
RULES_SCHEMA = _strict({"rules": {"type": "array", "items": _strict({
    "template": {"type": "string", "enum": ["protected_resources", "bounded_retries", "evidence_requirements", "task_completion", "contextual", "unsupported"]},
    "source_text": {"type": "string"},
    "explanation": {"type": "string"},
    "protected_paths": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
    "max_attempts": _NULLABLE_INT,
    "min_sources": _NULLABLE_INT,
    "issues": {"type": "array", "items": {"type": "string"}},
})}})

_TRANSLATE_SYSTEM = """You translate natural-language requirements for AI agents into structured rules for a runtime governor.
Supported templates (use only these):
- protected_resources: agents must not modify specific files/resources. Fill protected_paths with absolute path prefixes (ending in "/" for directories) only if the text names them; otherwise null.
- bounded_retries: a maximum number of consecutive failed/recovery attempts. Fill max_attempts only if the text states a number.
- evidence_requirements: claims need a minimum number of independent sources. Fill min_sources only if stated.
- task_completion: completion may only be reported when required checks pass.
- contextual: a real requirement that needs judgment (tone, relevance, quality) and cannot be checked deterministically.
- unsupported: anything else.
One rule per distinct requirement; source_text is the exact span it came from. Never invent numbers or paths: if a needed value is missing or ambiguous, leave it null and describe the problem in issues."""


def translate_rules_with_llm(text: str, model: str = DEFAULT_MODEL) -> tuple[Rules, dict]:
    return structured(model, _TRANSLATE_SYSTEM, text, RULES_SCHEMA, Rules)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Simulator in LLM mode: the model writes findings and picks citations

class _Finding(BaseModel):
    text: str
    source_ids: list[str]


class Findings(BaseModel):
    findings: list[_Finding]


FINDINGS_SCHEMA = _strict({"findings": {"type": "array", "items": _strict({"text": {"type": "string"}, "source_ids": {"type": "array", "items": {"type": "string"}}})}})


def write_findings_with_llm(model: str, question: str, sources: list[dict], feedback: str | None, previous: list[dict] | None) -> tuple[Findings, dict]:
    system = ("You are a research agent in a swarm. Answer only from the provided sources (they are synthetic test documents). "
              "Each finding must be at most 60 words, specific to the question, and cite source ids from the list.")
    parts = [f"Question: {question}",
             "Sources:\n" + "\n".join(f"- [{s['id']}] {s['title']} ({s['url']}, {s['publisher']}): {s['snippet']}" for s in sources)]
    if previous:
        parts.append(f"Your previous findings:\n{json.dumps(previous)}")
    parts.append(f"Runtime feedback on your previous submission (address it):\n{feedback}" if feedback else "Write 2 findings.")
    return structured(model, system, "\n\n".join(parts), FINDINGS_SCHEMA, Findings, 3000)  # type: ignore[return-value]
