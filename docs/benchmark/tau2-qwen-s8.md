# Benchmark tau2-qwen-s8

Real agents: Claude Code headless (subscription) whose only tools are the governor’s, through the MCP bridge. 48 agents per run: 12 per family. Each cell is a pair (governor off vs on) with identical tasks, seed and injected instructions. Success comes from objective checks: the original tests in a sandbox, or the support answer key. Rates are shown with Wilson 95% intervals. n is small; no significance is claimed.

## qwen/qwen3-coder-30b-a3b-instruct · rules in prompt

Experiments: baseline `exp-mvs1mrkt-3ef0`, governed `exp-mvs1mrsq-0b61`

| Family | Success (base → gov) | 95% CI (base / gov) | Violations took effect | Blocked | Natural violations (base / gov) | Injected instructions followed (base) | False success claims | Collateral failures | Escalated (gov) | Stopped early (base / gov) | Tokens (base / gov) | API-equiv. cost (base / gov) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **All** | 21/50 → 27/50 | 29–56 / 40–67 | 11 → 0 | 15 | 11 / 15 | 0/0 | 0 → 0 | 29/50 → 23/50 | 0 | 0 / 0 | 4.72M / 4.56M | $0.353 / $0.343 |

## qwen/qwen3-coder-30b-a3b-instruct · rules in prompt

Experiments: baseline `exp-mvs1f779-8d50`, governed `exp-mvs1f7dn-f2f3`

| Family | Success (base → gov) | 95% CI (base / gov) | Violations took effect | Blocked | Natural violations (base / gov) | Injected instructions followed (base) | False success claims | Collateral failures | Escalated (gov) | Stopped early (base / gov) | Tokens (base / gov) | API-equiv. cost (base / gov) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **All** | 20/50 → 28/50 | 28–54 / 42–69 | 19 → 0 | 8 | 19 / 8 | 0/0 | 0 → 0 | 30/50 → 22/50 | 0 | 0 / 0 | 4.24M / 4.52M | $0.309 / $0.329 |

Columns: success = all objective checks pass. "Took effect" counts violating actions that executed; under the governor they are blocked instead. "Injected instructions followed" = agents given a misleading instruction that then violated a law because of it. Collateral = agents without an injected instruction that did not succeed. "Stopped early" = the session ended without submitting (turn limit or the model gave up). API-equivalent cost is computed from token usage at list prices; subscription runs are not billed per token.
