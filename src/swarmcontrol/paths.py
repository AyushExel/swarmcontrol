"""Where things live. Bend sources ship inside the package; builds and scratch work go to a cache folder."""

import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
BEND_DIR = PACKAGE / "bend"
CORE_FILES = ("governor.bend", "LAWS.bend", "PROOF.bend")

CACHE_DIR = Path(os.environ.get("SWARMCONTROL_CACHE", Path.home() / ".cache" / "swarmcontrol"))
BUILD_DIR = CACHE_DIR / "build"  # compiled gate programs (platform-specific)
WORK_DIR = CACHE_DIR / "work"  # throwaway Bend workspaces for law checks

# The event log, laws and experiments (SQLite). Same schema and JSON documents as the earlier TypeScript server, so
# databases recorded with it open unchanged.
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "swarmcontrol"
DEFAULT_DB = Path(os.environ.get("SWARMCONTROL_DB") or DATA_DIR / "swarmcontrol.db")

# Benchmark scenarios (task data, repositories) and the dashboard build ship inside the package
SCENARIOS = PACKAGE / "scenarios"
WEB_DIR = PACKAGE / "web"
