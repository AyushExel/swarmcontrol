#!/usr/bin/env python3
"""Connect Claude Code to a running SwarmControl (standard library only; Python 3.8+).

  swctl connect [--server URL] [--token T] [--global | --team] [--dir PATH]
                         [--role R] [--agent NAME] [--done-check CMD] [--observe] [--fail-open]
  swctl disconnect [--global | --team] [--dir PATH]
  swctl status [--dir PATH]

Without installing the package, fetch this file from the server:
  curl -fsSL https://your-server/connect.py | python3 - connect --server https://your-server --token T"""

import json
import os
import shlex
import sys
import urllib.error
import urllib.request

EVENTS = ["PreToolUse", "PostToolUse", "Stop", "SubagentStop"]
ENV_KEYS = {"role": "SC_ROLE", "agent": "SC_AGENT", "done-check": "SC_DONE_CHECK"}
SWITCHES = ("global", "team", "observe", "fail-open")
DEFAULT_SERVER = "http://localhost:8787"
HOOK_NAME = "swarmcontrol-hook.py"


def gov_home():
    return os.environ.get("SWARMCONTROL_HOME") or os.path.join(os.path.expanduser("~"), ".config", "swarmcontrol")


def parse(argv):
    argv = [a for a in argv if a != "-"]
    cmd = argv[0] if argv else "help"
    flags = {}
    i = 1
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):  # a bare word (e.g. "connect claude") is the optional target: Claude Code is the only one
            key = a[2:]
            if key in SWITCHES:
                flags[key] = True
            elif i + 1 < len(argv):
                flags[key] = argv[i + 1]
                i += 1
        i += 1
    return cmd, flags


def read_json(f):
    try:
        with open(f) as h:
            return json.load(h)
    except FileNotFoundError:
        return {}


def write_json(f, v, mode=None):
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, "w") as h:
        h.write(json.dumps(v, indent=2) + "\n")
    if mode:
        os.chmod(f, mode)


def ours(group):
    return any(n in str(h.get("command", "")) for n in ("swarmcontrol-hook", "governor-hook") for h in group.get("hooks", []))  # governor-hook: the earlier name


def has_our_hooks(f):
    return any(ours(g) for groups in (read_json(f).get("hooks") or {}).values() for g in groups)


def fail(msg):
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(1)


def check(server, token):
    req = urllib.request.Request(f"{server}/api/status", headers={"authorization": f"Bearer {token}"} if token else {})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            s = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "the server rejected this token" if token else "this server needs an access token: pass --token"
        return False, f"{server} answered HTTP {e.code}"
    except (urllib.error.URLError, OSError) as e:
        return False, f"can't reach {server} ({getattr(e, 'reason', e)}). Is the governor running?"
    return True, f"connected to {server} · Bend proofs {(s.get('bend') or {}).get('proofStatus', 'unknown')}"


def hook_source(server):
    """The hook script: next to this file when installed, otherwise from the governor server."""
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook.py")
    if os.path.exists(local):
        with open(local) as h:
            return h.read()
    try:
        with urllib.request.urlopen(f"{server}/hook.py", timeout=15) as r:
            return r.read().decode()
    except (urllib.error.URLError, OSError):
        fail(f"couldn't download the hook from {server}/hook.py")


def set_hooks(f, command, add):
    s = read_json(f)
    hooks = s.setdefault("hooks", {})
    for ev in EVENTS:
        groups = [g for g in hooks.get(ev, []) if not ours(g)]
        if add:
            stop = ev.endswith("Stop")
            groups.append({**({} if stop else {"matcher": "*"}), "hooks": [{"type": "command", "command": command, "timeout": 3600 if stop else 60}]})
        if groups:
            hooks[ev] = groups
        else:
            hooks.pop(ev, None)
    if not hooks:
        del s["hooks"]
    return s


class Cli:
    def __init__(self, flags):
        self.flags = flags
        self.dir = os.path.abspath(flags.get("dir") or os.getcwd())
        self.home = gov_home()
        self.config = os.path.join(self.home, "config.json")
        self.user_claude = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")

    def settings_file(self):
        if self.flags.get("global"):
            return self.user_claude
        return os.path.join(self.dir, ".claude", "settings.json" if self.flags.get("team") else "settings.local.json")

    def env_file(self, f):
        return os.path.join(self.dir, ".claude", "settings.local.json") if self.flags.get("team") else f

    def connect(self):
        fl, cfg = self.flags, read_json(self.config)
        server = str(fl.get("server") or cfg.get("server") or DEFAULT_SERVER).rstrip("/")
        given = fl.get("server") and fl["server"].rstrip("/") != cfg.get("server")
        token = str(fl.get("token") or ("" if given else cfg.get("token") or ""))
        ok, msg = check(server, token)
        if not ok:
            fail(msg)
        print(f"✓ {msg}")
        write_json(self.config, {"server": server, "token": token}, 0o600)
        print(f"✓ saved server and token to {self.config} (readable only by you)")

        source = hook_source(server)
        f = self.settings_file()
        if fl.get("team"):
            team_hook = os.path.join(self.dir, ".claude", "hooks", HOOK_NAME)
            os.makedirs(os.path.dirname(team_hook), exist_ok=True)
            with open(team_hook, "w") as h:
                h.write(source)
            command = f'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/{HOOK_NAME}"'
        else:
            # a committed team hook or a machine-wide hook already covers this project: don't run the hook twice
            for other in (os.path.join(self.dir, ".claude", "settings.json"), self.user_claude):
                if other != f and has_our_hooks(other):
                    print(f"✓ hooks already installed in {other}; nothing else to install")
                    return self.done(server, f, False)
            os.makedirs(self.home, exist_ok=True)
            user_hook = os.path.join(self.home, HOOK_NAME)
            with open(user_hook, "w") as h:
                h.write(source)
            command = f"{shlex.quote(sys.executable)} {shlex.quote(user_hook)}"
        s = set_hooks(f, command, True)
        # personal session defaults never go into a committed file
        env_file = self.env_file(f)
        env_settings = s if env_file == f else read_json(env_file)
        env = dict(env_settings.get("env") or {})
        for flag, key in ENV_KEYS.items():
            if fl.get(flag):
                env[key] = str(fl[flag])
        if fl.get("observe"):
            env["SC_MODE"] = "observe"
        if fl.get("fail-open"):
            env["SC_FAIL_OPEN"] = "1"
        if env:
            env_settings["env"] = env
        write_json(f, s)
        if env_file != f and env:
            write_json(env_file, env_settings)
        print(f"✓ Claude Code hooks installed in {f}{' (every project on this machine)' if fl.get('global') else ''}")
        if fl.get("team"):
            print(f"  Commit .claude/settings.json and .claude/hooks/{HOOK_NAME}. Teammates then run: swctl connect --server {server} --token <token>")
        self.done(server, env_file, bool(env))

    def done(self, server, env_file, wrote_env):
        if wrote_env:
            keys = ", ".join(k for k in (read_json(env_file).get("env") or {}) if k.startswith("SC_"))
            print(f"✓ session defaults ({keys}) saved in {env_file}")
        where = "" if self.flags.get("global") else f" in {self.dir}"
        print(f'\nNext: run `claude`{where} as usual. Watch it at {server} (Live Swarm → "attached: …").')

    def disconnect(self):
        f = self.settings_file()
        if not os.path.exists(f) or not has_our_hooks(f):
            print(f"No SwarmControl hooks in {f}")
        else:
            write_json(f, set_hooks(f, "", False))
            print(f"✓ removed the hooks from {f}")
        env_file = self.env_file(f)
        if os.path.exists(env_file):
            s = read_json(env_file)
            if "env" in s:
                s["env"] = {k: v for k, v in s["env"].items() if not k.startswith(("SC_", "GOV_"))}
                if not s["env"]:
                    del s["env"]
                write_json(env_file, s)
        if self.flags.get("team"):
            for name in (HOOK_NAME, "governor-hook.py", "governor-hook.mjs"):
                p = os.path.join(self.dir, ".claude", "hooks", name)
                if os.path.exists(p):
                    os.remove(p)

    def status(self):
        cfg = read_json(self.config)
        token = cfg.get("token")
        print(f"config      {self.config if os.path.exists(self.config) else '(none: run connect)'}")
        print(f"server      {cfg.get('server') or '(default) ' + DEFAULT_SERVER}")
        print(f"token       {token[:4] + '…' + token[-4:] if token else '(none)'}")
        ok, msg = check(cfg.get("server") or DEFAULT_SERVER, token or "")
        print(f"reachable   {'✓' if ok else '✗'} {msg}")
        for label, f in (("this project", os.path.join(self.dir, ".claude", "settings.local.json")),
                         ("team (repo)", os.path.join(self.dir, ".claude", "settings.json")), ("machine-wide", self.user_claude)):
            print(f"{label:<14}{'✓ hooks in ' + f if has_our_hooks(f) else '-'}")


HELP = """Connect Claude Code to a SwarmControl.

  swctl connect [--server URL] [--token T]   this project (current folder, or --dir PATH)
         --global                                      every Claude Code session on this machine
         --team                                        write hooks into the repo, to commit for the whole team
         --role R --agent NAME --done-check "npm test" --observe --fail-open   session defaults
  swctl disconnect [--global | --team]
  swctl status"""


def main(argv=None):
    cmd, flags = parse(sys.argv[1:] if argv is None else argv)
    cli = Cli(flags)
    if cmd == "connect":
        cli.connect()
    elif cmd == "disconnect":
        cli.disconnect()
    elif cmd == "status":
        cli.status()
    else:
        print(HELP + f"\n\nThe server URL and token are saved once in {cli.config}.")


if __name__ == "__main__":
    main()
