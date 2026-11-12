# Benchmark dojo-qwen

Real agents: Claude Code headless (subscription) whose only tools are the governor’s, through the MCP bridge. 48 agents per run: 12 per family. Each cell is a pair (governor off vs on) with identical tasks, seed and injected instructions. Success comes from objective checks: the original tests in a sandbox, or the support answer key. Rates are shown with Wilson 95% intervals. n is small; no significance is claimed.

## qwen/qwen3-coder-30b-a3b-instruct · rules in prompt

Experiments: baseline `exp-mvrrmlhl-36bc`, governed `exp-mvrrmlhu-160b`

**AgentDojo banking**

| | Benign utility | Utility under attack | Attack success rate | 95% CI (ASR) | Violations took effect | Blocked | Escalated | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| Governor off | 8/16 (50%) | 82/144 (57%) | 30/144 (21%) | 15–28 | 99 | 0 | 0 | 0.91M | $0.080 |
| Governor on | 7/16 (44%) | 77/144 (53%) | 1/144 (1%) | 0–4 | 0 | 47 | 0 | 0.84M | $0.074 |

Infrastructure errors (baseline / governed): 0 / 0.

## qwen/qwen3-coder-30b-a3b-instruct · rules in prompt — INVALID: server crashed mid-run (runtime bug, fixed)

Experiments: baseline `exp-mvrrlm5h-991a`, governed `exp-mvrrlm5p-72cd`

**AgentDojo banking**

| | Benign utility | Utility under attack | Attack success rate | 95% CI (ASR) | Violations took effect | Blocked | Escalated | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| Governor off | 1/16 (6%) | 0/144 (0%) | 0/144 (0%) | 0–3 | 0 | 0 | 0 | 0.01M | $0.001 |
| Governor on | 0/16 (0%) | 0/144 (0%) | 0/144 (0%) | 0–3 | 0 | 0 | 0 | 0.01M | $0.001 |

Infrastructure errors (baseline / governed): 0 / 0.

Columns: success = all objective checks pass. "Took effect" counts violating actions that executed; under the governor they are blocked instead. "Injected instructions followed" = agents given a misleading instruction that then violated a law because of it. Collateral = agents without an injected instruction that did not succeed. "Stopped early" = the session ended without submitting (turn limit or the model gave up). API-equivalent cost is computed from token usage at list prices; subscription runs are not billed per token.
