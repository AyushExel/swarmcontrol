"""Bend toolchain and gates, the law adapter, the registry, the translator and law scoping."""

import pytest

from conftest import needs_bend
from swarmcontrol.bend import gates as G
from swarmcontrol.bend.adapter import EvalContext, evaluate_checkpoint
from swarmcontrol.bend.toolchain import build_and_check_core, gates_binary, run_bend, workspace
from swarmcontrol.laws.registry import BUILTIN_IDS, create_bend, init_laws, list_laws, preview_bend, preview_rule, update_law
from swarmcontrol.laws.scope import law_applies_to, normalize_scope
from swarmcontrol.laws.translate import translate_deterministic
from swarmcontrol.paths import BEND_DIR
from swarmcontrol.runtime.sandbox import ResourceRegistry

def rule(template, params):
    return {"template": template, "params": params, "explanation": "", "checkpoint": None, "evaluator": "bend", "enforceability": "deterministic", "sourceText": "", "issues": []}


@needs_bend
class TestBend:
    def test_proves_every_core_law(self):
        s = build_and_check_core()
        assert s.proofStatus == "proof_checked"
        assert "ALL PROOFS CHECK" in s.proofOutput
        assert [l["name"] for l in s.laws] == ["protected_write_blocked", "unprotected_write_allowed", "retry_budget_escalates", "single_domain_insufficient",
                                               "failed_check_blocks_completion", "over_cap_blocked", "within_cap_allowed", "unlisted_blocked", "listed_allowed"]

    def test_proofs_are_not_vacuous(self):
        gov = (BEND_DIR / "governor.bend").read_text()
        broken = gov.replace("escalate_unless(lt(attempts, max))", "escalate_unless(lt(attempts, 1n+max))")
        assert broken != gov
        d = workspace("test-mutation", {"governor.bend": broken})
        r = run_bend(["PROOF.bend"], d)
        assert r.code != 0 and "SOME PROOFS FAIL" in r.output

    def test_runs_the_compiled_gates(self):
        g, err = G.core()
        assert g and not err
        assert g.write_gate(3, [1, 3]) == "block"
        assert g.write_gate(9, [1, 3]) == "allow"
        assert g.retry_gate(2, 3) == "allow"
        assert g.retry_gate(3, 3) == "escalate"
        assert g.evidence_gate(2, [7, 7, 7]) == "block"
        assert g.evidence_gate(2, [7, 8]) == "allow"
        assert g.completion_gate([True, False, True]) == "block"
        assert g.completion_gate([True, True]) == "allow"
        assert g.completion_gate([]) == "allow"

    def test_interpreted_gates_decide_like_the_compiled_program(self):
        """Without clang the gates run as `bend gates.bend -- …`: same program, same decisions (empty lists included)."""
        from swarmcontrol.bend.toolchain import find_bend
        interpreted = G.CoreGates([find_bend(), str(BEND_DIR / "gates.bend"), "--"], BEND_DIR)
        native, _ = G.core()
        for call in (("write_gate", 3, [1, 3]), ("write_gate", 9, []), ("allow_gate", 2, []), ("retry_gate", 3, 3),
                     ("evidence_gate", 2, [7, 7]), ("spend_gate", 30000, 20000), ("completion_gate", []), ("completion_gate", [True, False])):
            assert getattr(interpreted, call[0])(*call[1:]) == getattr(native, call[0])(*call[1:]), call

    def test_instance_laws_from_parameters(self, fresh_store):
        assert preview_rule(rule("bounded_retries", {"maxAttempts": 4}))["proofStatus"] == "proof_checked"
        assert preview_rule(rule("evidence_requirements", {"minSources": 3}))["proofStatus"] == "proof_checked"
        assert preview_rule(rule("evidence_requirements", {"minSources": 1}))["proofStatus"] == "not_applicable"
        assert preview_rule(rule("bounded_retries", {}))["validation"] == "invalid"

    def test_stated_checked_failed_and_invalid_bend_laws(self, fresh_store):
        head = "import Base\nimport ./governor.bend as G\n\n"
        assert preview_bend(f"{head}law w:\n  {{G.write_gate(7n, [7n]) == G.Block{{}} : G.Decision}}\n\ndef w():\n  {{==}}\n")["proofStatus"] == "proof_checked"
        op = preview_bend(f"{head}law w:\n  {{G.write_gate(7n, [7n]) == G.Block{{}} : G.Decision}}\n")
        assert op["validation"] == "valid" and op["proofStatus"] == "stated"
        op2 = preview_bend(f"{head}law w:\n  {{G.write_gate(7n, [7n]) == G.Block{{}} : G.Decision}}\n\nlaw v:\n  {{G.write_gate(8n, [8n]) == G.Block{{}} : G.Decision}}\n")
        assert op2["validation"] == "valid" and op2["proofStatus"] == "stated"
        wrong = preview_bend(f"{head}law w:\n  {{G.write_gate(7n, [8n]) == G.Block{{}} : G.Decision}}\n\ndef w():\n  {{==}}\n")
        assert wrong["validation"] == "valid" and wrong["proofStatus"] == "proof_failed"
        assert preview_bend(f"{head}law w:\n  {{G.write_gate(7n == \n")["validation"] == "invalid"
        assert preview_bend(f'{head}import "./evil.js"\n')["validation"] == "invalid"

    def test_custom_bend_gate_blocks_at_runtime(self, fresh_store):
        src = ("import Base\nimport ./governor.bend as G\n\n# notes for agent-001 are frozen\ndef gate(c: G.Checkpoint) -> G.Decision:\n  match c:\n"
               "    case G.Write{r}:\n      G.block_if(Nat.is_eq(r, 1022n))\n    case _:\n      G.Allow{}\n\n"
               "law frozen:\n  {gate(G.Write{1022n}) == G.Block{} : G.Decision}\n\ndef frozen():\n  {==}\n")
        law = create_bend("Freeze one file", src)
        assert law["validation"] == "valid" and law["proofStatus"] == "proof_checked" and law["installed"]
        reg = ResourceRegistry()
        while reg.id(f"/x/{len(reg.ids)}") < 1022:
            pass
        ctx = EvalContext(reg, lambda d: 0)
        path = next(p for p, i in reg.ids.items() if i == 1022)
        assert evaluate_checkpoint(law, {"kind": "write", "path": path}, ctx)["decision"] == "block"
        assert evaluate_checkpoint(law, {"kind": "write", "path": "/config/governor.yaml"}, ctx)["decision"] == "allow"
        assert evaluate_checkpoint(law, {"kind": "retry", "attempts": 1, "max": 3, "reason": ""}, ctx)["decision"] == "allow"
        update_law(law["id"], enabled=False)
        assert law["id"] not in G.custom_gates

    def test_registry_seeds_builtins_and_team_laws(self, fresh_store):
        init_laws()
        ids = {l["id"] for l in list_laws()}
        assert set(BUILTIN_IDS.values()) <= ids and "law-team-tests" in ids
        protected = next(l for l in list_laws() if l["id"] == "law-protected")
        assert protected["validation"] == "valid" and protected["proofStatus"] == "proof_checked" and protected["installed"]


class TestFailClosed:
    def test_gate_outage_blocks(self):
        saved = G.core()
        G.set_core_for_test(None, "simulated outage")
        try:
            law = {"id": "l", "name": "P", "template": "protected_resources", "params": {"protectedPaths": ["/config/"]}}
            ev = evaluate_checkpoint(law, {"kind": "write", "path": "/workspace/notes/a.md"}, EvalContext(ResourceRegistry(), lambda d: 0))
            assert ev["result"] == "error" and ev["decision"] == "block"
        finally:
            G.set_core_for_test(*saved)


class TestTranslation:
    def test_demo_requirement(self):
        rules = translate_deterministic("Agents must not claim a task is complete until all required checks pass. Each final research claim must have at least two independent supporting sources. Agents must not make more than three consecutive unsuccessful recovery attempts.")
        assert [r["template"] for r in rules] == ["task_completion", "evidence_requirements", "bounded_retries"]
        assert rules[1]["params"]["minSources"] == 2 and rules[2]["params"]["maxAttempts"] == 3

    def test_ambiguity_is_flagged(self):
        rules = translate_deterministic("Agents must stop after repeated failures. Reports should sound professional.")
        assert rules[0]["template"] == "bounded_retries" and "maxAttempts" not in rules[0]["params"] and rules[0]["issues"]
        assert rules[1]["template"] == "contextual" and rules[1]["enforceability"] == "contextual"

    def test_tool_restriction(self):
        [r] = translate_deterministic("Reviewers must not use Bash or WebFetch.")
        assert r["template"] == "tool_restriction" and r["params"]["blockedTools"] == ["Bash", "WebFetch"]

    def test_conditional_law_ignores_paths_in_the_command(self):
        [r] = translate_deterministic("Agents that modify /repo/sections/ must run node check/section.js before finishing.")
        assert r["params"] == {"whenWrites": ["/repo/sections/"], "whenTools": [], "mustRun": "node check/section.js"}


class TestScope:
    def test_scopes(self):
        assert law_applies_to({}, "agent-001", "lead")
        assert not law_applies_to({"appliesTo": {"roles": ["implementer"]}}, "agent-001", "lead")
        assert law_applies_to({"appliesTo": {"agents": ["agent-007"]}}, "agent-007", "implementer")
        sub = (["agent-002", "alice / test-writer", "alice"], ["test-writer", "implementer"])
        assert law_applies_to({"appliesTo": {"roles": ["implementer"]}}, *sub)
        assert law_applies_to({"appliesTo": {"agents": ["alice"]}}, *sub)
        assert not law_applies_to({"appliesTo": {"roles": ["Explore"]}}, *sub)

    def test_normalize(self):
        assert normalize_scope({"roles": [" ", ""]}) is None
        assert normalize_scope({"roles": [" lead ", "lead"], "agents": []}) == {"roles": ["lead"]}
