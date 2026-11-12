"""The Python reducer (reports, summaries) must give the same numbers as the dashboard's TypeScript reducer: on fresh
simulator runs, and on any recorded databases in data/."""

import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from conftest import needs_bend
from swarmcontrol.experiments import build_config
from swarmcontrol.laws.registry import init_laws
from swarmcontrol.metrics import replay
from swarmcontrol.runtime.simulator import ExperimentRunner

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TSX = ROOT / "node_modules" / ".bin" / "tsx"


def recorded_runs(per_db: int = 6) -> dict[str, list[dict]]:
    runs: dict[str, list[dict]] = {}
    for db in sorted(DATA.glob("*.db")):
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            ids = [r[0] for r in con.execute("SELECT experiment_id, COUNT(*) n FROM events GROUP BY experiment_id ORDER BY n DESC LIMIT ?", (per_db,))]
            for i in ids:
                runs[f"{db.name}:{i}"] = [json.loads(r[0]) for r in con.execute("SELECT doc FROM events WHERE experiment_id = ? ORDER BY seq", (i,))]
        except sqlite3.DatabaseError:
            pass
        finally:
            con.close()
    return runs


def close(a, b, path=""):
    if isinstance(a, float) or isinstance(b, float):
        assert a == pytest.approx(b, rel=1e-9, abs=1e-9), path
    elif isinstance(a, dict):
        assert set(a) == set(b), f"{path}: keys {set(a) ^ set(b)}"
        for k in a:
            close(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), f"{path}: length {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            close(x, y, f"{path}[{i}]")
    else:
        assert a == b, f"{path}: {a!r} vs {b!r}"


def simulated_runs() -> dict[str, list[dict]]:
    runs = {}
    for k, inp in enumerate([{"swarmSize": 50, "seed": 3, "governor": True}, {"swarmSize": 50, "seed": 3, "governor": False},
                             {"swarmSize": 100, "seed": 8, "governor": True, "horizon": "long"}, {"swarmSize": 50, "seed": 8, "governor": False, "horizon": "long"}]):
        cfg = build_config({"speed": 0, **inp})
        events: list[dict] = []
        ExperimentRunner({"id": f"exp-sim-{k}", "config": cfg, "mode": cfg["mode"], "seed": cfg["seed"], "status": "running"}, events.extend, lambda e: None).run()
        runs[f"simulated:{k}"] = events
    return runs


@needs_bend
@pytest.mark.skipif(not TSX.exists() or not shutil.which("node"), reason="needs node and the dashboard's node_modules")
def test_same_metrics_as_the_dashboard(fresh_store):
    init_laws()
    runs = {**simulated_runs(), **recorded_runs()}
    ts = json.loads(subprocess.run([str(TSX), str(Path(__file__).parent / "ts_replay.ts")], input=json.dumps(runs), capture_output=True, text=True, check=True, cwd=ROOT).stdout)
    for run_id, events in runs.items():
        snap = replay(events)
        py = {"metrics": snap["metrics"], "timeline": snap["timeline"],
              "agents": [{k: a[k] for k in ("id", "state", "health", "recovered", "outcome")} for a in snap["agents"].values()]}
        close(py, ts[run_id], run_id)
    print(f"{len(runs)} recorded runs, {sum(map(len, runs.values()))} events compared")
