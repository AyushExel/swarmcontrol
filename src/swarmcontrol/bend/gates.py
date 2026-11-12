"""Calls the proven gate functions. The decisions come from governor.bend compiled into a native program
(gates.bend is its command-line driver), so the code that enforces a law is the code the proofs are about."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

Decision = str  # "allow" | "block" | "escalate"


class GateError(Exception):
    pass


def _nats(xs: list[int]) -> str:
    return ",".join(str(int(x)) for x in xs) if xs else "-"


def run_gate(cmd: list[str], args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([*cmd, *args], capture_output=True, text=True, timeout=10, cwd=cwd, env={**os.environ, "BEND_NO_TELEMETRY": "1", "NO_COLOR": "1"})


class CoreGates:
    """One short-lived process per check: the compiled program (about 1.5 ms), or `bend gates.bend` running the same
    program interpreted when clang isn't installed (about 100 ms)."""

    def __init__(self, cmd: list[str], cwd: Path | None = None):
        self.cmd = cmd
        self.cwd = cwd

    def _call(self, gate: str, *args: str) -> Decision:
        p = run_gate(self.cmd, [gate, *args], self.cwd)
        out = p.stdout.strip()
        if p.returncode != 0 or out not in ("allow", "block", "escalate"):
            raise GateError(f"{gate} answered {out!r} (exit {p.returncode}) {p.stderr.strip()[:200]}")
        return out

    def write_gate(self, r: int, ps: list[int]) -> Decision:
        return self._call("write_gate", str(r), _nats(ps))

    def allow_gate(self, r: int, xs: list[int]) -> Decision:
        return self._call("allow_gate", str(r), _nats(xs))

    def evidence_gate(self, minimum: int, ds: list[int]) -> Decision:
        return self._call("evidence_gate", str(minimum), _nats(ds))

    def retry_gate(self, attempts: int, maximum: int) -> Decision:
        return self._call("retry_gate", str(attempts), str(maximum))

    def spend_gate(self, amount: int, cap: int) -> Decision:
        return self._call("spend_gate", str(amount), str(cap))

    def completion_gate(self, checks: list[bool]) -> Decision:
        return self._call("completion_gate", ",".join("1" if c else "0" for c in checks) if checks else "-")


_core: CoreGates | None = None
_core_error: str | None = "gates not loaded yet"


def load_core_gates() -> CoreGates | None:
    global _core, _core_error
    from ..paths import BEND_DIR
    from .toolchain import find_bend, gates_binary

    b = gates_binary()
    meta_path = b.parent / "gates.meta.json"
    mode = json.loads(meta_path.read_text()).get("mode", "native") if meta_path.exists() else None
    bend = find_bend()
    if mode == "interpreted" and bend:
        _core, _core_error = CoreGates([bend, str(BEND_DIR / "gates.bend"), "--"], BEND_DIR), None  # "--": "-" (empty list) is an argument, not a bend option
    elif b.exists():
        _core, _core_error = CoreGates([str(b)]), None
    else:
        _core, _core_error = None, "the gate program is not built (Bend toolchain missing?)"
    return _core


def core() -> tuple[CoreGates | None, str | None]:
    return _core, _core_error


def set_core_for_test(g: CoreGates | None, err: str | None = None) -> None:
    """Simulate an evaluator outage: the runtime must fail closed."""
    global _core, _core_error
    _core, _core_error = g, err


# user-written Bend laws with a `def gate(c: G.Checkpoint) -> G.Decision`, compiled to their own program
CustomGate = Callable[[str, str], Decision]
custom_gates: dict[str, CustomGate] = {}
