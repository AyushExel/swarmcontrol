# Contributing

```bash
git clone https://github.com/AyushExel/swarmcontrol.git && cd swarmcontrol
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
npm ci && npm run build       # builds the dashboard into src/swarmcontrol/web (Node ≥ 22.13)
.venv/bin/swctl serve
npm run dev                   # optional: dashboard with hot reload on :5173
.venv/bin/pytest              # needs bend on PATH
```

The server is Python (FastAPI) under `src/swarmcontrol/`; the dashboard is React under `web/`. The Bend gates and their proofs are in `src/swarmcontrol/bend/` (`swctl bend-check` compiles them and checks the proofs).

Benchmarks with real models need a key in `.env` (`OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY`) or a logged-in `claude` CLI. Harness-mode benchmark agents run Claude Code with its permission checks off, so run them in a container or an OS sandbox.
