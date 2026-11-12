"""MCP stdio server that Claude Code spawns for one governed agent. It owns no logic: tool listing and every tool call
are forwarded to the governor API, which gates and executes them. With Claude Code's built-in tools disabled, this
bridge is the agent's only way to act.

Standalone (standard library only), so it starts fast and runs from any Python 3.8+.
env: SC_API (http://localhost:8787), SC_EXP, SC_AGENT, SC_TOKEN"""

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("SC_API", "http://localhost:8787")
BASE = f"{API}/api/bridge/{os.environ.get('SC_EXP', '')}/{os.environ.get('SC_AGENT', '')}"
HEADERS = {"content-type": "application/json", "x-sc-token": os.environ.get("SC_TOKEN", "")}


def http(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, headers=HEADERS, data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except ValueError:
            return e.code, None


def text(t, is_error=False):
    return {"content": [{"type": "text", "text": t}], "isError": is_error}


def handle(msg):
    method = msg.get("method")
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion") or "2025-06-18"
        return {"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": {"name": "governor", "version": "1.0.0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        _, tools = http("GET", "/tools")
        return {"tools": [{"name": t["name"], "description": t["description"], "inputSchema": t["input_schema"]} for t in tools or []]}
    if method == "tools/call":
        p = msg.get("params") or {}
        try:
            status, out = http("POST", "/call", {"name": p.get("name"), "input": p.get("arguments") or {}})
        except Exception as e:  # the governor is unreachable: nothing executes (fail closed)
            return text(f"runtime unreachable; action not executed ({e})", True)
        out = out or {}
        if status >= 400:
            return text(f"runtime error: {out.get('error') or out.get('detail') or status}", True)
        return text(out.get("content") or "", bool(out.get("isError")))
    raise KeyError(method)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if "id" not in msg:
            continue  # a notification: nothing to answer
        try:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "result": handle(msg)}
        except KeyError:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": f"method not found: {msg.get('method')}"}}
        except Exception as e:
            reply = {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32603, "message": str(e)}}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
