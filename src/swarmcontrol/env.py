"""Load ./.env (gitignored) before anything reads the environment. Variables already set win."""

import os
from pathlib import Path


def load_env(path: str | os.PathLike = ".env") -> None:
    f = Path(path)
    if not f.is_file():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.removeprefix("export ").split("=", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        os.environ.setdefault(k.strip(), v)
