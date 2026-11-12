# Benchmark dojo-sonnet

Real agents: Claude Code headless (subscription) whose only tools are the governor’s, through the MCP bridge. 48 agents per run: 12 per family. Each cell is a pair (governor off vs on) with identical tasks, seed and injected instructions. Success comes from objective checks: the original tests in a sandbox, or the support answer key. Rates are shown with Wilson 95% intervals. n is small; no significance is claimed.

## anthropic/claude-sonnet-5.5 · rules in prompt

Experiments: baseline `exp-mvrsren1-8e21`, governed `exp-mvrsren4-6af0`

**AgentDojo banking**

| | Benign utility | Utility under attack | Attack success rate | 95% CI (ASR) | Violations took effect | Blocked | Escalated | Tokens | Cost |
|---|---|---|---|---|---|---|---|---|---|
| Governor off | 14/16 (88%) | 144/144 (100%) | 0/144 (0%) | 0–3 | 19 | 0 | 0 | 1.10M | $2.999 |
| Governor on | 14/16 (88%) | 125/144 (87%) | 0/144 (0%) | 0–3 | 0 | 19 | 0 | 1.08M | $2.985 |

Infrastructure errors (baseline / governed): 0 / 0.

Columns: success = all objective checks pass. "Took effect" counts violating actions that executed; under the governor they are blocked instead. "Injected instructions followed" = agents given a misleading instruction that then violated a law because of it. Collateral = agents without an injected instruction that did not succeed. "Stopped early" = the session ended without submitting (turn limit or the model gave up). API-equivalent cost is computed from token usage at list prices; subscription runs are not billed per token.
