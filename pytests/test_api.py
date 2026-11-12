"""The HTTP API: auth, laws, the Claude Code hook route, the neutral attach route, approvals and export."""

import importlib

import pytest
from fastapi.testclient import TestClient

from conftest import needs_bend
from swarmcontrol import experiments as X
from swarmcontrol.laws.registry import init_laws

pytestmark = needs_bend


@pytest.fixture()
def client(fresh_store, monkeypatch):
    import swarmcontrol.api as api
    X.reset_for_test()
    init_laws()
    api._core.update({"proofStatus": "proof_checked"})  # booted by the session fixture
    with TestClient(api.app) as c:
        yield c
    X.close_all_attached()


def hook(c, event, session="s1", **payload):
    return c.post("/api/hooks/claude-code", json={"payload": {"hook_event_name": event, "session_id": session, "cwd": "/w", **payload},
                                                  "identity": {"project": "api-test", "agent": "alice", "canWait": True}}).json()


def test_status_and_laws(client):
    s = client.get("/api/status").json()
    assert s["gatesLoaded"] is True
    assert any(l["id"] == "law-protected" for l in client.get("/api/laws").json())
    assert client.get("/api/nope").status_code == 404


def test_hook_route_blocks_escalates_and_takes_a_human_decision(client):
    assert hook(client, "PreToolUse", tool_name="Read", tool_input={"file_path": "/w/src/a.js"}) == {}
    out = hook(client, "PreToolUse", tool_name="Write", tool_input={"file_path": "/w/test/a.test.js"})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Protected resources" in out["hookSpecificOutput"]["permissionDecisionReason"]
    for _ in range(4):
        hook(client, "PreToolUse", tool_name="Write", tool_input={"file_path": "/w/test/a.test.js"})
    exp = next(e for e in client.get("/api/experiments").json() if e["config"].get("attachProject") == "api-test")
    assert exp["live"]
    events = client.get(f"/api/experiments/{exp['id']}/events").json()
    assert any(e["type"] == "human_required" for e in events)
    agent = events[-1]["agentId"]
    # a stopping session that can wait is told to hold for the decision
    assert hook(client, "Stop")["governorWait"] == {"experiment": exp["id"], "agent": agent}
    assert client.get(f"/api/attach/{exp['id']}/agents/{agent}/decision").json() == {"decided": False}
    assert client.post(f"/api/experiments/{exp['id']}/agents/{agent}/human", json={"action": "retry_with_guidance", "note": "src only"}).json() == {"ok": True}
    assert client.get(f"/api/attach/{exp['id']}/agents/{agent}/decision").json() == {"decided": True, "action": "retry_with_guidance", "note": "src only"}
    lines = client.get(f"/api/export?format=trajectories&experiments={exp['id']}").text.strip().splitlines()
    assert len(lines) == 1 and '"escalated_to_human":true' in lines[0]


def test_subagent_calls_become_their_own_agent(client):
    hook(client, "PreToolUse", tool_name="Read", tool_input={})
    hook(client, "PreToolUse", tool_name="Read", tool_input={}, agent_id="sub1", agent_type="reviewer")
    exp = next(e for e in client.get("/api/experiments").json() if e["config"].get("attachProject") == "api-test")
    started = [e["data"]["brief"] for e in client.get(f"/api/experiments/{exp['id']}/events").json() if e["type"] == "agent_started"]
    assert started == ["alice (role: agent)", "alice / reviewer (role: reviewer; subagent of alice, inherits its laws)"]


def test_neutral_attach_route(client):
    r = client.post("/api/attach/check", json={"project": "sdk", "agent": "bot", "tool": "Write", "input": {"file_path": "/w/package.json"}, "cwd": "/w"}).json()
    assert r["allow"] is False and "Protected" in r["reason"] and r["health"] == "yellow"
    r = client.post("/api/attach/check", json={"project": "sdk", "agent": "bot", "tool": "Write", "input": {"file_path": "/w/src/x.js"}, "cwd": "/w"}).json()
    assert r["allow"] is True


def test_token_auth(monkeypatch, client):
    import swarmcontrol.api as api
    monkeypatch.setattr(api, "TOKEN", "t0k")
    assert client.get("/api/laws").status_code == 401
    assert client.get("/api/laws", headers={"authorization": "Bearer t0k"}).status_code == 200
    assert client.get("/api/laws?token=t0k").status_code == 200
    assert client.get("/hook.py").status_code == 200  # scripts are public and hold no secrets


def test_benchmark_backends_need_their_credentials(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    r = client.post("/api/experiments", json={"scenario": "suite", "families": ["support"]})
    assert r.status_code == 400 and "ANTHROPIC_API_KEY" in r.json()["error"]
    r = client.post("/api/experiments", json={"scenario": "suite", "families": ["support"], "backend": "openrouter"})
    assert r.status_code == 400 and "OPENROUTER_API_KEY" in r.json()["error"]


def wait_status(c, exp_id, timeout=60):
    import time
    end = time.time() + timeout
    while time.time() < end:
        e = c.get(f"/api/experiments/{exp_id}").json()
        if e["status"] != "running":
            return e
        time.sleep(0.1)
    raise AssertionError("experiment did not finish")


def test_simulator_run_human_approval_and_repetitions(client):
    exp = client.post("/api/experiments", json={"seed": 3, "speed": 0, "failure": {"rate": 0.9, "persistence": 0.6}}).json()
    done = wait_status(client, exp["id"])
    assert done["status"] == "needs_attention"
    events = client.get(f"/api/experiments/{exp['id']}/events").json()
    waiting = [e["agentId"] for e in events if e["type"] == "human_required"]
    assert client.post(f"/api/experiments/{exp['id']}/agents/{waiting[0]}/human", json={"action": "retry_with_guidance", "note": "plain keywords"}).json() == {"ok": True}
    wait_status(client, exp["id"])
    after = client.get(f"/api/experiments/{exp['id']}/events?after={events[-1]['id']}").json()
    assert after[0]["type"] == "human_action"
    assert any(e["type"] == "experiment_completed" for e in after)

    r = client.post("/api/experiments/paired", json={"repetitions": 2, "config": {"seed": 9}}).json()
    assert r["repetitions"] == 2
    import time
    for _ in range(300):
        reps = [e for e in client.get("/api/experiments").json() if e["config"].get("label") == r["group"]]
        if len(reps) == 4 and all(e["status"] != "running" for e in reps):
            break
        time.sleep(0.1)
    assert sorted((e["config"]["seed"], e["config"]["pairRole"]) for e in reps) == [(9, "baseline"), (9, "governed"), (10, "baseline"), (10, "governed")]
