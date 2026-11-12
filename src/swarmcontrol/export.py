"""Trace export for analysis and fine-tuning, built only from the recorded event log. Three JSONL datasets:

  trajectories  one line per agent: task, outcome, objective checks, labelled violations (law, blocked/executed,
                injected/natural), recovery, and for real-model runs the full conversation.
  sft           real-model conversations that succeeded with no violation taking effect.
  preferences   governed real-model runs: for each blocked action the agent then recovered from, the conversation
                up to the violating turn (prompt), the violating turn (rejected) and the corrected turn (chosen).

Simulated runs have no model conversations, so they only appear in `trajectories`, marked as simulated."""

from __future__ import annotations

import json

from .store import store


def _dump(x: dict) -> str:
    return json.dumps(x, separators=(",", ":"), ensure_ascii=False)


def conversation(evs: list[dict]) -> dict:
    start = next((e for e in evs if e["type"] == "agent_started"), None)
    data = (start or {}).get("data") or {}
    system, brief = data.get("system"), data.get("brief")
    messages: list[dict] = [{"role": "user", "content": brief}] if brief else []
    turn_ids: list[int] = [start["id"]] if brief else []
    for e in evs:
        if e["type"] != "model_turn":
            continue
        role = "user" if (e.get("data") or {}).get("role") == "user" else "assistant"
        content = [c for c in (e.get("data") or {}).get("content") or [] if c.get("type") != "thinking"]
        prev = messages[-1] if messages else None
        # merge consecutive same-role turns (e.g. tool results followed by human guidance)
        if prev and prev["role"] == role and isinstance(prev["content"], list):
            prev["content"].extend(content)
        else:
            messages.append({"role": role, "content": content})
            turn_ids.append(e["id"])
    return {"system": system, "messages": messages, "turnEventIds": turn_ids}


def agent_record(exp: dict, agent_id: str, evs: list[dict]) -> dict:
    cfg = exp["config"]
    queued = next((e for e in evs if e["type"] == "agent_queued"), None)
    qdata = (queued or {}).get("data") or {}
    end = next((e for e in reversed(evs) if e["type"] in ("task_completed", "task_failed", "agent_cancelled")), None)
    outcome = ((end or {}).get("data") or {}).get("outcome")
    violations = [e for e in evs if e.get("violation") and e["type"] in ("law_violated", "violation_executed")]
    recovered = {e["recovery"]["violationId"] for e in evs if e["type"] == "recovery_succeeded"}
    real = cfg.get("scenario") and cfg.get("scenario") != "synthetic"
    conv = conversation(evs) if real else None
    last = evs[-1] if evs else {}
    return {
        "id": f"{exp['id']}/{agent_id}",
        "experiment_id": exp["id"],
        "pair_id": cfg.get("pairId"),
        "scenario": cfg.get("scenario") or "synthetic",
        "simulated": exp.get("mode") == "simulation",
        "model": cfg.get("model"),
        "governed": cfg.get("governor"),
        "rules_in_prompt": cfg.get("rulesInPrompt"),
        "seed": exp.get("seed"),
        "agent_id": agent_id,
        "task": qdata.get("task"),
        "injected_instruction": qdata.get("injection"),
        "injected_faults": qdata.get("faults") if qdata.get("faults") is not None else ([qdata["fault"]] if qdata.get("fault") else []),
        "outcome": {"task_success": outcome.get("taskSuccess"), "claimed_success": outcome.get("claimedSuccess"), "checks": outcome.get("checks"),
                    "final_state": outcome.get("finalState"), "final_health": outcome.get("finalHealth")} if outcome
        else {"task_success": False, "claimed_success": False, "checks": None, "final_state": last.get("state") or "unknown", "final_health": last.get("health") or "unknown"},
        "labels": {
            "violations": [{
                "event_id": e["id"], "law_id": e["violation"]["lawId"], "law": e["violation"].get("lawName"), "template": e["violation"].get("template"),
                "disposition": e["violation"].get("disposition"), "origin": e["violation"].get("origin"), "propagated": bool(e["violation"].get("propagated")),
                "severity": e["violation"].get("severity"), "explanation": e["violation"].get("explanation"),
                "action": (e.get("action") or {}).get("summary"), "recovered": e["violation"]["violationId"] in recovered,
            } for e in violations],
            "any_violation_took_effect": any(e["violation"].get("disposition") == "executed" for e in violations),
            "escalated_to_human": any(e["type"] == "human_required" for e in evs),
            "human_actions": [e.get("data") for e in evs if e["type"] == "human_action"],
            "recoveries": [{"attempt": e["recovery"].get("attempt"), "feedback": e["recovery"].get("feedback")} for e in evs if e["type"] == "recovery_initiated"],
        },
        "tokens": sum(e.get("tokens") or 0 for e in evs),
        "cost_usd": round(sum(e.get("costUsd") or 0 for e in evs), 6),
        "system": conv["system"] if conv else None,
        "messages": conv["messages"] if conv else None,
        "actions": [{"event_id": e["id"], "type": e["type"], "tool": e["action"].get("tool"), "summary": e["action"].get("summary"), "decision": e.get("outcome")}
                    for e in evs if e.get("action") and e["type"] != "model_turn"],
    }


def preference_pairs(exp: dict, agent_id: str, evs: list[dict]) -> list[dict]:
    cfg = exp["config"]
    if not cfg.get("governor") or not cfg.get("scenario") or cfg["scenario"] == "synthetic":
        return []
    conv = conversation(evs)
    assistant = [(tid, i) for i, tid in enumerate(conv["turnEventIds"]) if conv["messages"][i]["role"] == "assistant"]

    def turn_before(event_id: int):
        return next(((tid, i) for tid, i in reversed(assistant) if tid < event_id), None)

    out = []
    for rec in (e for e in evs if e["type"] == "recovery_succeeded"):
        incident = rec["recovery"]["violationId"]
        blocked = next((e for e in evs if e["type"] == "law_violated" and (e.get("violation") or {}).get("violationId") == incident), None)
        if not blocked:
            continue
        rejected, chosen = turn_before(blocked["id"]), turn_before(rec["id"])
        if not rejected or not chosen or chosen[1] <= rejected[1]:
            continue
        out.append({
            "id": f"{exp['id']}/{agent_id}/{incident}", "experiment_id": exp["id"], "agent_id": agent_id, "model": cfg.get("model"),
            "law": blocked["violation"].get("lawName"), "origin": blocked["violation"].get("origin"), "explanation": blocked["violation"].get("explanation"),
            "system": conv["system"], "prompt": conv["messages"][: rejected[1]], "rejected": conv["messages"][rejected[1]], "chosen": conv["messages"][chosen[1]],
            "note": "chosen was generated after the runtime returned corrective feedback; that feedback is not in prompt",
        })
    return out


def export_lines(fmt: str, experiment_ids: list[str]) -> list[str]:
    lines: list[str] = []
    for exp_id in experiment_ids:
        exp = store().get_experiment(exp_id)
        if not exp:
            continue
        by_agent: dict[str, list[dict]] = {}
        for e in store().events(exp_id):
            if e.get("agentId"):
                by_agent.setdefault(e["agentId"], []).append(e)
        for agent_id, evs in by_agent.items():
            if fmt == "trajectories":
                lines.append(_dump(agent_record(exp, agent_id, evs)))
            elif fmt == "sft":
                r = agent_record(exp, agent_id, evs)
                if r["messages"] and r["outcome"]["task_success"] and not r["labels"]["any_violation_took_effect"] and not r["labels"]["escalated_to_human"]:
                    lines.append(_dump({"id": r["id"], "model": r["model"], "system": r["system"], "messages": r["messages"],
                                        "metadata": {"scenario": r["scenario"], "governed": r["governed"], "violations_blocked": len(r["labels"]["violations"])}}))
            else:
                lines.extend(_dump(p) for p in preference_pairs(exp, agent_id, evs))
    return lines
