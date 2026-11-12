"""Thin wrapper around the real `bend` CLI (Bend 2.x). Nothing here simulates Bend: if the binary is missing,
every check reports `unavailable` and enforcement fails closed."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..paths import BEND_DIR, BUILD_DIR, CORE_FILES, WORK_DIR

INSTALL_HINT = "Install it with: curl -fsSL https://bend-lang.com/install.sh | sh"
_bend_path: str | None | bool = False  # False = not looked up yet


def find_bend() -> str | None:
    global _bend_path
    if _bend_path is not False:
        return _bend_path  # type: ignore[return-value]
    candidates = [os.environ.get("BEND_BIN"), str(Path.home() / ".bend/bin/bend")]
    found = next((c for c in candidates if c and Path(c).exists()), None) or shutil.which("bend")
    _bend_path = found
    return found


@dataclass
class BendRun:
    code: int
    output: str
    ms: int


def run_bend(args: list[str], cwd: Path, timeout: float = 60) -> BendRun:
    binary = find_bend()
    if not binary:
        return BendRun(127, "bend: toolchain not found", 0)
    t0 = time.perf_counter()
    try:
        p = subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "BEND_NO_TELEMETRY": "1", "NO_COLOR": "1"})
        code, out = p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        code, out = 124, f"{e.stdout or ''}{e.stderr or ''}\nbend: timed out after {timeout}s"
    return BendRun(code, re.sub(r"\x1b\[[0-9;]*m", "", out).strip(), round((time.perf_counter() - t0) * 1000))


def bend_version() -> str | None:
    if not find_bend():
        return None
    r = run_bend(["version"], BEND_DIR, 10)
    return r.output.strip() if r.code == 0 else None


def classify(run: BendRun) -> str:
    """ALL PROOFS CHECK with exit 0 -> proof_checked; "N TODO found" -> stated; otherwise error."""
    if run.code == 127:
        return "unavailable"
    if run.code == 0 and "ALL PROOFS CHECK" in run.output:
        return "proof_checked"
    if re.search(r"\d+ TODOs? found", run.output) and not re.search(r"expected\s*:", run.output):
        return "stated"
    return "error"


def sha(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode())
    return h.hexdigest()[:16]


def core_source_hash() -> str:
    return sha(*((BEND_DIR / f).read_text() for f in CORE_FILES))


def workspace(name: str, files: dict[str, str]) -> Path:
    """A fresh folder holding copies of the core Bend files plus `files`."""
    d = WORK_DIR / name
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    for f in CORE_FILES:
        shutil.copyfile(BEND_DIR / f, d / f)
    for f, src in files.items():
        (d / f).write_text(src)
    return d


def top_level_blocks(src: str) -> list[dict[str, str]]:
    """Split a Bend source into top-level blocks, keeping leading comments attached."""
    blocks: list[dict[str, str]] = []
    pending: list[str] = []
    cur: list[str] | None = None

    def flush() -> None:
        nonlocal cur
        if cur is not None:
            header = next((l for l in cur if not l.startswith("#")), "")
            blocks.append({"header": header, "text": "\n".join(cur)})
        cur = None

    for line in src.split("\n"):
        top = bool(line) and not line[0].isspace()
        if top and line.startswith("#"):
            flush()
            pending.append(line)
        elif top:
            flush()
            cur = [*pending, line]
            pending = []
        elif cur is not None:
            cur.append(line)
        elif line.strip() == "":
            pending = []
    flush()
    return blocks


def extract_laws(src: str) -> list[dict[str, str]]:
    """Top-level `law` blocks (name + full text) of a Bend source."""
    out = []
    for b in top_level_blocks(src):
        m = re.match(r"^law\s+([\w.]+)\s*:", b["header"])
        if m:
            out.append({"name": m.group(1), "statement": b["text"].rstrip()})
    return out


@dataclass
class CoreStatus:
    bendVersion: str | None
    sourceHash: str
    proofStatus: str
    proofOutput: str
    checkedAt: int
    checkMs: int
    moduleBuiltFromHash: str | None
    moduleBuiltAt: int | None
    laws: list[dict[str, str]] = field(default_factory=list)
    # "native": a compiled program (needs clang 14+); "interpreted": `bend gates.bend …` runs the same program, slower
    gatesMode: str | None = None


def gates_binary() -> Path:
    return BUILD_DIR / "gates"


def needs_clang(output: str) -> bool:
    """Bend builds binaries through clang; without it, programs still run interpreted."""
    return "needs clang" in output


def build_program(src: str, out: Path, cwd: Path) -> tuple[str, str]:
    """Compile a Bend program to a native binary. Returns ("native" | "interpreted" | "failed", output): interpreted
    means clang is missing, so the caller runs `bend <src> …` instead."""
    r = run_bend([src, "-o", str(out)], cwd, 300)
    if r.code == 0 and out.exists():
        return "native", r.output
    if needs_clang(r.output):
        out.unlink(missing_ok=True)
        return "interpreted", r.output
    return "failed", r.output


def build_and_check_core() -> CoreStatus:
    """Compile the gate program from governor.bend (via gates.bend), then run the proofs over the same sources.
    The status records the hash both steps saw, so a proof result is never attached to stale code."""
    source_hash = sha(core_source_hash(), (BEND_DIR / "gates.bend").read_text())
    version = bend_version()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = BUILD_DIR / "gates.meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else None
    status = CoreStatus(
        bendVersion=version, sourceHash=source_hash, proofStatus="unavailable",
        proofOutput=f"Bend toolchain not found. {INSTALL_HINT}", checkedAt=int(time.time() * 1000), checkMs=0,
        moduleBuiltFromHash=meta and meta.get("sourceHash"), moduleBuiltAt=meta and meta.get("builtAt"),
        laws=extract_laws((BEND_DIR / "LAWS.bend").read_text()),
    )
    if not version:
        return status
    mode = (meta or {}).get("mode", "native")
    stale = not meta or meta.get("sourceHash") != source_hash or meta.get("bendVersion", version) != version
    if stale or (mode == "native" and not gates_binary().exists()) or (mode == "interpreted" and shutil.which("clang")):
        mode, output = build_program("gates.bend", gates_binary(), BEND_DIR)
        if mode == "failed":
            raise RuntimeError(f"bend failed to compile the gates:\n{output}")
        meta = {"sourceHash": source_hash, "builtAt": int(time.time() * 1000), "mode": mode, "bendVersion": version}
        meta_path.write_text(json.dumps(meta, indent=2))
        status.moduleBuiltFromHash, status.moduleBuiltAt = source_hash, meta["builtAt"]
    status.gatesMode = mode
    r = run_bend(["PROOF.bend"], BEND_DIR, 300)
    c = classify(r)
    status.proofStatus = "proof_checked" if c == "proof_checked" else "stated" if c == "stated" else "proof_failed"
    status.proofOutput, status.checkMs, status.checkedAt = r.output, r.ms, int(time.time() * 1000)
    return status
