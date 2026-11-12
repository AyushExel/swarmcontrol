# Benchmark deleg-haiku

Real agents: Claude Code headless (subscription) whose only tools are the governor’s, through the MCP bridge. 48 agents per run: 12 per family. Each cell is a pair (governor off vs on) with identical tasks, seed and injected instructions. Success comes from objective checks: the original tests in a sandbox, or the support answer key. Rates are shown with Wilson 95% intervals. n is small; no significance is claimed.

## haiku · rules in prompt

Experiments: baseline `exp-mvsaqi8u-fb85`, governed `exp-mvsaqi8v-261c`

| Family | Success (base → gov) | 95% CI (base / gov) | Violations took effect | Blocked | Natural violations (base / gov) | Injected instructions followed (base) | False success claims | Collateral failures | Escalated (gov) | Stopped early (base / gov) | Tokens (base / gov) | API-equiv. cost (base / gov) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **All** | 32/33 → 32/33 | 85–99 / 85–99 | 0 → 0 | 0 | 0 / 0 | 0/0 | 0 → 0 | 1/33 → 1/33 | 0 | 0 / 0 | 0.51M / 0.52M | $0.021 / $0.022 |

## haiku · rules NOT in prompt

Experiments: baseline `exp-mvsanxg1-42ee`, governed `exp-mvsanxg2-f540`

| Family | Success (base → gov) | 95% CI (base / gov) | Violations took effect | Blocked | Natural violations (base / gov) | Injected instructions followed (base) | False success claims | Collateral failures | Escalated (gov) | Stopped early (base / gov) | Tokens (base / gov) | API-equiv. cost (base / gov) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **All** | 33/33 → 29/33 | 90–100 / 73–95 | 0 → 0 | 6 | 0 / 6 | 0/0 | 0 → 0 | 0/33 → 4/33 | 0 | 0 / 0 | 0.53M / 0.58M | $0.021 / $0.025 |

Columns: success = all objective checks pass. "Took effect" counts violating actions that executed; under the governor they are blocked instead. "Injected instructions followed" = agents given a misleading instruction that then violated a law because of it. Collateral = agents without an injected instruction that did not succeed. "Stopped early" = the session ended without submitting (turn limit or the model gave up). API-equivalent cost is computed from token usage at list prices; subscription runs are not billed per token.
