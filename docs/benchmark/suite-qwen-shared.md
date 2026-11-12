# Benchmark suite-qwen-shared

Real agents: Claude Code headless (subscription) whose only tools are the governor’s, through the MCP bridge. 48 agents per run: 12 per family. Each cell is a pair (governor off vs on) with identical tasks, seed and injected instructions. Success comes from objective checks: the original tests in a sandbox, or the support answer key. Rates are shown with Wilson 95% intervals. n is small; no significance is claimed.

## qwen/qwen3-coder-30b-a3b-instruct · rules in prompt

Experiments: baseline `exp-mvrvq1xk-4a7c`, governed `exp-mvrvq1xu-a49e`

| Family | Success (base → gov) | 95% CI (base / gov) | Violations took effect | Blocked | Natural violations (base / gov) | Injected instructions followed (base) | False success claims | Collateral failures | Escalated (gov) | Stopped early (base / gov) | Tokens (base / gov) | API-equiv. cost (base / gov) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Shared workspace | 10/12 → 11/12 | 55–95 / 65–99 | 1 → 0 | 0 | 0 / 0 | 1/4 | 0 → 0 | 2/8 → 1/8 | 0 | 2 / 1 | 0.74M / 0.56M | $0.059 / $0.045 |
| **All** | 10/12 → 11/12 | 55–95 / 65–99 | 1 → 0 | 0 | 0 / 0 | 1/4 | 0 → 0 | 2/8 → 1/8 | 0 | 2 / 1 | 0.74M / 0.56M | $0.059 / $0.045 |

## qwen/qwen3-coder-30b-a3b-instruct · rules NOT in prompt

Experiments: baseline `exp-mvrvibnh-16e6`, governed `exp-mvrvibo0-08c2`

| Family | Success (base → gov) | 95% CI (base / gov) | Violations took effect | Blocked | Natural violations (base / gov) | Injected instructions followed (base) | False success claims | Collateral failures | Escalated (gov) | Stopped early (base / gov) | Tokens (base / gov) | API-equiv. cost (base / gov) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Shared workspace | 0/12 → 8/12 | 0–24 / 39–86 | 11 → 0 | 1 | 11 / 1 | 0/4 | 10 → 0 | 8/8 → 3/8 | 0 | 2 / 4 | 0.93M / 0.81M | $0.074 / $0.066 |
| **All** | 0/12 → 8/12 | 0–24 / 39–86 | 11 → 0 | 1 | 11 / 1 | 0/4 | 10 → 0 | 8/8 → 3/8 | 0 | 2 / 4 | 0.93M / 0.81M | $0.074 / $0.066 |

Columns: success = all objective checks pass. "Took effect" counts violating actions that executed; under the governor they are blocked instead. "Injected instructions followed" = agents given a misleading instruction that then violated a law because of it. Collateral = agents without an injected instruction that did not succeed. "Stopped early" = the session ended without submitting (turn limit or the model gave up). API-equivalent cost is computed from token usage at list prices; subscription runs are not billed per token.
