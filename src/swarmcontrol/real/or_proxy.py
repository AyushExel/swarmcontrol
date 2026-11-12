"""A proxy between Claude Code and OpenRouter's Anthropic-compatible API, for running open models inside the real
Claude Code harness. It does two things, and nothing else:
 1. Pins the inference provider (OpenRouter's `provider` preference), which Claude Code can't set itself.
 2. Repairs tool calls that the model wrote in its native text format (Qwen: <function=NAME><parameter=K>V
    </parameter></function>) into structured tool_use blocks, as Qwen's own harness (Qwen Code) does. Without this,
    Claude Code reads such a reply as a final answer and ends the session. Repairs are counted.
Upstream requests are made non-streaming; a streaming client gets the result re-emitted as Anthropic SSE."""

from __future__ import annotations

import json
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

proxy_stats = {"requests": 0, "repairedReplies": 0, "repairedCalls": 0}
_started: int | None = None
_lock = threading.Lock()

_FUNC = re.compile(r"<function=([^>\s]+)>([\s\S]*?)(?:</function>|$)")
_PARAM = re.compile(r"<parameter=([^>\s]+)>\n?([\s\S]*?)\n?</parameter>")


def repair_tool_calls(content: list[dict], tools: list[dict]) -> tuple[list[dict], int]:
    """Turn <function=...> text into tool_use blocks."""
    out: list[dict] = []
    repaired = 0
    for b in content:
        if b.get("type") != "text" or "<function=" not in (b.get("text") or ""):
            out.append(b)
            continue
        text = b["text"]
        first = text.index("<function=")
        lead = re.sub(r"<tool_call>\s*$", "", text[:first]).strip()
        if lead:
            out.append({"type": "text", "text": lead})
        for m in _FUNC.finditer(text[first:]):
            name = m.group(1)
            schema = next((t.get("input_schema", {}).get("properties", {}) for t in tools if t.get("name") == name), {}) or {}
            inp = {}
            for k, raw in _PARAM.findall(m.group(2)):
                if (schema.get(k) or {}).get("type") == "string":
                    inp[k] = raw
                else:
                    try:
                        inp[k] = json.loads(raw)
                    except ValueError:
                        inp[k] = raw
            out.append({"type": "tool_use", "id": f"toolu_{uuid.uuid4().hex[:24]}", "name": name, "input": inp})
            repaired += 1
    return out, repaired


def _sse(h: BaseHTTPRequestHandler, msg: dict) -> None:
    h.send_response(200)
    h.send_header("content-type", "text/event-stream")
    h.send_header("cache-control", "no-cache")
    h.end_headers()

    def send(event: str, data: dict) -> None:
        h.wfile.write(f"event: {event}\ndata: {json.dumps(data)}\n\n".encode())

    send("message_start", {"type": "message_start", "message": {"id": msg.get("id"), "type": "message", "role": "assistant", "model": msg.get("model"), "content": [],
                                                                "stop_reason": None, "stop_sequence": None, "usage": {**(msg.get("usage") or {}), "output_tokens": 1}}})
    for index, b in enumerate(msg.get("content") or []):
        t = b.get("type")
        if t == "tool_use":
            send("content_block_start", {"type": "content_block_start", "index": index, "content_block": {"type": "tool_use", "id": b.get("id"), "name": b.get("name"), "input": {}}})
            send("content_block_delta", {"type": "content_block_delta", "index": index, "delta": {"type": "input_json_delta", "partial_json": json.dumps(b.get("input") or {})}})
        elif t == "text":
            send("content_block_start", {"type": "content_block_start", "index": index, "content_block": {"type": "text", "text": ""}})
            send("content_block_delta", {"type": "content_block_delta", "index": index, "delta": {"type": "text_delta", "text": b.get("text") or ""}})
        elif t == "thinking":
            send("content_block_start", {"type": "content_block_start", "index": index, "content_block": {"type": "thinking", "thinking": "", "signature": ""}})
            send("content_block_delta", {"type": "content_block_delta", "index": index, "delta": {"type": "thinking_delta", "thinking": str(b.get("thinking") or "")}})
        else:
            continue
        send("content_block_stop", {"type": "content_block_stop", "index": index})
    send("message_delta", {"type": "message_delta", "delta": {"stop_reason": msg.get("stop_reason"), "stop_sequence": None},
                           "usage": {"output_tokens": int((msg.get("usage") or {}).get("output_tokens") or 1)}})
    send("message_stop", {"type": "message_stop"})


def open_router_proxy(order: list[str]) -> int:
    """Start the proxy once per process; returns its port."""
    global _started
    with _lock:
        if _started is not None:
            return _started

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def _forward(self) -> None:
                import httpx

                n = int(self.headers.get("content-length") or 0)
                body: bytes = self.rfile.read(n) if n else b""
                want_stream, tools = False, []
                is_messages = self.command == "POST" and re.search(r"/messages(\?|$)", self.path) is not None
                if is_messages:
                    try:
                        j = json.loads(body)
                        j["provider"] = {"order": order, "allow_fallbacks": False}
                        want_stream = bool(j.get("stream"))
                        j["stream"] = False
                        tools = j.get("tools") or []
                        body = json.dumps(j).encode()
                    except ValueError:
                        pass  # not JSON: forward unchanged
                headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length", "connection", "accept-encoding")}
                try:
                    r = httpx.request(self.command, f"https://openrouter.ai/api{self.path}", headers=headers, content=None if self.command in ("GET", "HEAD") else body, timeout=600)
                    if not is_messages or not r.is_success:
                        self.send_response(r.status_code)
                        self.send_header("content-type", r.headers.get("content-type") or "application/json")
                        self.end_headers()
                        self.wfile.write(r.content)
                        return
                    msg = r.json()
                    content, n_fixed = repair_tool_calls(msg.get("content") or [], tools)
                    with _lock:
                        proxy_stats["requests"] += 1
                        if n_fixed:
                            proxy_stats["repairedReplies"] += 1
                            proxy_stats["repairedCalls"] += n_fixed
                    if n_fixed:
                        msg["content"] = content
                        msg["stop_reason"] = "tool_use"
                    if want_stream:
                        _sse(self, msg)
                    else:
                        out = json.dumps(msg).encode()
                        self.send_response(200)
                        self.send_header("content-type", "application/json")
                        self.end_headers()
                        self.wfile.write(out)
                except Exception as e:  # noqa: BLE001
                    out = json.dumps({"type": "error", "error": {"type": "api_error", "message": f"proxy: {e}"}}).encode()
                    self.send_response(502)
                    self.send_header("content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(out)

            do_GET = do_POST = do_HEAD = _forward

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True, name="or-proxy").start()
        _started = server.server_address[1]
        return _started
