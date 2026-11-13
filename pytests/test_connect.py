"""The connect CLI and the Claude Code hook, against stand-in governors (no real server, isolated HOME)."""

import json
import os
import stat
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import swarmcontrol

PKG = Path(swarmcontrol.__file__).parent
TOKEN = "secret-token"


def serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


class StatusOnly(BaseHTTPRequestHandler):
    """/api/status needs the token; /hook.py is public."""

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/api/status":
            ok = self.headers.get("authorization") == f"Bearer {TOKEN}"
            body = json.dumps({"bend": {"proofStatus": "proof_checked"}} if ok else {}).encode()
            self.send_response(200 if ok else 401)
        elif self.path == "/hook.py":
            body = b"# hook"
            self.send_response(200)
        else:
            body = b""
            self.send_response(404)
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def gov():
    srv, url = serve(StatusOnly)
    yield url
    srv.shutdown()


@pytest.fixture()
def sb(tmp_path):
    env = {**os.environ, "HOME": str(tmp_path / "home"), "SWARMCONTROL_HOME": str(tmp_path / "cfg")}

    def cli(*args, check=True):
        r = subprocess.run([sys.executable, "-m", "swarmcontrol.cli", *args], env=env, cwd=tmp_path, capture_output=True, text=True)
        if check and r.returncode:
            raise AssertionError(r.stderr)
        return r

    return tmp_path, cli


def j(p):
    return json.loads(Path(p).read_text())


def test_refuses_missing_or_wrong_token(gov, sb):
    root, cli = sb
    assert "needs an access token" in cli("connect", "--server", gov, "--dir", str(root), check=False).stderr
    assert "rejected this token" in cli("connect", "--server", gov, "--token", "nope", "--dir", str(root), check=False).stderr
    assert not (root / "cfg" / "config.json").exists()


def test_connect_saves_privately_installs_hooks_and_disconnects(gov, sb):
    root, cli = sb
    cli("connect", "claude", "--server", f"{gov}/", "--token", TOKEN, "--dir", str(root), "--agent", "alice", "--observe")
    cfg = root / "cfg" / "config.json"
    assert j(cfg) == {"server": gov, "token": TOKEN}
    assert stat.S_IMODE(cfg.stat().st_mode) == 0o600
    settings = j(root / ".claude" / "settings.local.json")
    assert sorted(settings["hooks"]) == ["PostToolUse", "PreToolUse", "Stop", "SubagentStop"]
    assert settings["env"] == {"SC_AGENT": "alice", "SC_MODE": "observe"}
    assert (root / "cfg" / "swarmcontrol-hook.py").read_text() == (PKG / "hook.py").read_text()
    cli("disconnect", "--dir", str(root))
    assert j(root / ".claude" / "settings.local.json") == {}


def test_team_files_have_no_token_and_teammates_do_not_install_twice(gov, sb):
    root, cli = sb
    cli("connect", "--team", "--server", gov, "--token", TOKEN, "--dir", str(root), "--agent", "carol")
    team = (root / ".claude" / "settings.json").read_text()
    assert "$CLAUDE_PROJECT_DIR/.claude/hooks/swarmcontrol-hook.py" in team
    assert TOKEN not in team and "carol" not in team
    assert (root / ".claude" / "hooks" / "swarmcontrol-hook.py").exists()
    assert "already installed" in cli("connect", "--dir", str(root)).stdout  # server and token come from the saved config


def test_global_writes_user_settings(gov, sb):
    root, cli = sb
    cli("connect", "--global", "--server", gov, "--token", TOKEN)
    assert "PreToolUse" in j(root / "home" / ".claude" / "settings.json")["hooks"]


def test_connect_replaces_an_older_node_hook(gov, sb):
    root, cli = sb
    f = root / ".claude" / "settings.local.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "node ~/.config/swarmcontrol/governor-hook.mjs"}]}]}}))
    cli("connect", "--server", gov, "--token", TOKEN, "--dir", str(root))
    groups = j(f)["hooks"]["PreToolUse"]
    assert len(groups) == 1 and "swarmcontrol-hook.py" in groups[0]["hooks"][0]["command"]


def run_hook(url, payload, home, extra=None):
    env = {**os.environ, "SWARMCONTROL_HOME": str(home), "SC_API": url, **(extra or {})}
    r = subprocess.run([sys.executable, str(PKG / "hook.py")], input=json.dumps(payload), env=env, capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout) if r.stdout else None


def test_hook_holds_an_escalated_stop_until_a_human_decides(tmp_path):
    seen = {"polls": 0, "body": None}

    class Gov(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, obj):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(obj).encode())

        def do_POST(self):
            seen["body"] = json.loads(self.rfile.read(int(self.headers["content-length"])))
            self.reply({"governorWait": {"experiment": "e1", "agent": "a1"}})

        def do_GET(self):
            seen["polls"] += 1
            self.reply({"decided": False} if seen["polls"] < 2 else {"decided": True, "action": "retry_with_guidance", "note": "fix src only."})

    srv, url = serve(Gov)
    out = run_hook(url, {"hook_event_name": "Stop", "session_id": "s", "cwd": str(tmp_path)}, tmp_path)
    srv.shutdown()
    assert seen["body"]["identity"]["canWait"] is True
    assert out["decision"] == "block" and "fix src only." in out["reason"]
    assert "governorWait" not in out
    assert seen["polls"] == 2


def test_hook_fails_closed_when_the_governor_is_unreachable(tmp_path):
    out = run_hook("http://127.0.0.1:9", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(tmp_path)}, tmp_path)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert run_hook("http://127.0.0.1:9", {"hook_event_name": "PreToolUse", "cwd": str(tmp_path)}, tmp_path, {"SC_FAIL_OPEN": "1"}) is None


def test_connect_starts_a_local_server_and_the_hook_restarts_it(sb):
    """No server running: connect starts one in the background; after `swctl stop`, the next hook call starts it again."""
    import socket
    import urllib.request

    root, cli = sb
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    cfg = root / "cfg"
    try:
        r = cli("connect", "--server", url, "--dir", str(root))
        assert "started SwarmControl" in r.stdout and "connected to" in r.stdout
        assert j(cfg / "config.json")["autostart"] is True
        assert "proof" in urllib.request.urlopen(f"{url}/api/status", timeout=10).read().decode()

        assert "stopped the background server" in cli("stop").stdout
        for _ in range(50):  # wait for the port to close
            try:
                urllib.request.urlopen(f"{url}/api/status", timeout=1)
            except OSError:
                break
            __import__("time").sleep(0.2)
        env = {**os.environ, "HOME": str(root / "home"), "SWARMCONTROL_HOME": str(cfg)}
        env.pop("SC_API", None)
        out = subprocess.run([sys.executable, str(PKG / "hook.py")], env=env, capture_output=True, text=True, timeout=90,
                             input=json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "x"}, "cwd": str(root), "session_id": "s"}))
        assert "unreachable" not in out.stdout
        urllib.request.urlopen(f"{url}/api/status", timeout=10)
    finally:
        cli("stop", check=False)
