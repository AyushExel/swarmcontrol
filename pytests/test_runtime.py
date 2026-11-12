"""The simulated runtime governor, end to end."""

import pytest

from conftest import needs_bend
from swarmcontrol.bend import gates as G
from swarmcontrol.experiments import build_config
from swarmcontrol.laws.registry import BUILTIN_IDS, init_laws, list_laws
from swarmcontrol.metrics import replay
from swarmcontrol.runtime.sandbox import DEFAULT_PROTECTED, is_protected
from swarmcontrol.runtime.simulator import ExperimentRunner

pytestmark = needs_bend


def run(**inp):
    cfg = build_config({"speed": 0, **inp})
    events: list[dict] = []
    exp = {"id": "exp-test", "config": cfg, "mode": cfg["mode"], "seed": cfg["seed"], "status": "running"}
    r = ExperimentRunner(exp, events.extend, lambda e: None)
    r.run()
    return events, exp, r


def strip(evs):
    return [{**{k: v for k, v in e.items() if k not in ("ts", "experimentId", "evaluations")},
             "ev": [{k: v for k, v in x.items() if k != "micros"} for x in e["evaluations"]] if e.get("evaluations") else None} for e in evs]


@pytest.fixture(autouse=True)
def laws(fresh_store):
    init_laws()


def protected_writes(evs):
    return [e for e in evs if e["type"] == "action_executed" and e.get("action", {}).get("tool") == "write" and is_protected(str(e["action"]["args"]["path"]), DEFAULT_PROTECTED)]


def test_blocks_prohibited_writes_baseline_lets_them_through():
    base, _, _ = run(swarmSize=50, seed=7, governor=False)
    gov, _, _ = run(swarmSize=50, seed=7, governor=True)
    assert [e for e in gov if e["type"] == "action_blocked" and e.get("action", {}).get("tool") == "write"]
    assert not protected_writes(gov) and protected_writes(base)
    gm, bm = replay(gov)["metrics"], replay(base)["metrics"]
    assert gm["protectedModified"] == 0 and bm["protectedModified"] > 0  # measured from sandbox state, not from the governor's log
    assert gm["prohibitedExecuted"] == 0 and gm["prohibitedBlocked"] == gm["prohibitedAttempted"]


def test_recovers_automatically_and_escalates_when_the_budget_is_exhausted():
    evs, _, _ = run(swarmSize=100, seed=11, governor=True, failure={"rate": 0.6, "persistence": 0.3})
    snap = replay(evs)
    m = snap["metrics"]
    assert m["recoveriesSucceeded"] > 0 and m["humanRequired"] > 0
    # a recovered agent goes yellow then back to green
    rec = next(e for e in evs if e["type"] == "recovery_succeeded" and e.get("health") == "green")
    assert any(e.get("health") == "yellow" for e in evs if e["agentId"] == rec["agentId"] and e["id"] < rec["id"])
    # every escalated agent is red and awaiting a human
    agents = snap["agents"].values() if isinstance(snap["agents"], dict) else snap["agents"]
    assert all(a["health"] == "red" for a in agents if a["state"] == "awaiting_human")


def test_fails_closed_when_the_bend_evaluator_is_unavailable():
    saved = G.core()[0]
    G.set_core_for_test(None, "simulated outage")
    try:
        evs, _, _ = run(swarmSize=50, seed=3, governor=True)
        assert not [e for e in evs if e["type"] == "action_executed" and e.get("action", {}).get("tool") == "write"]  # nothing is allowed without an evaluation
        assert any(any(x["result"] == "error" and x["decision"] == "block" for x in e.get("evaluations") or []) for e in evs)
        assert replay(evs)["metrics"]["byState"]["awaiting_human"] == 50
    finally:
        G.set_core_for_test(saved)


def test_reproducible_and_pairs_share_one_fault_schedule():
    a, _, _ = run(swarmSize=50, seed=99, governor=True)
    b, _, _ = run(swarmSize=50, seed=99, governor=True)
    assert strip(a) == strip(b)
    base, _, _ = run(swarmSize=50, seed=99, governor=False)

    def schedule(evs):
        return [[e["agentId"], e["data"].get("fault"), e["data"].get("persistent"), e["data"]["task"]["question"]] for e in evs if e["type"] == "agent_queued"]

    assert schedule(base) == schedule(a)


def test_consistent_metrics_from_the_event_log():
    base, _, _ = run(swarmSize=100, seed=5, governor=False)
    gov, _, _ = run(swarmSize=100, seed=5, governor=True)
    for evs in (base, gov):
        m = replay(evs)["metrics"]
        assert m["total"] == 100
        assert m["violationsBlocked"] + m["violationsExecuted"] + m["violationsFlagged"] == m["violationsAttempted"]
        assert m["violationsInjected"] + m["violationsNatural"] == m["violationsAttempted"]
        assert m["violationsNatural"] == 0  # simulation: every violation traces to an injected fault
        assert sum(m["byState"].values()) == 100
        assert m["taskSuccess"] <= m["finished"]
    assert replay(base)["metrics"]["violationsBlocked"] == 0
    assert replay(gov)["metrics"]["violationsFoundByAudit"] == 0


def test_human_retry_does_not_bypass_enforcement():
    only_writes = {"protected_write": 1, "retry_loop": 0, "insufficient_evidence": 0, "premature_completion": 0, "constraint_violation": 0, "unverifiable_source": 0, "prompt_injection": 0}
    evs, _, r = run(swarmSize=50, seed=11, governor=True, failure={"rate": 1, "persistence": 1, "weights": only_writes})
    waiting = next(a for a in r.agents if a.state == "awaiting_human")
    r.human_action(waiting.id, "retry_with_guidance", "Write to your own notes file.")
    r.done.wait(30)
    import time
    for _ in range(100):
        if r.is_finished:
            break
        time.sleep(0.05)
    mine = [e for e in evs if e["agentId"] == waiting.id]
    assert any(e["type"] == "human_action" for e in mine)
    assert mine[-1]["type"] == "task_completed"
    assert not [e for e in mine if e["type"] == "action_executed" and e.get("action", {}).get("tool") == "write" and is_protected(str(e["action"]["args"]["path"]), DEFAULT_PROTECTED)]


def test_governed_with_a_subset_of_laws():
    evs, exp, _ = run(swarmSize=50, seed=7, governor=True, lawIds=[BUILTIN_IDS["evidence"]])
    assert [l["id"] for l in exp["config"]["laws"]] == [BUILTIN_IDS["evidence"]]
    # protected writes are not governed here, so the audit sees them take effect
    assert replay(evs)["metrics"]["prohibitedExecuted"] > 0
    assert len(list_laws()) >= 4
