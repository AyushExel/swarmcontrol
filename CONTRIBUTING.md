# Contributing

```bash
git clone https://github.com/AyushExel/swarmcontrol.git && cd swarmcontrol
uv venv && uv pip install -e '.[dev]'
npm ci && npm run build       # builds the dashboard into src/swarmcontrol/web (Node ≥ 22.13)
.venv/bin/swctl serve
npm run dev                   # optional: dashboard with hot reload on :5173
.venv/bin/pytest              # needs bend on PATH
```

The server is Python (FastAPI) under `src/swarmcontrol/`; the dashboard is React under `web/`. The Bend gates and their proofs are in `src/swarmcontrol/bend/` (`swctl bend-check` compiles them and checks the proofs).

Benchmarks with real models need a key in `.env` (`OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY`) or a logged-in `claude` CLI. Harness-mode benchmark agents run Claude Code with its permission checks off, so run them in a container or an OS sandbox.

## Adding a law type

A law type turns a family of plain-English rules into a deterministic check. The existing ones are the best guide; `required_reading` is a small, complete example to copy. A new type touches:

1. **`laws/translate.py`**: a pattern that recognizes the rule and extracts its parameters (`structured_for(template, params, …)`). Put specific patterns before general ones.
2. **`bend/adapter.py`**:
   - `applies()`: which checkpoint kinds the law speaks to;
   - `evaluate_checkpoint()`: the decision, made by calling a proven gate in `governor.bend` (reuse `write_gate`, `completion_gate`, `allow_gate`… where you can);
   - `bend_instance_source()`: the Bend law checked for these parameters;
   - `enforcement_for()`, `validate_params()` and `structured_for()`: when it runs, which parameters are required.
3. **`real/runner.py`**: if the law needs memory of earlier actions (what was read, what ran), track it per agent and emit the checkpoint in `_hook_decision`.
4. **`laws/registry.py`**: a short default name for the law.
5. **The dashboard**: the template name in `web/src/shared/types.ts`, and a parameter editor in `ParamsForm` in `web/src/pages/Laws.tsx`.
6. **Tests**: add the plain-English examples to `pytests/test_translate.py`, and an end-to-end case through the hook route in `pytests/test_api.py`.

If the decision needs a new gate function, add it to `bend/governor.bend`, state its properties in `LAWS.bend`, prove them in `PROOF.bend`, and check with `swctl bend-check`.

Ideas that would be welcome: approval before deleting files, limits on the number of files changed, network allowlists, and judgment-based rules checked by a model.
