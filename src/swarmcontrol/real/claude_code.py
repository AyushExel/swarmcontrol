"""Is the Claude Code CLI available for the headless backend?"""

from __future__ import annotations

import os
import subprocess

_cached: dict | None = None


def claude_bin() -> str:
    return os.environ.get("CLAUDE_BIN") or "claude"


def claude_code_info() -> dict:
    global _cached
    if _cached is None:
        try:
            v = subprocess.run([claude_bin(), "--version"], capture_output=True, text=True, timeout=10, check=True).stdout.strip()
            _cached = {"ok": True, "version": v}
        except (OSError, subprocess.SubprocessError):
            _cached = {"ok": False, "version": None}
    return _cached


def claude_code_available() -> bool:
    return claude_code_info()["ok"]
