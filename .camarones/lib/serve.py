"""The Camarones portal server (stdlib, no Docker, no npm build).

Live mode (`camaron up`): people read the docs as they are right now, edit, confirm, comment and commit — the same
actions as the CLI, on the same files — and browse / rebuild the C4 explorer, the code graphs and the OpenWiki wikis.
Static mode (`up --static`): serves the read-only export (`portal`) exactly like nginx would.
Binds 127.0.0.1 only. Mutating calls need the X-Camarones header, which a cross-site page cannot send without a
CORS preflight this server never grants."""
from __future__ import annotations

import itertools, json, mimetypes, re, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .common import CTX, KIT, ROOT, DOCS, CACHE, VERSIONS, out, rel_file
from . import codemap, docs, env, plan, usage

APP = KIT / "portal" / "app-build"           # the portal: React views + the docs views (portal/app), built in the kit's CI
UI = APP                                     # the old name, kept for callers
SITE = CACHE / "site"
UI_LIBS = (("marked", "15.0.12", "lib/marked.umd.js"), ("dompurify", "3.2.6", "dist/purify.min.js"),
           ("mermaid", "11.4.1", "dist/mermaid.min.js"), ("@highlightjs/cdn-assets", "11.11.1", "highlight.min.js"),
           ("vis-network", "9.1.6", "standalone/umd/vis-network.min.js"))     # the code map, loaded on its tab only
VENDOR_RE = re.compile(r"^/vendor/((?:@[\w.-]+/)?[\w.-]+)@([\w.+-]+)/([\w./+-]+)$")
STATIC = False
mimetypes.add_type("text/javascript", ".js")    # Windows may map .js to text/plain in the registry


def reviewer() -> str:
    return out(["git", "config", "user.name"], cwd=ROOT) or "human"


def doc_file(path: str, lang: str = "") -> Path:
    """Only pages the docs model knows about (or their translations) can be read or written through the API."""
    canon = dict(docs.iter_docs())
    if path not in canon:
        raise KeyError(f"unknown page {path}")
    if not lang:
        return canon[path]
    f = (DOCS / "i18n" / lang / path).resolve()
    if DOCS.resolve() not in f.parents:
        raise KeyError(path)
    return f


def tree() -> dict:
    rows = docs.collect()
    ws = docs.workspace()
    return {"project": ws["project"]["name"], "langs": ws["project"].get("translations", []), "reviewer": reviewer(),
            "summary": docs.summary(rows), "feedback": len(docs.pending_feedback()), "kit": VERSIONS["kit"],
            "repos": docs.repo_names(), "codeGraphs": list(env.code_graphs()), "engines": env.wiki_engines(),
            "sections": docs.SECTIONS, "views": env.c4_views(), "codeMaps": codemap.available(), "editBase": "",
            "docs": [{k: r[k] for k in ("path", "file", "title", "description", "type", "space", "trust", "owner", "i18n",
                                        "orphan_sources")} for r in rows]}


def read(path: str, lang: str = "") -> dict:
    f = doc_file(path, lang)
    raw = f.read_text(encoding="utf-8") if f.exists() else ""
    fm, body = docs.split_fm(raw)
    row = next((r for r in docs.collect() if r["path"] == path), {})
    return {"path": path, "lang": lang, "file": rel_file(f), "raw": raw, "exists": f.exists(),
            "title": fm.get("title") or docs.first_heading(body) or Path(path).stem, "trust": row.get("trust"),
            "owner": row.get("owner"), "sources": fm.get("x-sources") or [], "confirmed": fm.get("x-confirmed"),
            "fresh": row.get("fresh"), "freshness": row.get("freshness"),
            "feedback": [l for l in docs.pending_feedback() if f"`{row.get('file')}`" in l]}


def api_ask(question: str) -> dict:
    """Ask the docs (R34): the sections that best answer a question, each with its citation, trust and freshness.
    No model: the same retrieval as the MCP `ask`, through the same freshness gate."""
    from .harness import freshness
    hits = docs.search(question, 20) if question.strip() else []
    usage.record("portal:ask", channel="human", hit=bool(hits))
    rows, out = {r["path"]: r for r in docs.collect()}, []
    for h in hits:
        r = rows.get(h["path"], {})
        ok, notice = freshness.gate(h["path"], r.get("trust", "draft"), r.get("freshness"))
        f = dict(docs.iter_docs()).get(h["path"])
        if not f:
            continue
        body = docs.split_fm(f.read_text(encoding="utf-8"))[1]
        found = docs.section_text(body, h["section"]) if h.get("section") else None
        tldr = docs.tldr(body)
        whole = body.replace(tldr, "", 1) if tldr else body              # the portal shows the TL;DR above the text
        out.append({"cite": h["path"] + (f"#{h['section']}" if found else ""), "title": h["title"],
                    "trust": r.get("trust"), "fresh": r.get("fresh"), "notice": notice, "withheld_for_agents": not ok,
                    "tldr": tldr, "text": found[1] if found else whole.strip()[:3000]})
        if len(out) >= 3:
            break
    from . import answers
    readable = any(not s["withheld_for_agents"] for s in out)          # the AI only reads what agents may read
    return {"question": question, "sections": out, "ai": answers.runner() if readable else None}


def api_doc(q: dict) -> dict:
    """A page the reader opened (`track`), not the extra reads the UI does for fallbacks and the home page."""
    d = read(q["path"], q.get("lang", ""))
    if q.get("track"):
        usage.record("portal:doc", channel="human", page=q["path"])
    return d


def api_search(q: dict) -> list[dict]:
    """Only full searches (`track`) count: the palette searches on every keystroke."""
    hits = docs.search(q.get("q", ""))
    if q.get("track"):
        usage.record("portal:search", channel="human", hit=bool(hits))
    return hits


def write(path: str, raw: str, lang: str = "") -> dict:
    f = doc_file(path, lang)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(raw if raw.endswith("\n") else raw + "\n", encoding="utf-8")
    return read(path, lang)


def create(path: str, title: str) -> dict:
    path = path.strip().lstrip("/").removeprefix("docs/")
    if not re.fullmatch(r"[\w./-]+\.md", path) or ".." in path:
        raise ValueError("path must look like section/page.md")
    f = DOCS / path
    if f.exists():
        raise ValueError(f"{path} already exists")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(docs.join_fm({"title": title, "description": "", "type": "guide", "x-owner": "human"},
                              f"\n# {title}\n\n"), encoding="utf-8")
    return read(path)


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

    def go(log):
        scheduler.run_parallel(lang=b.get("lang") or "en", max_parallel=parallel, per_runner=slots,
                               max_units=max_units, echo=log)
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


def api_pipeline() -> dict:
    """The plan as a graph for the Pipeline tab: every unit with its status and dependencies, how it runs (isolation,
    tier, runner), and the latest run."""
    from .harness import pipeline, runs
    try:
        nodes = {u["id"]: u for u in plan.pipeline_units()}
    except plan.PipelineError:
        nodes = {}
    types = pipeline.types()
    units = []
    for u in plan.load()["units"]:
        t, n = types.get(u["type"], {}), nodes.get(u["id"], {})
        units.append({**{k: u.get(k) for k in ("id", "title", "type", "phase", "status", "deps", "repo", "notes", "runner")},
                      "isolation": n.get("isolation") or t.get("isolation", "none"),
                      "tier": n.get("tier") or t.get("tier", "agentic-heavy"), "agent": n.get("runner"),
                      "approval": bool(n.get("approval")), "awaiting": plan.awaiting(u)})
    latest = runs.ids()
    return {"units": units, "run": runs.summary(latest[0]) if latest else None}


def status(check: bool = True) -> dict:
    """`check=False` skips the full quality check (seconds on a big project): the page shows the rest at once."""
    return {"queue": [{k: r[k] for k in ("path", "title", "trust", "type")} for r in docs.review_queue()],
            "feedback": docs.pending_feedback(), "changes": docs.changes(),
            "check": dict(zip(("errors", "warnings"), docs.check())) if check else None,
            "plan": dict(zip(("done", "total"), plan.progress()))}


# ---------- background jobs (builds and wiki generation run for minutes) ----------
JOBS: dict[str, dict] = {}
JOB_IDS = itertools.count(1)
JOB_LOCK = threading.Lock()


def start_job(kind: str, label: str, fn) -> dict:
    """One job per kind at a time: a second click attaches to the running one."""
    with JOB_LOCK:
        running = next((j for j in JOBS.values() if j["kind"] == kind and j["status"] == "running"), None)
        if running:
            return running
        job = {"id": str(next(JOB_IDS)), "kind": kind, "label": label, "status": "running", "log": [],
               "started": time.time(), "ended": None}
        JOBS[job["id"]] = job

    def work():
        try:
            ok = fn(job["log"].append)
            job["status"] = "done" if ok is not False else "failed"
        except Exception as e:  # noqa: BLE001
            job["log"].append(f"⚠ {e}")
            job["status"] = "failed"
        job["ended"] = time.time()

    threading.Thread(target=work, daemon=True).start()
    return job


def build(b: dict) -> dict:
    what, repo = b.get("what"), b.get("repo") or ""
    if what == "c4":
        return start_job("c4", "C4 explorer", lambda log: env.build_c4(log=log))
    if what == "graph":
        return start_job("graph", "Code graphs", lambda log: env.build_graphs(log=log))
    if what == "wiki-graph" and repo in docs.repo_names():
        return start_job("wiki-graph", f"Wiki graph {repo}", lambda log: env.wiki_graph(repo, log=log))
    raise ValueError(f"unknown build {what!r}")


def wiki(b: dict) -> dict:
    repo, mode, engine = b.get("repo", ""), b.get("mode", ""), b.get("engine", "")
    if repo not in docs.repo_names() or mode not in ("", "init", "update"):
        raise ValueError("unknown repo or mode")
    return start_job("wiki", f"OpenWiki {repo}", lambda log: env.openwiki_generate(repo, mode, log, engine))


def cdn_local(html: str) -> str:
    """Graph viewers pull libraries from CDNs; point them at /vendor/ (npm-fetched once) so they work offline."""
    return docs.CDN_RE.sub(lambda m: f"/vendor/{m.group(1)}@{m.group(2)}/{m.group(3)}", html)


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

    def do_HEAD(self):
        self.do_GET()

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
        try:
            if STATIC:
                return self.get_static_site(p)
            if p.startswith("/api/"):
                return self.api_get(p[len("/api/"):], q)
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
        if name == "tree":
            return self.json(tree())
        if name == "doc":
            return self.json(api_doc(q))
        if name == "status":
            return self.json(status(check=q.get("check") != "0"))
        if name == "check":
            return self.json(dict(zip(("errors", "warnings"), docs.check())))
        if name == "search":
            return self.json(api_search(q))
        if name == "wikis":
            return self.json(env.wikis())
        if name == "codemap":
            m = codemap.load(q.get("repo", "")) if q.get("repo") in docs.repo_names() else None
            return self.json(m) if m else self.json({"error": "no code map"}, 404)
        if name == "viewers":
            return self.json(env.viewers())
        if name == "jobs":
            return self.json([{k: v for k, v in j.items() if k != "log"} for j in JOBS.values()])
        if name == "pipeline":
            return self.json(api_pipeline())
        if name == "ask":
            return self.json(api_ask(q.get("q", "")))
        if name == "boards":
            from . import boards
            return self.json(boards.boards())
        if name == "board":
            from . import boards
            return self.json(boards.read(q.get("name", "")))
        if name == "sketch":
            from . import boards
            return self.json(boards.sketch(q.get("view", "")))
        if name == "reviews":
            from . import review
            return self.json(review.open_requests())
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
        """Server-sent events: one message per run event, its id the byte offset after it. Ends with the run, or
        after an hour with nothing new (a run killed without run.finished)."""
        from .harness.events import EventLog
        log = EventLog(CTX.runs / run_id / "events.jsonl")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        quiet = beat = time.monotonic()
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
                elif time.monotonic() - beat > 15:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    beat = time.monotonic()
                time.sleep(0.3)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_PUT(self):
        self.do_POST()

    def do_POST(self):
        if STATIC:
            return self.json({"error": "read-only portal — run `camaron up` to edit"}, 405)
        if self.headers.get("X-Camarones") != "1":
            return self.json({"error": "forbidden"}, 403)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            b = json.loads(self.rfile.read(n) or b"{}")
            p = urllib.parse.urlparse(self.path).path
            by = (b.get("by") or reviewer()).strip()
            if p == "/api/doc":
                return self.json(write(b["path"], b["raw"], b.get("lang", "")))
            if p == "/api/new":
                return self.json(create(b["path"], b["title"]))
            if p == "/api/confirm":
                docs.confirm([str(doc_file(b["path"], b.get("lang", "")))], by)
                return self.json(read(b["path"], b.get("lang", "")))
            if p == "/api/feedback":
                from . import review
                review.comment(b["path"], b["text"], by, b.get("slug", ""), b.get("snippet", ""))
                plan.ensure("review-fixes", "review-fixes")
                return self.json(read(b["path"]))
            if p == "/api/board":
                from . import boards
                return self.json(boards.save(b.get("name", ""), b.get("scene")))
            if p == "/api/review/decide":
                from . import review
                return self.json(review.decide(b["id"], b["decision"], by, b.get("comments", "")))
            if p == "/api/commit":
                docs.llms()
                ok = env.checkpoint_commit(b.get("message") or "docs edited in the portal")
                return self.json({"committed": ok, "head": out(["git", "log", "-1", "--format=%h %s"], cwd=ROOT)})
            if p == "/api/build":
                return self.json(build(b))
            if p == "/api/wiki":
                return self.json(wiki(b))
            if p == "/api/runs":
                return self.json(*start_run(b))
            if m := re.fullmatch(r"/api/runs/([\w.-]+)/cancel", p):
                from .harness import scheduler
                scheduler.request_cancel(m.group(1))
                return self.json({"cancelling": m.group(1)})
            if p == "/api/units/retry":
                return self.json(*retry_unit(b.get("unit", "")))
            if p == "/api/ask/answer":
                from . import answers
                return self.json(answers.answer(str(b.get("q", ""))))
            if p == "/api/units/approve":
                return self.json(*approve_unit(b.get("unit", "")))
            self.json({"error": "not found"}, 404)
        except (KeyError, ValueError, RuntimeError) as e:
            self.json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            self.json({"error": f"{type(e).__name__}: {e}"}, 500)


def run_server(port: int = 8080, static: bool = False) -> None:
    global STATIC
    STATIC = static
    if static and not (SITE / "index.html").exists():
        raise RuntimeError("the portal is not exported yet — run `camaron portal` first")
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
