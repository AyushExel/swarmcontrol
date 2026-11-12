# Sanity check: does the governor hold up inside a real agent harness?

*October 2026 · not part of the headline results · Qwen 3 Coder 30B-A3B only*

The headline benchmarks ran the model in a bare tool loop. Here we reran the two long-horizon headlines with the same model inside **Claude Code**, unmodified: its own system prompt, its built-in tools (Read, Edit, Write, Bash, subagents…) and its own loop. The governor plugged in the way a user would install it, through Claude Code's hooks (then `integrations/claude-code/governor-hook.mjs`; now `src/swarmcontrol/hook.py`, same protocol) plus MCP for the domain tools.

## Results

**Delegated team** (1 lead + 32 engineers, HumanEval tickets, half impossible, rules only in the governor):

| | Bare loop: off → on | Inside Claude Code: off → on |
|---|---|---|
| False "done" claims | 32 → **0** | 26 → **0** |
| Tickets with QA's tests edited | 31 → **0** | 28 → **0** |
| Violations that took effect | 66 → **0** | 98 → **0** |
| Impossible tickets handled honestly | 0 → **16** / 16 | 0 → **11** / 16 |
| Possible tickets done | 0 → 1 / 16 | 0 → 1 / 16 |

**Ops shift** (32 agents × ~10 τ² customers on shared live databases), compared on the 310 customers both arms finished:

| | Bare loop: off → on | Inside Claude Code: off → on |
|---|---|---|
| Customers resolved | 52% → **62%** (328 each) | 18% → **22%** (56 → 69 of 310) |
| Policy violations that hit the database | 63 → **0** | 23 → **0** |

## What this says

- **The value proposition holds.** In the harness, as in the bare loop, no violation took effect under the governor, false "done" claims went to zero, and success rose.
- **The harness hurts the small open model more than anything else.** Qwen resolves 18–22% of customers inside Claude Code versus 52–62% in a bare loop. Claude Code's large prompt and toolset are built for Claude.
- **The harness adds a new kind of deviation.** With Claude Code's tools, the Qwen lead sometimes skipped delegation: it wrote code itself or spawned its own subagents, leaving the team idle. A role-scoped law ("the lead delegates, never changes files") caught it. Its first block message only said "path protected", the lead didn't recover, and the whole team waited on a human. Feedback that names the allowed action ("assign each ticket") fixed that.

## How it was run (differences from the bare loop)

- Claude Code headless, with the model routed through OpenRouter's Anthropic-compatible API via a local proxy (then `server/src/real/or-proxy.ts`; now `src/swarmcontrol/real/or_proxy.py`). The proxy pins the inference provider (Amazon Bedrock) and repairs replies where the model wrote a tool call in its native text format (`<function=…>`), as Qwen's own harness does. Under 1% of replies needed it (e.g. 4 of 1,373).
- Both arms ran in the same workspace sandbox (no file or shell access outside the agent's workspace), enforced as infrastructure, not as a law.
- The ops shift resumes one Claude Code session per agent for every customer message (in τ² the agent's text is its message to the customer).

## Run notes (including the runs that didn't count)

- **Delegated team, final pair:** `harness-deleg-qwen5` (seed 8), graded in [`harness-delegated-qwen5-graded.md`](benchmark/harness-delegated-qwen5-graded.md). Earlier pairs:
  - `harness-deleg-qwen`: the lead's block message didn't name `assign`, so the lead escalated and the team stalled.
  - `harness-deleg-qwen2`: a runner deadlock (escalated agents held worker slots), since fixed.
  - `harness-deleg-qwen4`: the baseline lead's first reply was a hallucinated system note, so Claude Code ended the session at once.
- **Ops shift:** `harness-shift-qwen`. The last few customers hit the API key's spending limit and are excluded from both arms. The simulated customer timed out on 13 baseline and 6 governed conversations; those count as unresolved.
- Total OpenRouter spend for the harness checks: about $35.
