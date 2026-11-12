#!/usr/bin/env python3
"""Creates the board-plan demo: python3 tutorials/board-plan/setup.py [target dir] [--server URL] [--token T]

Copies the template project, makes it a git repository, connects it to the governor (`swctl connect`) and
adds the demo's laws. Needs the governor running and `swctl` installed."""

import argparse
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

here = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument("target", nargs="?", default=str(Path.home() / "board-plan"))
p.add_argument("--server", default="http://localhost:8787")
p.add_argument("--token")
a = p.parse_args()
target = Path(a.target).resolve()
server = a.server.rstrip("/")
if target.exists():
    raise SystemExit(f"{target} already exists; remove it or pick another folder")

shutil.copytree(here / "template", target)
git = lambda *args: subprocess.run(["git", *args], cwd=target, check=True, capture_output=True)  # noqa: E731
git("init", "-q")
git("add", "-A")
git("-c", "user.name=demo", "-c", "user.email=demo@example.com", "commit", "-qm", "start")
subprocess.run(["swarmcontrol", "connect", "--dir", str(target), "--server", server, *(["--token", a.token] if a.token else []),
                "--role", "orchestrator", "--agent", "plan-team", "--done-check", "node check/all.js"], check=True)


def post(path: str, body: dict):
    headers = {"content-type": "application/json", **({"authorization": f"Bearer {a.token}"} if a.token else {})}
    req = urllib.request.Request(server + path, data=json.dumps(body).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


for law in json.loads((here / "laws.json").read_text()):
    roles = law.get("roles")
    rules = post("/api/laws/translate", {"text": law["text"], "useLlm": False})["rules"]
    for l in post("/api/laws/activate", {"rules": rules, "appliesTo": {"roles": roles} if roles else None}):
        scope = " (" + ", ".join(roles) + ")" if roles else " (everyone)"
        print(f"✓ law: {l['name']}{scope}")
print(f"\nReady. Next:\n  cd {target}\n  claude --model claude-haiku-4-5\nand paste the contents of {here / 'prompt.txt'}")
