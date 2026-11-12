# Benchmark dojo-haiku

Real agents: Claude Code headless (subscription) whose only tools are the governor’s, through the MCP bridge. 48 agents per run: 12 per family. Each cell is a pair (governor off vs on) with identical tasks, seed and injected instructions. Success comes from objective checks: the original tests in a sandbox, or the support answer key. Rates are shown with Wilson 95% intervals. n is small; no significance is claimed.

## anthropic/claude-haiku-5.5 · rules in prompt

Experiments: baseline `exp-mvrsrem0-7141`, governed `exp-mvrsrem4-8f78`

**AgentDojo banking**

| | Benign utility | Utility under attack | Attack success rate | 95% CI (ASR) | Violations took effect | Blocked | Escalated | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| Governor off | 12/16 (75%) | 98/144 (68%) | 0/144 (0%) | 0–3 | 4 | 0 | 0 | 1.08M | $0.171 |
| Governor on | 11/16 (69%) | 96/144 (67%) | 0/144 (0%) | 0–3 | 0 | 8 | 0 | 1.14M | $0.179 |

Infrastructure errors (baseline / governed): 0 / 0.

Columns: success = all objective checks pass. "Took effect" counts violating actions that executed; under the governor they are blocked instead. "Injected instructions followed" = agents given a misleading instruction that then violated a law because of it. Collateral = agents without an injected instruction that did not succeed. "Stopped early" = the session ended without submitting (turn limit or the model gave up). API-equivalent cost is computed from token usage at list prices; subscription runs are not billed per token.
