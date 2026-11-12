import os
import tempfile

import pytest

# isolate every test run: in-memory database, private cache for builds and Bend workspaces
os.environ.setdefault("SWARMCONTROL_CACHE", tempfile.mkdtemp(prefix="sg-test-cache-"))
os.environ["SWARMCONTROL_DB"] = ":memory:"

from swarmcontrol.bend import gates  # noqa: E402
from swarmcontrol.bend.toolchain import build_and_check_core, find_bend  # noqa: E402
from swarmcontrol.store import Store, use_store  # noqa: E402

HAS_BEND = bool(find_bend())
needs_bend = pytest.mark.skipif(not HAS_BEND, reason="Bend toolchain not installed")


@pytest.fixture(scope="session", autouse=True)
def core():
    status = build_and_check_core() if HAS_BEND else None
    gates.load_core_gates()
    return status


@pytest.fixture()
def fresh_store():
    return use_store(Store(":memory:"))
