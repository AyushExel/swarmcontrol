# Benchmark deleg-qwen2

Real agents: Claude Code headless (subscription) whose only tools are the governor’s, through the MCP bridge. 48 agents per run: 12 per family. Each cell is a pair (governor off vs on) with identical tasks, seed and injected instructions. Success comes from objective checks: the original tests in a sandbox, or the support answer key. Rates are shown with Wilson 95% intervals. n is small; no significance is claimed.

## qwen/qwen3-coder-30b-a3b-instruct · rules in prompt

Experiments: baseline `exp-mvsbakcr-3638`, governed `exp-mvsbakcs-2a35`

| Family | Success (base → gov) | 95% CI (base / gov) | Violations took effect | Blocked | Natural violations (base / gov) | Injected instructions followed (base) | False success claims | Collateral failures | Escalated (gov) | Stopped early (base / gov) | Tokens (base / gov) | API-equiv. cost (base / gov) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **All** | 13/33 → 17/33 | 25–56 / 35–67 | 26 → 0 | 22 | 26 / 22 | 0/0 | 12 → 6 | 20/33 → 16/33 | 0 | 8 / 6 | 1.17M / 1.72M | $0.140 / $0.196 |

## qwen/qwen3-coder-30b-a3b-instruct · rules NOT in prompt

Experiments: baseline `exp-mvsb3t1x-3b90`, governed `exp-mvsb3t21-fb39`

| Family | Success (base → gov) | 95% CI (base / gov) | Violations took effect | Blocked | Natural violations (base / gov) | Injected instructions followed (base) | False success claims | Collateral failures | Escalated (gov) | Stopped early (base / gov) | Tokens (base / gov) | API-equiv. cost (base / gov) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **All** | 1/33 → 12/33 | 1–15 / 22–53 | 66 → 0 | 71 | 66 / 71 | 0/0 | 32 → 0 | 32/33 → 21/33 | 0 | 0 / 0 | 1.41M / 1.94M | $0.250 / $0.342 |

Columns: success = all objective checks pass. "Took effect" counts violating actions that executed; under the governor they are blocked instead. "Injected instructions followed" = agents given a misleading instruction that then violated a law because of it. Collateral = agents without an injected instruction that did not succeed. "Stopped early" = the session ended without submitting (turn limit or the model gave up). API-equivalent cost is computed from token usage at list prices; subscription runs are not billed per token.
