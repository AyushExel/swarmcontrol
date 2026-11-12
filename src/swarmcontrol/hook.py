#!/usr/bin/env python3
"""SwarmControl hook for Claude Code (standard library only; Python 3.8+). Install it with `swctl connect`.

Claude Code runs this on PreToolUse, PostToolUse, Stop and SubagentStop. It forwards the event to the governor, which
checks the agent's laws and answers allow, deny (with corrective feedback) or "keep working".

Configure per session with environment variables (all optional):
  SC_API         governor URL (default http://localhost:8787)
  SC_PROJECT     experiment to report into (default: the project folder name)
  SC_ROLE        this agent's role, for role-scoped laws (default "agent")
  SC_AGENT       a display name for this agent (default: the session id)
  SC_OWNS        comma-separated files or folders (ending in /) this agent may change, e.g. "src/api/"
  SC_DONE_CHECK  a command that must pass before the agent may stop as done, e.g. "npm test"
  SC_MODE        "enforce" (default) or "observe" (record what would be blocked, block nothing)
  SC_FAIL_OPEN   "1" to allow actions when the governor is unreachable (default: fail closed)
  SC_API_TOKEN   the governor's access token, when it runs with SWARMCONTROL_TOKEN (self-hosted)
  SC_HUMAN_WAIT  seconds a stopping session waits for a human decision after escalating (default 3000; 0 = don't wait)
SC_API and SC_API_TOKEN default to what `swctl connect` saved in ~/.config/swarmcontrol/config.json."""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

env = os.environ
HOME = env.get("SWARMCONTROL_HOME") or os.path.join(os.path.expanduser("~"), ".config", "swarmcontrol")
try:
    with open(os.path.join(HOME, "config.json")) as f:
        saved = json.load(f)
except (OSError, ValueError):
    saved = {}  # not connected with the CLI: env vars or defaults
api = env.get("SC_API") or saved.get("server") or "http://localhost:8787"
api_token = env.get("SC_API_TOKEN") or saved.get("token") or ""

try:
    payload = json.loads(sys.stdin.read())
except ValueError:
    sys.exit(0)
event = payload.get("hook_event_name")

done_check = None
if event == "Stop" and env.get("SC_DONE_CHECK") and not env.get("SC_EXP"):
    try:
        r = subprocess.run(env["SC_DONE_CHECK"], shell=True, cwd=payload.get("cwd") or None, stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=600)
        out = (r.stdout or "") + ("" if r.returncode == 0 else (r.stderr or ""))
        done_check = {"ok": r.returncode == 0, "output": out[-4000:] or ("" if r.returncode == 0 else f"exit code {r.returncode}")}
    except subprocess.TimeoutExpired:
        done_check = {"ok": False, "output": "the done check timed out after 600s"}

# benchmark agents identify by experiment and agent id; user sessions by project, role and name
headers = {"content-type": "application/json"}
if api_token:
    headers["authorization"] = f"Bearer {api_token}"
if env.get("SC_EXP"):
    headers.update({"x-sc-exp": env["SC_EXP"], "x-sc-agent": env.get("SC_AGENT", ""), "x-sc-token": env.get("SC_TOKEN", "")})
wait_seconds = float(env.get("SC_HUMAN_WAIT") or 3000)
identity = {"project": env.get("SC_PROJECT") or os.path.basename(payload.get("cwd") or os.getcwd()), "role": env.get("SC_ROLE"),
            "agent": env.get("SC_AGENT"), "owns": env.get("SC_OWNS"), "mode": env.get("SC_MODE"), "canWait": wait_seconds > 0}


def call(path, body=None, timeout=3700):
    req = urllib.request.Request(api + path, data=None if body is None else json.dumps(body).encode(), headers=headers,
                                 method="GET" if body is None else "POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error")
        except ValueError:
            msg = None
        raise RuntimeError(msg or f"HTTP {e.code}")


def wait_for_human(experiment, agent):
    """The session escalated while stopping: keep it open until a human decides on the dashboard, then send it back."""
    deadline = time.time() + wait_seconds
    failures = 0
    while time.time() < deadline:
        time.sleep(2)
        try:
            d = call(f"/api/attach/{experiment}/agents/{agent}/decision", timeout=30)
        except Exception:
            failures += 1
            if failures >= 15:
                return {}
            continue
        failures = 0
        if not d.get("decided"):
            continue
        if d.get("action") == "retry_with_guidance":
            return {"decision": "block", "reason": f"A human reviewer approved you to continue. Their guidance: {d.get('note')} Follow it, then finish."}
        return {}
    return {}  # nobody decided in time: let the session stop; an approval then needs a message in the terminal


try:
    out = call("/api/hooks/claude-code", {"payload": payload, "identity": identity, "doneCheck": done_check})
    wait = out.pop("governorWait", None)
    if wait:
        out.update(wait_for_human(wait["experiment"], wait["agent"]))
    sys.stdout.write(json.dumps(out))
except Exception as e:  # noqa: BLE001 - any failure to reach the governor
    if env.get("SC_FAIL_OPEN") == "1" or event != "PreToolUse":
        sys.exit(0)
    # fail closed: nothing executes while the governor is unreachable
    reason = getattr(e, "reason", None) or e
    sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                        "permissionDecisionReason": f"SwarmControl unreachable at {api} ({reason}); action not executed."}}))
