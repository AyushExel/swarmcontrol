"""Mapping a harness's tool calls (Claude Code hook payloads) to governor checkpoints.

File tools name their target directly. Shell commands are parsed best-effort for the files they would change;
anything this parser misses is not caught, so pair shell access with a sandbox for hard guarantees."""

from __future__ import annotations

import os
import re
from pathlib import Path


def _resolve(base: str, p: str) -> str:
    """Like Node's path.resolve: absolute and normalized, without following symlinks."""
    return os.path.normpath(os.path.join(base, p))


def shell_words(cmd: str) -> list[str]:
    """Split a shell command into words, honouring quotes; operators (&&, ||, ;, |, >, >>) become their own words."""
    out: list[str] = []
    cur = ""
    q: str | None = None
    i, n = 0, len(cmd)

    def push():
        nonlocal cur
        if cur:
            out.append(cur)
        cur = ""

    while i < n:
        c = cmd[i]
        if q:
            if c == q:
                q = None
            elif c == "\\" and q == '"' and i + 1 < n:
                i += 1
                cur += cmd[i]
            else:
                cur += c
            i += 1
            continue
        if c in ("'", '"'):
            q = c
        elif c == "\\" and i + 1 < n:
            i += 1
            cur += cmd[i]
        elif c.isspace():
            push()
        elif c == "&" and cmd[i + 1 : i + 2] == "&":
            push(); out.append("&&"); i += 1
        elif c == "|" and cmd[i + 1 : i + 2] == "|":
            push(); out.append("||"); i += 1
        elif c in (";", "|", "\n"):
            push(); out.append(";")
        elif c == ">":
            # fd prefixes (2>, 1>) and &> belong to the redirect
            if re.fullmatch(r"\d", cur) or cur == "&":
                cur = ""
            push()
            if cmd[i + 1 : i + 2] == ">":
                out.append(">>"); i += 1
            else:
                out.append(">")
            if cmd[i + 1 : i + 2] == "&":  # >&2: not a file
                i += 1
                while i + 1 < n and not cmd[i + 1].isspace():
                    i += 1
                out.pop()
        else:
            cur += c
        i += 1
    push()
    return out


def expand_home(p: str) -> str:
    """The shell expands these before a command sees them; the parser has to as well."""
    m = re.fullmatch(r"(~|\$HOME|\$\{HOME\})(/.*)?", p)
    return os.path.normpath(str(Path.home()) + (m.group(2) or "")) if m else p


def bash_write_targets(cmd: str, cwd: str) -> list[str]:
    """Files a shell command would create, change or delete (relative paths resolved against cwd, following `cd`)."""
    targets: list[str] = []
    base = cwd

    def add(p: str | None):
        if not p or p.startswith("-") or p.startswith("/dev/"):
            return
        targets.append(_resolve(base, expand_home(p)))

    segs: list[list[str]] = [[]]
    for w in shell_words(cmd):
        if w in ("&&", "||", ";"):
            segs.append([])
        else:
            segs[-1].append(w)
    for seg in segs:
        # redirections anywhere in the segment
        args: list[str] = []
        i = 0
        while i < len(seg):
            if seg[i] in (">", ">>"):
                i += 1
                add(seg[i] if i < len(seg) else None)
            else:
                args.append(seg[i])
            i += 1
        while args and re.match(r"^\w+=", args[0]):  # VAR=value prefixes
            args.pop(0)
        if not args:
            continue
        prog, rest = args[0], args[1:]
        files = [a for a in rest if not a.startswith("-")]
        name = prog.split("/")[-1]
        if name == "cd":
            base = _resolve(base, expand_home(rest[0] if rest else "~"))
        elif name in ("rm", "rmdir", "touch", "truncate", "shred", "unlink", "mkdir", "tee", "mv"):
            for f in files:  # mv: the source disappears and the destination changes
                add(f)
        elif name in ("cp", "install", "ln", "rsync"):
            add(files[-1] if files else None)
        elif name in ("chmod", "chown"):
            for f in files[1:]:
                add(f)
        elif name in ("sed", "perl") and any(re.match(r"^-[a-zA-Z]*i", a) or a == "--in-place" for a in rest):
            # sed -i 's/a/b/' file...: the script is the first non-flag word unless -e/-f supplied it
            script_given = any(a in ("-e", "-f") or re.fullmatch(r"-[a-zA-Z]*e", a) for a in rest)
            operands = [a for k, a in enumerate(rest) if not a.startswith("-") and not (k > 0 and rest[k - 1] in ("-e", "-f"))]
            for f in operands if script_given else operands[1:]:
                add(f)
        elif name == "git" and rest and rest[0] in ("checkout", "restore", "rm", "mv", "clean", "reset"):
            picked = rest[rest.index("--") + 1 :] if "--" in rest else [a for a in rest[1:] if not a.startswith("-") and "/" in a]
            for f in picked:
                add(f)
        elif name == "dd":
            for a in rest:
                if a.startswith("of="):
                    add(a[3:])
    return list(dict.fromkeys(targets))


def tool_write_targets(tool: str, inp: dict, cwd: str) -> list[str]:
    """Files a Claude Code tool call would write, as absolute paths. Read-only tools return []."""
    def p(v):
        return [v if os.path.isabs(v) else _resolve(cwd, v)] if isinstance(v, str) and v else []

    if tool in ("Write", "Edit", "MultiEdit"):
        return p(inp.get("file_path"))
    if tool == "NotebookEdit":
        return p(inp.get("notebook_path"))
    if tool == "Bash":
        return bash_write_targets(str(inp.get("command") or ""), cwd)
    return []


_SHELL_RC = r"/\.(bashrc|bash_profile|bash_login|bash_logout|profile|zshrc|zshenv|zprofile|zlogin|zlogout)$"


def is_governor_config(abs_path: str) -> bool:
    """What an agent must never change, whatever the laws say: the settings and hooks connecting it to the governor,
    the governor's saved config, and the machine's environment (shell startup files; folders of commands on PATH,
    where a wrapper could shadow the tools a done check runs). A blocked Haiku 4.5 agent tried each of these."""
    home = str(Path.home())
    in_home = abs_path[len(home):] if abs_path == home or abs_path.startswith(home + "/") else None
    return bool(
        re.search(r"/\.claude/(settings(\.local)?\.json$|hooks(/|$))", abs_path)
        or re.search(r"/\.config/(swarmcontrol|swarm-governor)(/|$)", abs_path)
        or re.search(_SHELL_RC, abs_path)
        or re.match(r"^/(usr/local|opt/homebrew)/bin(/|$)", abs_path)
        or (in_home is not None and re.match(r"^/(\.local/bin|bin|\.volta/bin|\.npm-global/bin)(/|$)", in_home))
    )


def virtual_path(abs_path: str, root: str) -> str:
    """The governor's virtual path for a file: /repo/<path relative to the project root>, or /host/<absolute path>."""
    rel = os.path.relpath(abs_path, root) if root else abs_path
    if not root or rel.startswith("..") or os.path.isabs(rel):
        return f"/host{abs_path}"
    return "/repo/" if rel == "." else f"/repo/{rel}"


def outside_root(tool: str, inp: dict, cwd: str, root: str) -> str | None:
    """Benchmark sandbox (both arms, as infrastructure): the first path a tool call would touch outside `root`."""
    def inside(a: str):
        return a == root or a.startswith(root + "/") or a == "/dev/null"

    def check(p):
        if not isinstance(p, str) or not p:
            return None
        a = "/home" + p[1:] if p.startswith("~") else p if os.path.isabs(p) else _resolve(cwd, p)
        return None if inside(a) else a

    if tool == "Bash":
        for w in shell_words(str(inp.get("command") or "")):
            for part in re.split(r"[=:,]", w):
                if part.startswith("/") or part.startswith("~") or ".." in part.split("/"):
                    bad = check(part)
                    if bad:
                        return bad
        return None
    for k in ("file_path", "notebook_path", "path"):
        bad = check(inp.get(k))
        if bad:
            return bad
    return None
