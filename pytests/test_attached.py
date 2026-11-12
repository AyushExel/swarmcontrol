"""Attached harness sessions through the runner: subagent scoping, tool restrictions, conditional laws,
governor integrity, background subagents, escalation and human approval."""

import itertools

import pytest

from conftest import needs_bend
from swarmcontrol import experiments as X
from swarmcontrol.laws.registry import create_from_rule, delete_law, init_laws
from swarmcontrol.laws.translate import translate_deterministic

pytestmark = needs_bend
_n = itertools.count()


@pytest.fixture(autouse=True)
def env(fresh_store):
    X.reset_for_test()
    init_laws()
    yield
    X.close_all_attached()


def runner(enforce=True):
    return X.attached_runner(f"test-{next(_n)}", enforce)


def denied(out):
    return (out.get("hookSpecificOutput") or {}).get("permissionDecision") == "deny"


def blocked(out):
    return out.get("decision") == "block"


def pre(r, a, tool, inp):
    return r.hook_event(a, "PreToolUse", {"tool_name": tool, "tool_input": inp, "cwd": "/w"})


def law_from(text, name, scope=None):
    return create_from_rule(translate_deterministic(text)[0], name, scope)


def test_subagent_type_law_governs_only_that_subagent():
    law = law_from("Reviewers must not use Bash.", "Reviewers: no Bash", {"roles": ["reviewer"]})
    X.close_all_attached()
    r = runner()
    parent = r.attach_agent("s1", "alice", "implementer", "/w")
    reviewer = r.attach_agent("s1:a1", "alice / reviewer", "reviewer", "/w", None, {"names": ["alice"], "roles": ["implementer"]})
    assert denied(pre(r, reviewer, "Bash", {"command": "ls"}))
    assert not denied(pre(r, parent, "Bash", {"command": "ls"}))
    # laws inherit downward: the built-in protected-tests law still covers the subagent
    assert denied(pre(r, reviewer, "Write", {"file_path": "/w/test/a.test.js"}))
    delete_law(law["id"])


def test_conditional_law_blocks_finish_until_command_runs():
    law = law_from("Agents that modify /repo/src/ must run npm test before finishing.", "src changes need tests")
    X.close_all_attached()
    write = {"tool_name": "Edit", "tool_input": {"file_path": "/w/src/cart.js"}, "cwd": "/w"}
    test = {"tool_name": "Bash", "tool_input": {"command": "npm test 2>&1"}, "cwd": "/w"}
    r = runner()
    a = r.attach_agent("o1", "bob", "implementer", "/w")
    assert not blocked(r.hook_event(a, "Stop", {}))  # nothing triggered yet
    b = r.attach_agent("o2", "bob2", "implementer", "/w")
    r.hook_event(b, "PostToolUse", write)
    out = r.hook_event(b, "Stop", {})
    assert blocked(out)
    assert "changed src/cart.js" in out["reason"] and '"npm test"' in out["reason"]
    r.hook_event(b, "PostToolUse", test)
    assert not blocked(r.hook_event(b, "Stop", {}))
    # a later change re-arms the obligation, for subagents too (SubagentStop)
    sub = r.attach_agent("o2:s1", "bob2 / fixer", "fixer", "/w", None, {"names": ["bob2"], "roles": ["implementer"]})
    r.hook_event(sub, "PostToolUse", write)
    assert blocked(r.hook_event(sub, "SubagentStop", {}))

    o = runner(enforce=False)
    c = o.attach_agent("o3", "carol", "implementer", "/w")
    o.hook_event(c, "PostToolUse", write)
    assert not blocked(o.hook_event(c, "Stop", {}))
    from swarmcontrol.store import store
    assert any(e["type"] == "violation_executed" and e["violation"]["lawId"] == law["id"] for e in store().events(o.exp["id"]))
    delete_law(law["id"])


@pytest.mark.parametrize("enforce", [True, False])
def test_governor_integrity_even_in_observe_mode(enforce):
    r = runner(enforce)
    a = r.attach_agent("i", "mallory", "implementer", "/w")
    assert denied(pre(r, a, "Edit", {"file_path": "/w/.claude/settings.local.json"}))
    assert denied(pre(r, a, "Write", {"file_path": "/w/.claude/hooks/swarmcontrol-hook.py"}))
    assert denied(pre(r, a, "Bash", {"command": "echo {} > .claude/settings.json"}))
    assert denied(pre(r, a, "Write", {"file_path": "/home/me/.config/swarmcontrol/config.json"}))


def test_background_subagents_defer_done_checks():
    r = runner()
    a = r.attach_agent("w1", "lead", "orchestrator", "/w")
    failing = {"ok": False, "output": "not done"}
    pre(r, a, "Agent", {})
    for _ in range(5):
        assert not blocked(r.hook_event(a, "Stop", {}, failing))
    assert a.health == "green"
    sub = r.attach_agent("w1:s1", "lead / researcher", "researcher", "/w", None, {"names": ["lead"], "roles": ["orchestrator"]})
    r.hook_event(sub, "SubagentStop", {})
    assert blocked(r.hook_event(a, "Stop", {}, failing))


def test_repeated_blocks_escalate_and_human_approval_clears_them():
    r = runner()
    a = r.attach_agent("e1", "dev", "implementer", "/w")

    def write(path):
        return pre(r, a, "Write", {"file_path": path})

    for _ in range(3):
        assert denied(write("/w/test/a.test.js"))
        assert a.state != "awaiting_human"
        write("/w/src/ok.js")  # a passing write in between would have reset the old budget
        r.hook_event(a, "Stop", {}, {"ok": False, "output": "gate failed"})
        if a.state == "awaiting_human":
            break
    if a.state != "awaiting_human":
        write("/w/test/a.test.js")
    assert a.state == "awaiting_human" and a.health == "red"
    a.held_at = 0
    r.human_action(a.id, "retry_with_guidance", "carry on")
    assert a.state == "recovering"
    # the waiting hook collects the decision once
    assert r.human_decision(a.id) == {"decided": True, "action": "retry_with_guidance", "note": "carry on"}
    assert denied(write("/w/test/a.test.js"))
    assert a.state != "awaiting_human"


def test_escalated_subagent_no_longer_counts_as_running():
    r = runner()
    lead = r.attach_agent("p1", "lead", "orchestrator", "/w")
    pre(r, lead, "Agent", {})
    sub = r.attach_agent("p1:s", "lead / eng", "eng", "/w", None, {"names": ["lead"], "roles": ["orchestrator"]})
    for _ in range(4):
        pre(r, sub, "Write", {"file_path": "/w/test/a.js"})
    assert sub.state == "awaiting_human"
    r.hook_event(sub, "SubagentStop", {})
    assert blocked(r.hook_event(lead, "Stop", {}, {"ok": False, "output": "no"}))


@pytest.mark.parametrize("cmd", ["echo x >> ~/.bashrc", "echo x >> ~/.zprofile", "echo x > $HOME/.zshrc", "cat > ~/.local/bin/node",
                                 "cp a ~/.config/swarmcontrol/release-gate.js"])
def test_machine_environment_is_off_limits(cmd):
    r = runner(enforce=False)  # even in observe mode
    a = r.attach_agent("n1", "dev", "implementer", "/w")
    assert denied(pre(r, a, "Bash", {"command": cmd}))
    assert not denied(pre(r, a, "Bash", {"command": "npm test"}))
    assert not denied(pre(r, a, "Bash", {"command": "echo x > notes.txt"}))


def test_law_changes_open_a_fresh_session_record():
    r = runner()
    X.close_all_attached()
    assert X.attached_runner(r.cfg["attachProject"], True) is not r
