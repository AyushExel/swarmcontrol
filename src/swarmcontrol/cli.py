"""The `swctl` command: `serve` runs the governor; connect / disconnect / status wire Claude Code to one;
`bench` and `bend-check` are maintainer tools (benchmarks and their reports, the Bend proof gate)."""

from __future__ import annotations

import argparse
import os
import sys

from . import connect


def serve(argv: list[str]) -> None:
    p = argparse.ArgumentParser(prog="swctl serve", description="Run the governor API and dashboard.")
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8787)))
    p.add_argument("--db", help="SQLite event store (default: SWARMCONTROL_DB, or ~/.local/share/swarmcontrol/swarmcontrol.db)")
    a = p.parse_args(argv)
    from .env import load_env

    load_env()
    if a.db:
        os.environ["SWARMCONTROL_DB"] = a.db
    # agents started by benchmark runs (the MCP bridge, harness hooks) call back on this port
    os.environ["PORT"] = str(a.port)
    # loopback by default; a network address needs a shared access token
    if a.host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get("SWARMCONTROL_TOKEN"):
        sys.exit(f"[swarmcontrol] refusing to listen on {a.host} without SWARMCONTROL_TOKEN: set one (e.g. `openssl rand -hex 32`), or keep --host 127.0.0.1.")
    import uvicorn

    print(f"[swarmcontrol] API on http://{'localhost' if a.host == '127.0.0.1' else a.host}:{a.port}", flush=True)
    uvicorn.run("swarmcontrol.api:app", host=a.host, port=a.port, log_level="warning")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "serve":
        serve(args[1:])
    elif args and args[0] == "bench":
        from .benchtools import main as bench

        sys.exit(bench(args[1:]))
    elif args and args[0] == "bend-check":
        from .benchtools import bend_check

        sys.exit(bend_check())
    else:
        connect.main(args)
        if not args or args[0] not in ("connect", "disconnect", "status", "stop"):
            print("\n  swctl serve [--host H] [--port P] [--db FILE]   run the governor and dashboard")
            print("  swctl bench run|report|delegated-report|shift-report|summarize|smoke|demo   benchmarks (maintainers)")
            print("  swctl bend-check                               compile the gates and check the proofs")


if __name__ == "__main__":
    main()
