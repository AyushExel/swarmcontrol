"""The governor's HTTP API and dashboard.

Loopback by default. Listening on a network address requires a shared access token (SWARMCONTROL_TOKEN): every /api
request must then send it, as `Authorization: Bearer <token>` (or ?token= for event streams and downloads)."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse

from . import experiments as X
from .bend import gates as G
from .bend.adapter import CHECK_LABELS
from .bend.toolchain import build_and_check_core, find_bend
from .export import export_lines
from .laws import registry as R
from .laws.translate import translate
from .llm import DEFAULT_MODEL, SIMULATED_PRICE_PER_MTOK, llm_available
from .paths import BEND_DIR, PACKAGE, WEB_DIR
from .real.claude_code import claude_code_info
from .real.runner import RealRunner
from .runtime.sandbox import CATALOG, DEFAULT_PROTECTED
from .runtime.simulator import BASELINE_LOOP_CAP, COMPLIANCE_MODEL, SAFETY_RECOVERY_CAP
from .store import store

TOKEN = os.environ.get("SWARMCONTROL_TOKEN", "")
_core: dict[str, Any] = {}


def _dist() -> Path | None:
    """The built dashboard: shipped inside the package (in a checkout, `npm run build` puts it there)."""
    return WEB_DIR if (WEB_DIR / "index.html").exists() else None


def boot() -> None:
    st = build_and_check_core()
    _core.clear()
    _core.update(st.__dict__)
    G.load_core_gates()
    R.init_laws()
    X.recover_interrupted()
    gates, err = G.core()
    print(f"[swarmcontrol] bend {st.bendVersion or 'NOT FOUND'} · core proofs: {st.proofStatus} ({st.checkMs}ms) · "
          f"gates: {('loaded' if st.gatesMode != 'interpreted' else 'loaded, interpreted (install clang 14+ for ~100x faster checks)') if gates else f'UNAVAILABLE ({err})'} · llm: {DEFAULT_MODEL if llm_available() else 'not configured'}", flush=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not _core:
        await asyncio.to_thread(boot)
    yield


app = FastAPI(title="SwarmControl", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")


def _same(given: str | None) -> bool:
    return bool(given) and hmac.compare_digest(given.encode(), TOKEN.encode())


@app.middleware("http")
async def auth(request: Request, call_next):
    path = request.url.path
    if TOKEN and path.startswith("/api/"):
        # benchmark agents carry a per-run token that the bridge and hook handlers check themselves
        exempt = path.startswith("/api/bridge/") or (path == "/api/hooks/claude-code" and request.headers.get("x-sc-exp"))
        bearer = (request.headers.get("authorization") or "").removeprefix("Bearer ").removeprefix("bearer ").strip()
        if not exempt and not (_same(bearer) or _same(request.headers.get("x-swarmcontrol-token")) or _same(request.query_params.get("token"))):
            return JSONResponse({"error": "unauthorized: send the governor access token (SWARMCONTROL_TOKEN)"}, status_code=401)
    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_error(_req: Request, exc: HTTPException):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(ValueError)
async def value_error(_req: Request, exc: ValueError):
    return JSONResponse({"error": str(exc)}, status_code=400)


@app.exception_handler(LookupError)
async def lookup_error(_req: Request, exc: LookupError):
    return JSONResponse({"error": str(exc).strip("'\"")}, status_code=404)


async def _body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    try:
        b = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "invalid JSON body")
    return b if isinstance(b, dict) else {}


# ---------------------------------------------------------------- status

@app.get("/api/status")
def status():
    gates, err = G.core()
    return {
        "bend": {**_core, "binary": find_bend()},
        "gatesLoaded": gates is not None, "gatesError": err,
        "llm": {"available": llm_available(), "model": DEFAULT_MODEL},
        "claudeCode": claude_code_info(),
        "openRouter": bool(os.environ.get("OPENROUTER_API_KEY")),
        "defaults": {"failure": X.DEFAULT_FAILURE, "maxRecoveryAttempts": 3, "protectedPaths": DEFAULT_PROTECTED},
        "assumptions": {"complianceModel": COMPLIANCE_MODEL, "baselineLoopCap": BASELINE_LOOP_CAP, "safetyRecoveryCap": SAFETY_RECOVERY_CAP,
                        "simulatedPricePerMTok": SIMULATED_PRICE_PER_MTOK},
        "checks": {**CHECK_LABELS, "acceptance_suite": "CI acceptance suite passes (held-out tests the agent cannot see)"},
        "catalog": [r["path"] for r in CATALOG],
    }


@app.get("/api/bend/sources")
def bend_sources():
    return {k: (BEND_DIR / f).read_text() for k, f in (("governor", "governor.bend"), ("laws", "LAWS.bend"), ("proof", "PROOF.bend"))}


@app.post("/api/bend/recheck")
def bend_recheck():
    st = build_and_check_core()
    _core.clear()
    _core.update(st.__dict__)
    G.load_core_gates()
    return _core


# ------------------------------------------------------------------ laws

def _laws_changed(out):
    # attached sessions snapshot their laws when they start; the next hook call opens a record with the current laws
    X.close_all_attached()
    return out


@app.get("/api/laws")
def laws():
    return R.list_laws()


@app.post("/api/laws/translate")
async def laws_translate(request: Request):
    body = await _body(request)
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text is required")
    t = await asyncio.to_thread(translate, text, body.get("useLlm") is not False)
    drafts = [await asyncio.to_thread(R.preview_rule, r) for r in t["rules"]]
    return {**t, "drafts": drafts}


@app.post("/api/laws/preview")
async def laws_preview(request: Request):
    return await asyncio.to_thread(R.preview_rule, (await _body(request)).get("rule") or {})


@app.post("/api/laws/activate")
async def laws_activate(request: Request):
    body = await _body(request)
    rules, names = body.get("rules") or [], body.get("names") or []
    # appliesTo: optional scope for every activated rule (roles and/or agent ids); omitted = global
    out = [await asyncio.to_thread(R.create_from_rule, r, names[i] if i < len(names) else None, body.get("appliesTo")) for i, r in enumerate(rules)]
    return _laws_changed(out)


@app.post("/api/laws/bend/check")
async def laws_bend_check(request: Request):
    return await asyncio.to_thread(R.preview_bend, str((await _body(request)).get("source") or ""))


@app.post("/api/laws/bend")
async def laws_bend(request: Request):
    body = await _body(request)
    if not body.get("name") or not body.get("source"):
        raise HTTPException(400, "name and source are required")
    law = await asyncio.to_thread(R.create_bend, str(body["name"]), str(body["source"]), str(body.get("description") or ""), body.get("appliesTo"))
    return _laws_changed(law)


@app.patch("/api/laws/{law_id}")
async def laws_update(law_id: str, request: Request):
    body = await _body(request)
    kw = {k: body[k] for k in ("name", "description", "params", "source", "enabled") if k in body}
    if "appliesTo" in body:
        kw["applies_to"] = body["appliesTo"]
    return _laws_changed(await asyncio.to_thread(R.update_law, law_id, **kw))


@app.post("/api/laws/{law_id}/validate")
def laws_validate(law_id: str):
    return R.revalidate(law_id)


@app.delete("/api/laws/{law_id}")
def laws_delete(law_id: str):
    R.delete_law(law_id)
    return _laws_changed({"ok": True})


# ----------------------------------------------------------- experiments

def _live(exp_id: str) -> bool:
    r = X.runner_for(exp_id)
    return bool(r and not r.is_finished)


@app.get("/api/experiments")
def experiments_list():
    return [{**e, "config": {**e["config"], "laws": [{"id": l["id"], "name": l["name"], "template": l["template"]} for l in e["config"]["laws"]]},
             "live": _live(e["id"])} for e in store().experiments()]


@app.post("/api/experiments")
async def experiments_start(request: Request):
    return X.start_experiment(await _body(request))


@app.post("/api/experiments/paired")
async def experiments_paired(request: Request):
    body = await _body(request)
    reps = int(body.get("repetitions") or 1)
    if reps > 1:
        return X.start_repetitions(body.get("config") or {}, reps)
    return X.start_paired(body.get("config") or {})


@app.get("/api/experiments/{exp_id}")
def experiment_get(exp_id: str):
    e = store().get_experiment(exp_id)
    if not e:
        raise HTTPException(404, "experiment not found")
    return {**e, "live": _live(exp_id), "humanActionsAvailable": X.runner_for(exp_id) is not None}


@app.get("/api/experiments/{exp_id}/events")
def experiment_events(exp_id: str, after: int = 0):
    return store().events(exp_id, after)


@app.post("/api/experiments/{exp_id}/agents/{agent_id}/human")
async def experiment_human(exp_id: str, agent_id: str, request: Request):
    body = await _body(request)
    r = X.runner_for(exp_id)
    if not r:
        raise HTTPException(409, "This experiment is not loaded in the running server (it was recorded before a restart); human actions are unavailable.")
    try:
        r.human_action(agent_id, "cancel" if body.get("action") == "cancel" else "retry_with_guidance", body.get("note"))
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.get("/api/experiments/{exp_id}/stream")
async def experiment_stream(exp_id: str, request: Request, after: int = 0):
    """Server-sent events: backfill from the persisted log, then stream live events."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[list[dict]] = asyncio.Queue()
    r = X.runner_for(exp_id)
    # subscribe first, then backfill, so nothing falls between the two
    unsub = r.subscribe(lambda evs: loop.call_soon_threadsafe(queue.put_nowait, evs)) if r else None

    def status_frame() -> str:
        e = store().get_experiment(exp_id)
        return f"event: status\ndata: {json.dumps({'status': e['status'] if e else None})}\n\n"

    async def gen():
        last = after

        def frame(evs: list[dict]) -> str | None:
            nonlocal last
            fresh = [e for e in evs if e["id"] > last]
            if not fresh:
                return None
            last = fresh[-1]["id"]
            return f"data: {json.dumps(fresh, separators=(',', ':'), ensure_ascii=False)}\n\n"

        try:
            backlog = store().events(exp_id, after)
            for i in range(0, len(backlog), 2000):
                if f := frame(backlog[i : i + 2000]):
                    yield f
            yield status_frame()
            while not await request.is_disconnected():
                try:
                    evs = await asyncio.wait_for(queue.get(), timeout=2)
                    if f := frame(evs):
                        yield f
                except asyncio.TimeoutError:
                    yield status_frame()
        finally:
            if unsub:
                unsub()

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


# ------------------------------------------------------ attached harnesses
# Governing an existing harness: the Claude Code hook posts every hook event here. Identity: a user's session
# (project, role, agent name); benchmark agents (exp + agent + token headers) arrive with the Python benchmarks.

def _owns(raw: Any) -> list[str] | None:
    xs = [f"/repo/{x.strip().removeprefix('./').lstrip('/')}" for x in str(raw or "").split(",") if x.strip()]
    return xs or None


def _bridge_runner(request: Request, exp: str) -> RealRunner:
    """A benchmark run's agents (MCP bridge, harness hooks) authenticate with the run's own token."""
    r = X.runner_for(exp)
    if not isinstance(r, RealRunner):
        raise HTTPException(404, "no live real-model run with this id")
    if not hmac.compare_digest(request.headers.get("x-sc-token") or "", r.token):
        raise HTTPException(403, "bad bridge token")
    return r


# MCP bridge for Claude Code agents: every tool call is gated by the runner.
@app.get("/api/bridge/{exp_id}/{agent_id}/tools")
def bridge_tools(exp_id: str, agent_id: str, request: Request):
    return _bridge_runner(request, exp_id).bridge_tools(agent_id)


@app.post("/api/bridge/{exp_id}/{agent_id}/call")
async def bridge_call(exp_id: str, agent_id: str, request: Request):
    r = _bridge_runner(request, exp_id)
    body = await _body(request)
    inp = body.get("input") if isinstance(body.get("input"), dict) else {}
    return await asyncio.to_thread(r.bridge_call, agent_id, str(body.get("name") or ""), inp)


@app.post("/api/hooks/claude-code")
async def hooks_claude_code(request: Request):
    body = await _body(request)
    payload = body.get("payload") or {}
    event = str(payload.get("hook_event_name") or "")
    exp = request.headers.get("x-sc-exp")
    if exp:
        r = _bridge_runner(request, exp)
        a = r.agent_by_id(request.headers.get("x-sc-agent") or "")
        if not a:
            raise HTTPException(404, "unknown agent")
        return await asyncio.to_thread(r.hook_event, a, event, payload, None)
    ident = body.get("identity") or {}
    project = str(ident.get("project") or "default")
    r = X.attached_runner(project, ident.get("mode") != "observe")
    cwd = str(payload.get("cwd") or "")
    owns = _owns(ident.get("owns"))
    session = str(payload.get("session_id") or "session")
    name = str(ident.get("agent") or f"session {session[:8]}")
    role = str(ident.get("role") or "agent")
    # Claude Code marks tool calls made inside a subagent with agent_id / agent_type: each subagent is its own agent,
    # with its type as its role, and it inherits the session's laws (so a subagent can't be used to dodge them)
    if payload.get("agent_id"):
        sub = str(payload.get("agent_type") or "subagent")
        a = r.attach_agent(f"{session}:{payload['agent_id']}", f"{name} / {sub}", sub, cwd, owns, {"names": [name], "roles": [role]})
    else:
        a = r.attach_agent(session, name, role, cwd, owns)
    out = await asyncio.to_thread(r.hook_event, a, event, payload, body.get("doneCheck"))
    # escalated while finishing: a hook that can wait holds the session open until a human decides
    if ident.get("canWait") and event in ("Stop", "SubagentStop") and a.state == "awaiting_human":
        return {**out, "governorWait": {"experiment": r.exp["id"], "agent": a.id}}
    return out


@app.get("/api/attach/{exp_id}/agents/{agent_id}/decision")
def attach_decision(exp_id: str, agent_id: str):
    r = X.runner_for(exp_id)
    return r.human_decision(agent_id) if r else {"decided": True, "action": "gone", "note": ""}


@app.post("/api/attach/check")
async def attach_check(request: Request):
    """Any other harness or SDK: the same decision, with a neutral payload.
    { project, role, agent, session, owns, mode, event, tool, input, cwd, result, doneCheck, parent?: { agent, role } }"""
    body = await _body(request)
    r = X.attached_runner(str(body.get("project") or "default"), body.get("mode") != "observe")
    p = body.get("parent") or {}
    parent = {"names": [str(p["agent"])], "roles": [str(p.get("role") or "agent")]} if p.get("agent") else None
    a = r.attach_agent(str(body.get("session") or body.get("agent") or "session"), str(body.get("agent") or body.get("session") or "agent"),
                       str(body.get("role") or "agent"), str(body.get("cwd") or ""), _owns(body.get("owns")), parent)
    out = await asyncio.to_thread(r.hook_event, a, str(body.get("event") or "PreToolUse"),
                                  {"tool_name": body.get("tool"), "tool_input": body.get("input") or {}, "cwd": body.get("cwd"), "tool_response": body.get("result")},
                                  body.get("doneCheck"))
    denied = out.get("hookSpecificOutput") or {}
    blocked = denied.get("permissionDecision") == "deny" or out.get("decision") == "block"
    return {"allow": not blocked, "reason": denied.get("permissionDecisionReason") or out.get("reason"), "agent": a.id, "experiment": r.exp["id"], "health": a.health}


@app.post("/api/attach/{exp_id}/close")
def attach_close(exp_id: str):
    X.close_attached(exp_id)
    return {"closed": exp_id}


@app.post("/api/benchmarks/{bench_id}/invalidate")
async def benchmarks_invalidate(bench_id: str, request: Request):
    """Mark benchmark runs invalid (e.g. usage-limit errors) so reports flag them."""
    body = await _body(request)
    for exp_id in body.get("ids") or []:
        e = store().get_experiment(exp_id)
        if e and e["config"].get("benchmarkId") == bench_id:
            store().put_experiment({**e, "config": {**e["config"], "invalid": str(body.get("reason") or "invalid")}})
    return {"ok": True}


@app.get("/api/export")
def export(format: str = "trajectories", experiments: str | None = None):
    """JSONL export for analysis / fine-tuning: ?format=trajectories|sft|preferences&experiments=id,id (default: all)."""
    fmt = format if format in ("trajectories", "sft", "preferences") else "trajectories"
    ids = [x for x in experiments.split(",") if x] if experiments else [e["id"] for e in store().experiments()]
    return Response("\n".join(export_lines(fmt, ids)) + "\n", media_type="application/x-ndjson",
                    headers={"Content-Disposition": f'attachment; filename="{fmt}.jsonl"'})


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
def api_not_found(rest: str):
    raise HTTPException(404, "not found")


# ---------------------------------------------------------- scripts and UI

@app.get("/hook.py")
def hook_script():
    """The Claude Code hook (standard library only), so developers can connect without installing anything."""
    return PlainTextResponse((PACKAGE / "hook.py").read_text(), media_type="text/x-python; charset=utf-8")


@app.get("/connect.py")
def connect_script():
    return PlainTextResponse((PACKAGE / "connect.py").read_text(), media_type="text/x-python; charset=utf-8")


@app.get("/{path:path}")
def ui(path: str):
    dist = _dist()
    if not dist:
        raise HTTPException(404, "UI not built: run `npm run build` in a checkout, or install the published package")
    f = (dist / path).resolve()
    if path and f.is_file() and f.is_relative_to(dist.resolve()):
        return FileResponse(f)
    return FileResponse(dist / "index.html")
