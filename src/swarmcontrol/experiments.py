"""Experiment lifecycle: single runs, paired (baseline vs governed) runs, and the live experiments that collect the
user's own harness sessions. Paired runs share every input except the governor flag."""

from __future__ import annotations

import math
import os
import threading
import time
import uuid

from .laws.registry import BUILTIN_IDS, list_laws
from .llm import DEFAULT_MODEL, llm_available
from .real.claude_code import claude_code_available
from .real.families import BENCH_FAMILIES, task_count
from .real.runner import RealRunner
from .runtime.simulator import ExperimentRunner
from .store import store

DEFAULT_FAILURE = {
    "rate": 0.4, "hazard": 0.04,
    "weights": {"protected_write": 1, "retry_loop": 1, "insufficient_evidence": 1, "premature_completion": 1, "constraint_violation": 1,
                "unverifiable_source": 0.4, "prompt_injection": 0},
    "persistence": 0.2,
}

_runners: dict[str, RealRunner | ExperimentRunner] = {}
_attached: dict[tuple[str, bool], str] = {}
_lock = threading.RLock()


def _clamp(x, lo, hi):
    return min(hi, max(lo, x))


def recover_interrupted() -> None:
    for e in store().experiments():
        if e["status"] == "running":
            # an attached harness run has no end of its own: a restart just closes it (the next session opens a new one)
            if e["config"].get("attachProject"):
                store().put_experiment({**e, "status": "completed", "endedAt": e.get("endedAt") or int(time.time() * 1000)})
            else:
                store().put_experiment({**e, "status": "error", "error": "Server restarted while this experiment was running.",
                                        "endedAt": e.get("endedAt") or int(time.time() * 1000)})


def build_config(inp: dict) -> dict:
    scenario = inp.get("scenario") if inp.get("scenario") in ("web_research", "bugfix", "suite") else "synthetic"
    real = scenario != "synthetic"
    families = (inp.get("families") or BENCH_FAMILIES) if scenario == "suite" else [scenario] if real else None
    backend = (inp.get("backend") if inp.get("backend") in ("claude_code", "openrouter") else "api") if real else None
    attached = bool(families and "attached" in families)
    if backend == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
        raise ValueError("The OpenRouter backend needs OPENROUTER_API_KEY on the server.")
    if backend == "claude_code" and families and "web_research" in families:
        raise ValueError("Web research needs the API backend (it uses the server-side web_search tool).")
    task_limit = math.trunc(inp["taskLimit"]) if inp.get("taskLimit") and inp["taskLimit"] > 0 else None
    # real scenarios have a fixed task list; the synthetic simulator runs 50 or 100 agents
    swarm_size = task_count(families, task_limit) if real else 100 if inp.get("swarmSize") == 100 else 50
    mode = "llm" if real or inp.get("mode") == "llm" else "simulation"
    if backend == "claude_code" and not claude_code_available():
        raise ValueError("The Claude Code backend needs the `claude` CLI on PATH (or CLAUDE_BIN), logged in.")
    if mode == "llm" and backend == "api" and not llm_available() and not attached:
        raise ValueError("The API backend needs ANTHROPIC_API_KEY to be set on the server.")
    max_rec = _clamp(round(inp.get("maxRecoveryAttempts", 3)), 1, 10)
    all_laws = list_laws()
    law_ids = inp.get("lawIds") if inp.get("lawIds") is not None else [l["id"] for l in all_laws if l["enabled"]]
    # snapshot laws at launch so later edits do not change a recorded experiment
    laws = [{**l, "enabled": True, "params": {**l["params"], "maxAttempts": max_rec} if l["id"] == BUILTIN_IDS["retries"] else l["params"]}
            for l in all_laws if l["id"] in law_ids]
    f = inp.get("failure") or {}
    failure = {
        "rate": _clamp(f.get("rate", DEFAULT_FAILURE["rate"]), 0, 1),
        "hazard": _clamp(f.get("hazard", DEFAULT_FAILURE["hazard"]), 0, 0.5),
        "weights": {**DEFAULT_FAILURE["weights"], **(f.get("weights") or {})},
        "persistence": _clamp(f.get("persistence", DEFAULT_FAILURE["persistence"]), 0, 1),
    }
    speed = inp.get("speed")
    cfg = {
        "scenario": scenario, "rulesInPrompt": inp.get("rulesInPrompt", True), "taskLimit": task_limit, "swarmSize": swarm_size,
        "horizon": "long" if inp.get("horizon") == "long" else "short", "mode": mode, "governor": inp.get("governor", True),
        "lawIds": law_ids, "laws": laws, "failure": failure, "seed": math.trunc(inp.get("seed", 42)), "maxRecoveryAttempts": max_rec,
        "speed": 2 if speed is None else 0 if speed <= 0 else speed,
        "maxParallel": min(swarm_size, max(1, inp.get("maxParallel") or (6 if real else 32))),
        "model": (inp.get("model") or DEFAULT_MODEL) if mode == "llm" else None, "families": families, "backend": backend,
    }
    for k in ("benchmarkId", "budgetUsd", "pairId", "pairRole", "repetition", "label", "harness", "attachProject"):
        cfg[k] = inp.get(k)
    # undefined fields are omitted from the stored document, as in the TypeScript server
    return {k: v for k, v in cfg.items() if v is not None}


def launch(cfg: dict) -> dict:
    exp = {"id": f"exp-{_base36(int(time.time() * 1000))}-{uuid.uuid4().hex[:4]}", "config": cfg, "mode": cfg["mode"], "seed": cfg["seed"],
           "status": "running", "startedAt": int(time.time() * 1000), "endedAt": None}
    store().put_experiment(exp)
    on_status = lambda e: store().put_experiment({**e, "config": exp["config"]})  # noqa: E731
    if cfg["scenario"] == "synthetic":
        runner: RealRunner | ExperimentRunner = ExperimentRunner({**exp, "config": cfg}, store().append_events, on_status)
    else:
        runner = RealRunner(exp, store().append_events, on_status)
    with _lock:
        _runners[exp["id"]] = runner
    if isinstance(runner, RealRunner) and "attached" in (cfg.get("families") or []):
        runner.run()  # attached: records sessions as their hooks arrive
    else:
        threading.Thread(target=_run, args=(runner, exp), daemon=True, name=f"run-{exp['id']}").start()
    return exp


def _run(runner: RealRunner | ExperimentRunner, exp: dict) -> None:
    try:
        runner.run()
    except Exception as e:  # noqa: BLE001
        store().put_experiment({**exp, "status": "error", "error": str(e), "endedAt": int(time.time() * 1000)})
        runner.done.set()


def _base36(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + s
    return s or "0"


def start_experiment(inp: dict) -> dict:
    return launch(build_config(inp))


def start_paired(inp: dict) -> dict:
    """Same workload under both conditions: identical config, seed and fault schedule."""
    pair_id = f"pair-{uuid.uuid4().hex[:8]}"
    base = build_config({**inp, "pairId": pair_id})
    return {"pairId": pair_id, "baseline": launch({**base, "governor": False, "pairRole": "baseline"}),
            "governed": launch({**base, "governor": True, "pairRole": "governed"})}


def start_repetitions(inp: dict, repetitions: int) -> dict:
    """Repeated pairs (seed, seed+1, ...) run instantly, one pair at a time."""
    n = min(20, max(1, int(repetitions)))
    group = f"reps-{uuid.uuid4().hex[:6]}"
    build_config(inp)  # validate before returning

    def go():
        for i in range(n):
            p = start_paired({**inp, "seed": inp.get("seed", 42) + i, "speed": 0, "repetition": i, "label": group})
            for e in (p["baseline"], p["governed"]):
                _runners[e["id"]].done.wait()

    threading.Thread(target=go, daemon=True, name=group).start()
    return {"group": group, "repetitions": n}


def attached_runner(project: str, enforce: bool) -> RealRunner:
    """One live experiment per (project, mode) collects the user's own harness sessions; created on first use."""
    with _lock:
        live = _attached.get((project, enforce))
        r = _runners.get(live) if live else None
        if isinstance(r, RealRunner):
            return r
        exp = launch(build_config({"scenario": "suite", "families": ["attached"], "governor": enforce, "attachProject": project, "label": f"attached: {project}"}))
        _attached[(project, enforce)] = exp["id"]
        return _runners[exp["id"]]


def close_attached(exp_id: str) -> None:
    with _lock:
        r = _runners.get(exp_id)
        if isinstance(r, RealRunner):
            r.close()
        for k, v in list(_attached.items()):
            if v == exp_id:
                del _attached[k]


def close_all_attached() -> None:
    """Attached sessions snapshot their laws when they start; after a law change the next hook opens a fresh record."""
    for exp_id in list(_attached.values()):
        close_attached(exp_id)


def runner_for(exp_id: str) -> RealRunner | None:
    return _runners.get(exp_id)


def reset_for_test() -> None:
    with _lock:
        _runners.clear()
        _attached.clear()
