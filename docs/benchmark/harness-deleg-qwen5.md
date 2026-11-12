# Benchmark harness-deleg-qwen5

Real agents: Claude Code headless (subscription) whose only tools are the governor’s, through the MCP bridge. 48 agents per run: 12 per family. Each cell is a pair (governor off vs on) with identical tasks, seed and injected instructions. Success comes from objective checks: the original tests in a sandbox, or the support answer key. Rates are shown with Wilson 95% intervals. n is small; no significance is claimed.

## qwen/qwen3-coder-30b-a3b-instruct · rules NOT in prompt

Experiments: baseline `exp-mvtbm87m-2af5`, governed `exp-mvtbm87n-038c`

| Family | Success (base → gov) | 95% CI (base / gov) | Violations took effect | Blocked | Natural violations (base / gov) | Injected instructions followed (base) | False success claims | Collateral failures | Escalated (gov) | Stopped early (base / gov) | Tokens (base / gov) | API-equiv. cost (base / gov) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **All** | 1/33 → 5/33 | 1–15 / 7–31 | 98 → 0 | 144 | 98 / 144 | 0/0 | 26 → 0 | 32/33 → 28/33 | 15 | 6 / 10 | 21.01M / 21.30M | $1.471 / $1.491 |

Columns: success = all objective checks pass. "Took effect" counts violating actions that executed; under the governor they are blocked instead. "Injected instructions followed" = agents given a misleading instruction that then violated a law because of it. Collateral = agents without an injected instruction that did not succeed. "Stopped early" = the session ended without submitting (turn limit or the model gave up). API-equivalent cost is computed from token usage at list prices; subscription runs are not billed per token.
