"""The plan and its runs: the Pipeline view, the runs and their event streams, starting and stopping a documentation
run, retrying or approving a unit, and the plan's cost."""
from __future__ import annotations

import json
import time
from typing import BinaryIO

from lib import docs, plan
from lib.app.portal_views import reviewer
from lib.core.paths import CTX
from lib.interfaces.http.jobs import start_job
from lib.interfaces.http.messages import Request, Response, event_stream, json_response
from lib.interfaces.http.router import Access, route
from lib.interfaces.http.routes.machine import ui_lang
from lib.interfaces.http.routes.terminals import unit_terminals


STOPPED_AFTER = 5.0                          # seconds of quiet before a run's stream asks whether its run was stopped


def start_run(b: dict) -> tuple[dict, int]:
    """A documentation run as a background job of this server; refused while another run (CLI or portal) holds the
    run lock."""
    from lib.harness import scheduler
    holder = scheduler.busy()
    if holder:
        return {"error": f"a documentation run is already in progress (pid {holder.get('pid')})"}, 409
    try:
        slots = scheduler.parse_slots(str(b.get("per_runner") or ""))
    except ValueError as e:
        return {"error": f"per_runner {e}"}, 400
    parallel = max(1, min(8, int(b.get("parallel") or 2)))
    max_units = int(b["max_units"]) if b.get("max_units") not in (None, "") else None
    policy = b.get("policy") or "on-conflict"
    if policy not in ("on-conflict", "never"):
        return {"error": "policy: on-conflict or never"}, 400

    def go(log):
        scheduler.run_parallel(lang=b.get("lang") or "en", max_parallel=parallel, per_runner=slots,
                               max_units=max_units, include_interviews=bool(b.get("include_interviews")),
                               policy=policy, echo=log)
    return start_job("run", "documentation run", go), 200


def retry_unit(uid: str) -> tuple[dict, int]:
    u = next((x for x in plan.load()["units"] if x["id"] == uid), None)
    if not u:
        return {"error": f"unknown unit {uid}"}, 404
    if u["status"] != "blocked":
        return {"error": f"{uid} is {u['status']}: only blocked units are retried"}, 409
    return plan.set_status(uid, "todo", "retry requested from the portal"), 200


def approve_unit(uid: str) -> tuple[dict, int]:
    u = next((x for x in plan.load()["units"] if x["id"] == uid), None)
    if not u:
        return {"error": f"unknown unit {uid}"}, 404
    if not plan.awaiting(u):
        return {"error": f"{uid} is not awaiting approval"}, 409
    return plan.approve(uid, by=reviewer()), 200


def run_stopped(run_id: str, busy: bool | None = None) -> bool:
    """A plan run whose log has no run.finished and never will: stopped from outside (its job stopped, which is SIGTERM
    to its process group or taskkill /F on Windows, or a crash) before it could log its end. One run holds the run lock
    at a time, the latest, so an older one is over, and the latest is once the lock is free or stale; its log is read
    again after that, so a run that ended on its own in between is not taken for a stopped one. `busy` is the lock's
    answer when the caller already probed it (a probe holds the lock for an instant, so two can see each other); None
    probes."""
    from lib.harness import runs, scheduler
    latest = runs.ids(wiki=False)
    if busy is None:
        busy = scheduler.busy() is not None
    if run_id not in latest or (run_id == latest[0] and busy):
        return False
    return not any(e["type"] == "run.finished" for e in runs.events(run_id))


def api_pipeline(lang: str = "") -> dict:
    """The plan as a graph for the Pipeline tab: every unit with its status and dependencies, how it runs (isolation,
    tier, runner), its agent session (open or paused, lib/sessions.py), its live terminal in this server and the latest
    run. Titles read in `lang` (plan.title); plan.yaml is only read."""
    from lib import sessions
    from lib.harness import pipeline, runs, scheduler
    lang = ui_lang(lang)
    locked = scheduler.busy() is not None                    # asked once: the second probe could see the first
    busy = sessions.headless(locked)
    term = unit_terminals()
    try:
        nodes = {u["id"]: u for u in plan.pipeline_units()}
    except plan.PipelineError:
        nodes = {}
    types = pipeline.types()
    units = []
    data = plan.load()
    ready = {u["id"] for u in plan.available(data)}          # the app's Plan groups by it
    for u in data["units"]:
        t, n = types.get(u["type"], {}), nodes.get(u["id"], {})
        units.append({**{k: u.get(k) for k in ("id", "type", "phase", "status", "deps", "repo", "notes", "runner")},
                      "title": plan.title(u, lang),
                      "isolation": n.get("isolation") or t.get("isolation", "none"),
                      "tier": n.get("tier") or t.get("tier", "agentic-heavy"), "agent": n.get("runner"),
                      "approval": bool(n.get("approval")), "awaiting": plan.awaiting(u), "ready": u["id"] in ready,
                      "terminal": term.get(u["id"]), **sessions.board(u, busy)})
    latest = runs.ids(wiki=False)
    run = {**runs.summary(latest[0]), **runs.slots(latest[0])} if latest else None
    if run and not run["finished"] and run_stopped(run["run"], locked):
        run.update(finished=True, interrupted=True, running=[], waiting={})
    return {"units": units, "run": run, "interviews": docs.interview_mode() if docs.interview_mode_chosen() else None}


def stream_events(run_id: str, offset: int) -> Response:
    """Server-sent events: one message per run event, its id the byte offset after it. Ends with the run; for a plan
    run stopped from outside (run_stopped), once its log is read to the end; or after an hour with nothing new. A
    stopped run already read to its end is a 204, the one answer that stops a browser's EventSource from
    reconnecting."""
    from lib.harness.events import EventLog
    log = EventLog(CTX.runs / run_id / "events.jsonl")
    stopped = run_stopped(run_id)
    if stopped and not log.read_lines(offset):
        return Response(204, ctype=None)

    def follow(out: BinaryIO, offset: int = offset, stopped: bool = stopped) -> None:
        quiet = beat = looked = time.monotonic()
        try:
            while time.monotonic() - quiet < 3600:
                batch = log.read_lines(offset)
                for ev, offset in batch:
                    out.write(f"id: {offset}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8"))
                    if ev.get("type") == "run.finished":
                        out.flush()
                        return
                if batch:
                    out.flush()
                    quiet = time.monotonic()
                elif stopped:
                    return              # read once more after it was found stopped: nothing was left
                elif time.monotonic() - beat > 15:
                    out.write(b": keep-alive\n\n")
                    out.flush()
                    beat = time.monotonic()
                now = time.monotonic()
                if not batch and min(now - quiet, now - looked) > STOPPED_AFTER:
                    looked, stopped = now, run_stopped(run_id)
                time.sleep(0.3)
        except (BrokenPipeError, ConnectionResetError):
            return
    return event_stream(follow)


@route("GET", "/api/pipeline")
def get_pipeline(req: Request) -> Response:
    return json_response(api_pipeline(req.query.get("lang", "")))


@route("GET", "/api/runs")
def get_runs(req: Request) -> Response:
    from lib.harness import runs
    return json_response(runs.rows())


@route("POST", "/api/runs", access=Access.APP)
def post_runs(req: Request) -> Response:
    return json_response(*start_run(req.body))


@route("GET", "/api/runs/{run:[\\w.-]+}")
def get_run(req: Request) -> Response:
    from lib.harness import runs
    run = req.params["run"]
    if run not in runs.ids():
        return json_response({"error": f"no run {run}"}, 404)
    return json_response(runs.detail(run))


@route("GET", "/api/runs/{run:[\\w.-]+}/events")
def get_run_events(req: Request) -> Response:
    from lib.harness import runs
    run = req.params["run"]
    if run not in runs.ids():
        return json_response({"error": f"no run {run}"}, 404)
    return stream_events(run, int(req.headers.get("Last-Event-ID") or req.query.get("from") or 0))


@route("POST", "/api/runs/{run:[\\w.-]+}/cancel", access=Access.APP)
def post_run_cancel(req: Request) -> Response:
    from lib.harness import scheduler
    scheduler.request_cancel(req.params["run"])
    return json_response({"cancelling": req.params["run"]})


@route("POST", "/api/units/retry")
def post_unit_retry(req: Request) -> Response:
    return json_response(*retry_unit(req.body.get("unit", "")))


@route("POST", "/api/units/approve")
def post_unit_approve(req: Request) -> Response:
    return json_response(*approve_unit(req.body.get("unit", "")))


@route("GET", "/api/plan/cost")
def get_plan_cost(req: Request) -> Response:
    from lib.harness import ledger          # a read: the bill as the roll-ups have it, never a harvest
    return json_response(ledger.bill())


@route("POST", "/api/plan/cost", access=Access.APP)
def post_plan_cost(req: Request) -> Response:
    from lib.harness import ledger          # the app: this machine's sessions first, then the bill
    ledger.harvest()
    return json_response(ledger.bill())
