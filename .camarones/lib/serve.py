"""The Camarones portal server (stdlib, no Docker, no npm build).

Live mode (`camaron up`): people read the docs as they are right now, edit, confirm, comment and commit — the same
actions as the CLI, on the same files — and browse / rebuild the C4 explorer, the code graphs and the OpenWiki wikis.
Static mode (`up --static`): serves the read-only export (`portal`) exactly like nginx would.
Binds 127.0.0.1 only. Mutating calls need the X-Camarones header, which a cross-site page cannot send without a
CORS preflight this server never grants.

The portal is the team's viewer. Work that starts a process or calls a model (runs, wikis, builds, scans, CI files,
Ask's AI answer) belongs to the desktop app: it starts this server with CAMARONES_APP_TOKEN and sends the token on
each request (lib/appapi.py); without it those calls answer 403 with `"app": true`. With a token set, a request whose
Host is not this server is refused (a DNS-rebinding page would otherwise be same-origin)."""
from __future__ import annotations

import atexit, base64, datetime as dt, hmac, json, logging, mimetypes, os, re, signal, sys, threading, time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .common import CTX, KIT, ROOT, DOCS, CACHE, kill_tree, out
from . import docs, env, plan, sourcelinks, usage
from .app import portal_views
from .app.portal_views import APP, UI, UI_LIBS, doc_file, read, reviewer, status, tree
from .interfaces.http import inputs, router
from .interfaces.http.routes.analysis import (
    api_inventory, api_schemas, build, first_look, inventory_job, schemas_write, wiki,
)
from .interfaces.http.routes.board import kanban_marks, kanban_state
from .interfaces.http.routes.docs import api_ask, api_doc, api_search, create, write
from .interfaces.http.routes.machine import app_creds, app_kitdev, app_summary, sessions_setting, ui_lang
from .interfaces.http.routes.onboard import app_onboard
from .interfaces.http.routes.terminals import app_session, app_terminal, app_unit, shutdown, unit_terminals
from .interfaces.http.jobs import CANCEL, JOB_LOCK, JOBS, claim_job, fail_job, job_running, run_job, start_job
from .interfaces.http.messages import Request, Response
from .interfaces.http.router import APP_ONLY_MSG, Access

_log = logging.getLogger("camaron.serve")

DESKTOP = KIT / "desktop" / "renderer-build"  # the desktop app's own UI (desktop/renderer): its project windows load it here
SITE = CACHE / "site"
VENDOR_RE = re.compile(r"^/vendor/((?:@[\w.-]+/)?[\w.-]+)@([\w.+-]+)/([\w./+-]+)$")
STATIC = False
APP_GONE_GRACE = 10                          # seconds the normal stop has once the app is gone (watch_app)
APP_TOKEN = ""                               # set by the desktop app (CAMARONES_APP_TOKEN); empty: browser portal only
PORTAL_TOKEN = ""                            # set by `camaron up` (CAMARONES_PORTAL_TOKEN): lets this machine's browser write the board
APP_ONLY = re.compile(r"^/api/(runs|runs/[\w.-]+/cancel|wiki|build|inventory|schemas|ci|ask/answer|plan/cost)$")
STOPPED_AFTER = 5.0                          # seconds of quiet before a run's stream asks whether its run was stopped
mimetypes.add_type("text/javascript", ".js")    # Windows may map .js to text/plain in the registry
mimetypes.add_type("font/woff2", ".woff2")    # the portal theme fonts; older Pythons do not know the type


def api_c4_view(view: str) -> dict:
    """A C4 view's elements for the portal's panel: fields, draft/confirmed, and the relations in and out of each."""
    from . import c4edit
    idx = c4edit.index()
    shown = c4edit.view_elements(view, idx)
    keep = ("fqn", "kind", "title", "technology", "description", "tags", "draft", "confirmed", "confirmedBy",
            "confirmedAt", "file", "line")
    rel = lambda r: {k: r[k] for k in ("from", "to", "label", "kind")}  # noqa: E731
    return {"view": view, "kinds": idx["kinds"], "relKinds": idx["relKinds"], "editable": not STATIC,
            "all": [{"fqn": f, "title": e["title"]} for f, e in idx["elements"].items()],
            "elements": [{**{k: idx["elements"][f][k] for k in keep},
                          "out": [rel(r) for r in idx["relations"] if r["from"] == f],
                          "in": [rel(r) for r in idx["relations"] if r["to"] == f]} for f in shown]}


def kpis_miss(b: dict) -> dict:
    """A question nobody found an answer to: `question` adds it to the open questions for the next interview,
    `dismiss` just forgets it."""
    q, action = str(b.get("q") or ""), b.get("action")
    if q not in {m["q"] for m in usage.misses()}:
        raise KeyError(q)
    if action == "question":
        n = next(m["n"] for m in usage.misses() if m["q"] == q)
        f = DOCS / "interview" / "open-questions.md"
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("---\ntype: interview\ntitle: Open questions\ndescription: Questions agents could not answer "
                         "from the code; answer them in the next interview or inline.\n---\n# Open questions\n",
                         encoding="utf-8", newline="\n")
        text = f.read_text(encoding="utf-8")
        line = (f"- [ ] ({dt.date.today().isoformat()}, docs-gap) {q} — asked {n}× in the portal or by agents; "
                "no page answered it\n")
        f.write_text(text.rstrip("\n") + "\n" + line, encoding="utf-8", newline="\n")
    elif action != "dismiss":
        raise ValueError("action: question or dismiss")
    usage.forget(q)
    return {"misses": usage.misses()}


def c4_change(path: str, b: dict, by: str) -> dict:
    from . import c4edit
    if path == "element":
        changes = {k: b[k] for k in c4edit.EDITABLE if k in b}
        return c4edit.edit(b["fqn"], **changes)
    if path == "confirm":
        return {"confirmed": c4edit.confirm_view(b["view"], by) if b.get("view") else c4edit.confirm(b["fqns"], by)}
    if path == "relation" and b.get("action") == "add":
        return c4edit.add_relation(b["from"], b["to"], str(b.get("label") or ""), b.get("kind") or None)
    if path == "remove":
        return c4edit.remove_element(b["fqn"])
    if path == "relation" and b.get("action") == "remove":
        return c4edit.remove_relation(b["from"], b["to"], str(b.get("label") or ""))
    raise ValueError(f"unknown C4 change {path!r}")


def start_run(b: dict) -> tuple[dict, int]:
    """A documentation run as a background job of this server; refused while another run (CLI or portal) holds the
    run lock."""
    from .harness import scheduler
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
    from .harness import runs, scheduler
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
    from . import sessions
    from .harness import pipeline, runs, scheduler
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


def cancel_job(job_id: str) -> dict:
    """The app's cancel button: an in-process job (setup) is asked to stop between steps; a command job is killed."""
    ev = CANCEL.get(job_id)
    if ev is not None and JOBS.get(job_id, {}).get("status") == "running":
        ev.set()
        return {"cancelling": job_id}
    from . import appapi
    return appapi.cancel(job_id)


def api_interview(who: str = "") -> dict:
    """The team questionnaire for the portal's Interview view: the questions, the labels of the offline form (both
    languages), who answered and, with `who`, that person's own answers to edit them."""
    from . import questionnaire
    try:
        data = questionnaire.load()
    except ValueError as e:
        return {"available": False, "reason": str(e), "mode": docs.interview_mode(), "chosen": docs.interview_mode_chosen()}
    mine = next((r for n, r in questionnaire.responses().items() if who and n.strip().lower() == who.strip().lower()), None)
    return {"available": True, "mode": docs.interview_mode(), "chosen": docs.interview_mode_chosen(), "id": data["id"], "title": data.get("title") or "",
            "intro": data.get("intro") or "", "questions": data["questions"], "labels": questionnaire.LABELS,
            "status": questionnaire.status(), "user": reviewer(), "mine": mine}


def cdn_local(html: str) -> str:
    """Graph viewers pull libraries from CDNs; point them at /vendor/ (npm-fetched once) so they work offline."""
    return docs.CDN_RE.sub(lambda m: f"/vendor/{m.group(1)}@{m.group(2)}/{m.group(3)}", html)


def token_matches(got: str, want: str) -> bool:
    """Constant-time compare on bytes: a non-ASCII header makes compare_digest raise on str."""
    return hmac.compare_digest(got.encode("utf-8"), want.encode("utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "camarones"

    def log_message(self, fmt, *args):         # quiet: the server runs detached
        pass

    def send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, data, code: int = 200) -> None:
        self.send(code, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def file(self, f: Path, local_cdn: bool = False) -> None:
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        body = f.read_bytes()
        if local_cdn and f.suffix == ".html":
            body = cdn_local(body.decode("utf-8", errors="replace")).encode()
        self.send(200, body, ctype)

    def static(self, base: Path, rel: str, local_cdn: bool = False, spa: bool = False) -> bool:
        """Serve base/rel like a static host: dir → index.html; `spa` falls back to the app's index.html."""
        base = base.resolve()
        f = (base / rel.lstrip("/")).resolve()
        if base != f and base not in f.parents:
            return False
        for cand in (f, f / "index.html"):
            if cand.is_file():
                self.file(cand, local_cdn)
                return True
        if spa and (base / "index.html").is_file():
            self.file(base / "index.html", local_cdn)
            return True
        return False

    def not_found(self) -> None:
        self.send(404, b"not found", "text/plain")

    def reply(self, resp: Response) -> None:
        """Write a route's Response: an event stream after its headers, anything else as `send` writes it."""
        if resp.stream is not None:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            resp.stream(self.wfile)
            return
        self.send_response(resp.status)
        if resp.ctype is not None:
            self.send_header("Content-Type", resp.ctype)
            self.send_header("Content-Length", str(len(resp.body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in resp.headers.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD" and resp.body:
            self.wfile.write(resp.body)

    def routed(self, hit: router.Match, path: str, query: dict, body, by: str = "") -> Request:
        return Request("GET" if self.command in ("GET", "HEAD") else "POST", path, query, self.headers, body=body,
                       params=hit.params, by=by, is_app=self.is_app(), can_write=self.can_write(), static=STATIC)

    def do_HEAD(self):
        self.do_GET()

    def is_app(self) -> bool:
        return bool(APP_TOKEN) and token_matches(self.headers.get("X-Camaron-Token", ""), APP_TOKEN)

    def can_write(self) -> bool:
        """The app, or a browser that got the portal token from `camaron up`. The portal token never unlocks APP_ONLY."""
        return self.is_app() or (bool(PORTAL_TOKEN) and token_matches(self.headers.get("X-Camaron-Token", ""), PORTAL_TOKEN))

    def foreign_host(self) -> bool:
        if not (APP_TOKEN or PORTAL_TOKEN):
            return False
        port = self.server.server_address[1]
        ok = {f"127.0.0.1:{port}", f"localhost:{port}"} | ({"127.0.0.1", "localhost"} if port == 80 else set())
        return self.headers.get("Host", "") not in ok          # on port 80 the browser leaves the port out

    def stream_job(self, job: dict, offset: int) -> None:
        """Server-sent events of a job's log: one `line` per log line (its id the line count after it), then `end`."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            while True:
                lines, running = job["log"][offset:], job["status"] == "running"
                for line in lines:
                    offset += 1
                    ev = {"type": "line", "n": offset, "text": line}
                    self.wfile.write(f"id: {offset}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8"))
                if not running and offset >= len(job["log"]):
                    end = {"type": "end", "status": job["status"], "rc": job.get("rc"), "result": job.get("result")}
                    self.wfile.write(f"data: {json.dumps(end, ensure_ascii=False)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    return
                self.wfile.flush()
                time.sleep(0.2)
        except (BrokenPipeError, ConnectionResetError):
            return

    def api_app_get(self, name: str, q: dict):
        from . import appapi
        if name == "info":
            return self.json(appapi.info())
        if name == "catalog":
            return self.json(appapi.catalog())
        if name == "adr" or name.startswith("adr/"):
            from . import adr_api
            return self.json(*adr_api.get(name, q))
        if (m := re.fullmatch(r"jobs/([\w.-]+)/events", name)) and m.group(1) in JOBS:
            return self.stream_job(JOBS[m.group(1)], int(self.headers.get("Last-Event-ID") or q.get("from") or 0))
        self.json({"error": "not found"}, 404)

    def get_static_site(self, p: str) -> None:
        if p.startswith("/architecture/") and self.static(SITE / "architecture", p[len("/architecture/"):], spa=True):
            return
        if self.static(SITE, p):
            return
        if not Path(p).suffix:
            return self.file(SITE / "index.html")
        self.not_found()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        p = urllib.parse.unquote(u.path)
        if self.foreign_host():
            return self.json({"error": "forbidden host"}, 403)
        try:
            hit = router.load().match("GET", p)
            if (p.startswith("/api/app/") or (hit and hit.route.access == Access.APP)) and not self.is_app():
                return self.json({"error": APP_ONLY_MSG, "app": True}, 403)
            if hit and (not STATIC or p.startswith("/api/app/") or hit.route.static):
                return self.reply(hit.route.handler(self.routed(hit, p, q, {})))
            if p.startswith("/api/app/"):
                return self.api_app_get(p[len("/api/app/"):], q)
            if p == "/firstlook":                     # the C4 draft's interactive view (read-only, like the docs)
                from . import onboard
                f = onboard.last_draft().get("html")
                return self.file(Path(f), local_cdn=True) if f and Path(f).is_file() else self.not_found()
            if STATIC:
                return self.get_static_site(p)
            if p.startswith("/api/"):
                return self.api_get(p[len("/api/"):], q)
            if p.startswith("/raw/wikis/"):           # images next to a wiki page (wikis/<repo>/<page>)
                repo, _, rel = p[len("/raw/wikis/"):].partition("/")
                ok = repo in docs.repo_names() and self.static(docs.wiki_dir(repo), rel)
                return ok or self.not_found()
            if p.startswith("/raw/"):                 # images and diagrams referenced by the docs
                return self.static(DOCS, p[len("/raw/"):]) or self.not_found()
            if m := VENDOR_RE.match(p):
                f = docs.vendor_file(*m.groups())
                if f:
                    return self.file(f)
                return self.send(302, b"", "text/plain", {"Location": f"https://cdn.jsdelivr.net/npm/{m.group(1)}@"
                                                                      f"{m.group(2)}/{m.group(3)}"})
            if p.startswith("/architecture/"):
                return self.static(env.VIEWERS / "architecture", p[len("/architecture/"):], spa=True) or self.not_found()
            if m := re.match(r"^/code-graph/(?:([\w.-]+)/?)?$", p):
                f = env.code_graphs().get(m.group(1) or "all")
                return self.file(f, local_cdn=True) if f else self.not_found()
            if m := re.match(r"^/wiki-graph/([\w.-]+)/(.*)$", p):
                return self.static(env.VIEWERS / "wiki-graph" / m.group(1), m.group(2), local_cdn=True) or self.not_found()
            if p == "/next" or p.startswith("/next/"):            # the preview address of 3.26–4.16: one portal now
                return self.send(301, b"", "text/plain", {"Location": "/"})
            if p == "/desktop":                                   # its assets are relative to /desktop/
                return self.send(301, b"", "text/plain", {"Location": "/desktop/"})
            if p.startswith("/desktop/"):
                return self.static(DESKTOP, p[len("/desktop/"):], spa=True) or self.not_found()
            if p in ("/", "/index.html"):
                return self.file(APP / "index.html")
            if self.static(APP, p):
                return
            if not Path(p).suffix:
                return self.file(APP / "index.html")
            self.not_found()
        except KeyError as e:
            self.json({"error": f"missing or unknown: {e}"}, 404)
        except Exception as e:  # noqa: BLE001
            self.json({"error": f"{type(e).__name__}: {e}"}, 500)

    def api_get(self, name: str, q: dict):
        if name == "jobs":
            from . import appapi
            return self.json([{**{k: v for k, v in j.items() if k != "log"}, "stoppable": appapi.stoppable(j["id"])}
                              for j in list(JOBS.values())])
        if name == "pipeline":
            return self.json(api_pipeline(q.get("lang", "")))
        if name == "interview":
            return self.json(api_interview(q.get("who", "")))
        if name == "sync":
            return self.json(env.sync_status(fetch=q.get("fetch") == "1"))
        if name == "kpis":
            from .harness import kpis
            return self.json(kpis.dashboard())
        if name == "plan/cost":                 # a read: the bill as the roll-ups have it, never a harvest
            from .harness import ledger
            return self.json(ledger.bill())
        if name == "c4/view":
            return self.json(api_c4_view(q.get("id", "")))
        if name == "runs":
            from .harness import runs
            return self.json(runs.rows())
        if m := re.fullmatch(r"runs/([\w.-]+)(/events)?", name):
            from .harness import runs
            if m.group(1) not in runs.ids():
                return self.json({"error": f"no run {m.group(1)}"}, 404)
            if m.group(2):
                return self.stream_events(m.group(1), int(self.headers.get("Last-Event-ID") or q.get("from") or 0))
            return self.json(runs.detail(m.group(1)))
        if name.startswith("jobs/") and name[5:] in JOBS:
            j = JOBS[name[5:]]
            since = int(q.get("since", 0))
            return self.json({**j, "log": j["log"][since:], "lines": len(j["log"])})
        self.json({"error": "not found"}, 404)

    def stream_events(self, run_id: str, offset: int) -> None:
        """Server-sent events: one message per run event, its id the byte offset after it. Ends with the run; for a
        plan run stopped from outside (run_stopped), once its log is read to the end; or after an hour with nothing
        new. A stopped run already read to its end is a 204, the one answer that stops a browser's EventSource from
        reconnecting."""
        from .harness.events import EventLog
        log = EventLog(CTX.runs / run_id / "events.jsonl")
        stopped = run_stopped(run_id)
        if stopped and not log.read_lines(offset):
            self.send_response(204)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        quiet = beat = looked = time.monotonic()
        try:
            while time.monotonic() - quiet < 3600:
                batch = log.read_lines(offset)
                for ev, offset in batch:
                    self.wfile.write(f"id: {offset}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8"))
                    if ev.get("type") == "run.finished":
                        self.wfile.flush()
                        return
                if batch:
                    self.wfile.flush()
                    quiet = time.monotonic()
                elif stopped:
                    return              # read once more after it was found stopped: nothing was left
                elif time.monotonic() - beat > 15:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    beat = time.monotonic()
                now = time.monotonic()
                if not batch and min(now - quiet, now - looked) > STOPPED_AFTER:
                    looked, stopped = now, run_stopped(run_id)
                time.sleep(0.3)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_PUT(self):
        self.do_POST()

    def do_POST(self):
        try:                    # read the body first: answering before it is read resets the connection on Windows
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        except ValueError:
            raw = b""
        if STATIC:
            return self.json({"error": "read-only portal — run `camaron up` to edit"}, 405)
        if self.headers.get("X-Camarones") != "1" or self.foreign_host():
            return self.json({"error": "forbidden"}, 403)
        p = urllib.parse.urlparse(self.path).path
        hit = router.load().match("POST", p)
        if (APP_ONLY.match(p) or p.startswith("/api/app/") or (hit and hit.route.access == Access.APP)) \
                and not self.is_app():
            return self.json({"error": APP_ONLY_MSG, "app": True}, 403)
        try:
            b = json.loads(raw or b"{}")
            if hit:
                by = (b.get("by") or reviewer()).strip() if hit.route.by else ""
                if hit.route.access == Access.PORTAL and not self.can_write():
                    return self.json({"error": hit.route.refusal, "token": True}, 403)
                return self.reply(hit.route.handler(self.routed(hit, p, {}, b, by)))
            by = (b.get("by") or reviewer()).strip()
            if p == "/api/app/cmd":
                from . import appapi
                try:
                    return self.json(appapi.start(b, start_job))
                except PermissionError as e:
                    return self.json({"error": str(e), "confirm": True}, 409)
                except KeyError as e:
                    return self.json({"error": f"unknown command {e}"}, 404)
            if m := re.fullmatch(r"/api/app/adr/([a-z]+)", p):     # the decisions (lib/adr_api.py)
                from . import adr_api
                return self.json(*adr_api.post(m.group(1), b, by))
            if m := re.fullmatch(r"/api/app/jobs/([\w.-]+)/cancel", p):
                return self.json(cancel_job(m.group(1)))
            if p == "/api/sync/share":             # the team action: checkpoint, pull the team's work, push
                return self.json({"result": env.share(log=lambda _: None), "sync": env.sync_status()})
            if p == "/api/interview/answer":
                from . import questionnaire
                questionnaire.answer(b)
                return self.json(questionnaire.status())
            if p == "/api/runs":
                return self.json(*start_run(b))
            if m := re.fullmatch(r"/api/runs/([\w.-]+)/cancel", p):
                from .harness import scheduler
                scheduler.request_cancel(m.group(1))
                return self.json({"cancelling": m.group(1)})
            if p == "/api/units/retry":
                return self.json(*retry_unit(b.get("unit", "")))
            if p == "/api/plan/cost":            # the app: this machine's sessions first, then the bill
                from .harness import ledger
                ledger.harvest()
                return self.json(ledger.bill())
            if p == "/api/kpis/miss":
                try:
                    return self.json(kpis_miss(b))
                except KeyError as e:
                    return self.json({"error": f"not in the list: {e}"}, 404)
            if m := re.fullmatch(r"/api/c4/(element|confirm|relation|remove)", p):
                try:
                    return self.json(c4_change(m.group(1), b, by))
                except KeyError as e:
                    return self.json({"error": f"not in the model: {e}"}, 404)
            if p == "/api/units/approve":
                return self.json(*approve_unit(b.get("unit", "")))
            self.json({"error": "not found"}, 404)
        except (KeyError, ValueError, RuntimeError) as e:
            self.json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            self.json({"error": f"{type(e).__name__}: {e}"}, 500)


def take_tokens() -> None:
    """Read this server's tokens and take them out of the environment, so no command, run or agent it starts inherits them."""
    global APP_TOKEN, PORTAL_TOKEN
    APP_TOKEN = os.environ.pop("CAMARONES_APP_TOKEN", "")
    PORTAL_TOKEN = os.environ.pop("CAMARONES_PORTAL_TOKEN", "")


def watch_app() -> None:
    """Stops this server when the app that started it is gone. A crash or a force-quit runs none of the app's code, so
    the app holds the other end of our stdin, the system closes it, and the read here returns. The stop is the app's own,
    what the server started included; one that hangs ends with the process after APP_GONE_GRACE s. What this server
    starts reads nothing from stdin, as before: nobody writes to this pipe, so a child inheriting it would wait for the
    app to end (`claude -p` reads its stdin)."""
    pipe = os.dup(0)
    nothing = os.open(os.devnull, os.O_RDONLY)
    os.dup2(nothing, 0)
    os.close(nothing)

    def wait() -> None:
        try:
            while os.read(pipe, 4096):
                pass
        except OSError:
            pass
        kill_tree(os.getpid())
        time.sleep(APP_GONE_GRACE)
        os._exit(1)
    threading.Thread(target=wait, daemon=True, name="app lifeline").start()


def run_server(port: int = 8080, static: bool = False) -> None:
    global STATIC
    STATIC = static
    take_tokens()
    if static and not (SITE / "index.html").exists():
        raise RuntimeError("the portal is not exported yet — run `camaron portal` first")
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    atexit.register(shutdown)                   # no agent outlives its server: the app's stop, Ctrl+C, an error
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))       # how the app stops it on POSIX; SystemExit runs atexit
    if os.environ.pop("CAMARONES_LIFELINE", ""):
        watch_app()
    if APP_TOKEN:                            # the app reads the port (0 = any free one) from this first line
        print(json.dumps({"ready": True, "port": httpd.server_address[1]}), flush=True)
        sys.stdout.flush()
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
