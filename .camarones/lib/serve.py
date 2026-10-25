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

import datetime as dt, hmac, itertools, json, mimetypes, os, re, sys, threading, time, urllib.parse
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
APP_TOKEN = ""                               # set by the desktop app (CAMARONES_APP_TOKEN); empty: browser portal only
PORTAL_TOKEN = ""                            # set by `camaron up` (CAMARONES_PORTAL_TOKEN): lets this machine's browser write the board
APP_ONLY = re.compile(r"^/api/(runs|runs/[\w.-]+/cancel|wiki|build|inventory|schemas|ci|ask/answer)$")
APP_ONLY_MSG = "this runs on your machine: open it in the desktop app (`camaron app`)"
mimetypes.add_type("text/javascript", ".js")    # Windows may map .js to text/plain in the registry
mimetypes.add_type("font/woff2", ".woff2")    # the portal theme fonts; older Pythons do not know the type


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
            "repos": docs.repo_names(), "codeGraphs": list(env.code_graphs()), "engines": env.wiki_engines(), "engineHelp": env.wiki_engine_help(), "kitGuides": sorted(docs.kit_guides()),
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
    usage.record("portal:ask", channel="human", hit=bool(hits), query=question)
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


def api_schemas() -> dict:
    """Each repo's tables and collections (lib/schemas.py) with the same markdown its data page holds."""
    from . import schemas
    out = []
    for name, r in schemas.scan().items():
        page = schemas.PAGE.format(repo=name)
        out.append({"repo": name, "tools": r["tools"], "stores": [{"kind": s["kind"], "engines": s["engines"],
                                                                   "entities": s["entities"]} for s in r["stores"]],
                    "entities": sum(len(s["entities"]) for s in r["stores"]), "markdown": schemas.block_body(r),
                    "page": page if (DOCS / page).is_file() else None})
    return {"repos": out}


def schemas_write() -> dict:
    from . import genblocks, schemas
    written = schemas.write_pages(log=lambda _: None)
    genblocks.refresh()
    docs.llms()
    return {"written": written}


def api_inventory() -> dict:
    """The last inventory (docs/.work/inventory.json), or a fresh scan of the manifests when there is none yet."""
    from . import inventory
    return inventory.load() or inventory.scan()


def inventory_job(b: dict) -> dict:
    from . import inventory
    cves = bool(b.get("cves"))
    return start_job("inventory", "Libraries" + (" + vulnerabilities" if cves else ""),
                     lambda log: bool(inventory.run(log=log, cves=cves)))


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
    if path == "relation" and b.get("action") == "remove":
        return c4edit.remove_relation(b["from"], b["to"], str(b.get("label") or ""))
    raise ValueError(f"unknown C4 change {path!r}")


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
        usage.record("portal:search", channel="human", hit=bool(hits), query=q.get("q", ""))
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


def app_kitdev(b: dict) -> tuple[dict, int]:
    """A Kit dev task (lib/kitdev.py) as a job, outside this project's environment (the sandbox is its own project)."""
    from . import appapi, kitdev
    task = str(b.get("task", ""))
    try:
        if task == "sandbox-open":
            return {"opened": kitdev.open_wizard()}, 200
        argv, cwd = kitdev.command(task, b)
    except PermissionError as e:
        return {"error": str(e)}, 403
    env = {k: v for k, v in os.environ.items() if k not in ("CAMARONES_ROOT", "CAMARONES_APP_TOKEN")}
    label = " ".join([Path(argv[0]).stem, *argv[1:]])
    return appapi.stream_job(start_job, f"kitdev:{task}", argv, cwd, {**env, "PYTHONUTF8": "1"}, label=label,
                             shown=[Path(argv[0]).stem, *argv[1:]]), 200


def app_creds(action: str, b: dict) -> tuple[dict, int]:
    """The desktop app's tokens for GitLab / GitHub (lib/creds.py, the OS keychain): saved only after the forge accepts
    them (or with `anyway`), tested, or deleted. A token is never sent back."""
    from . import creds
    raw = str(b.get("host") or "").strip()
    host = creds.host_of(raw if "://" in raw else f"https://{raw}") or raw
    if not host or host.startswith("-") or "/" in host:
        return {"error": "host: like gitlab.example.com"}, 400
    if action == "/delete":
        creds.delete(host)
        return {"deleted": host}, 200
    if action == "/test":
        tok = creds.get(host)
        if not tok:
            return {"error": f"no token saved for {host}"}, 404
        ok, info = creds.verify(host, creds.hosts().get(host, {}).get("kind") or creds.guess_kind(host), tok)
        return {"ok": ok, "info": info}, 200
    if action:
        return {"error": "not found"}, 404
    kind, token = b.get("kind") or creds.guess_kind(host), str(b.get("token") or "").strip()
    if kind not in ("gitlab", "github") or not token:
        return {"error": "kind (gitlab or github) and token are required"}, 400
    ok, info = creds.verify(host, kind, token)
    if not ok and not b.get("anyway"):
        return {"error": f"{host} did not accept the token: {info}"}, 400
    where = creds.save(host, kind, token, info if ok else "")
    return {"host": host, "user": info if ok else "", "where": where}, 200


def api_interview(who: str = "") -> dict:
    """The team questionnaire for the portal's Interview view: the questions, the labels of the offline form (both
    languages), who answered and, with `who`, that person's own answers to edit them."""
    from . import questionnaire
    try:
        data = questionnaire.load()
    except ValueError as e:
        return {"available": False, "reason": str(e), "mode": docs.interview_mode()}
    mine = next((r for n, r in questionnaire.responses().items() if who and n.strip().lower() == who.strip().lower()), None)
    return {"available": True, "mode": docs.interview_mode(), "id": data["id"], "title": data.get("title") or "",
            "intro": data.get("intro") or "", "questions": data["questions"], "labels": questionnaire.LABELS,
            "status": questionnaire.status(), "user": reviewer(), "mine": mine}


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
            if isinstance(ok, dict):                 # a command job: its exit code decides
                job.update(ok)
                ok = ok.get("rc", 0) == 0
            job["status"] = "done" if ok is not False else "failed"
        except Exception as e:  # noqa: BLE001
            job["log"].append(f"⚠ {e}")
            job["status"] = "failed"
        job["ended"] = time.time()

    threading.Thread(target=work, daemon=True).start()
    return job


def first_look(log) -> bool:
    """A fresh project's first pages without AI, from the static scan: the C4 draft and its page, the stack and tools,
    llms.txt; then the C4 explorer when LikeC4 is installed. What the empty Docs and Architecture tabs offer."""
    from . import quickarch, radar
    quickarch.save(quickarch.draft(log=log))
    radar.run(log=log)
    from . import inventory, schemas
    inventory.run(log=log)
    schemas.write_pages(log=log)
    docs.llms()
    if env.which("likec4"):
        env.build_c4(log=log)
    log("✔ first look written: architecture/first-look.md, overview/tooling.md and the C4 draft")
    return True


def build(b: dict) -> dict:
    what, repo = b.get("what"), b.get("repo") or ""
    if what == "first-look":
        return start_job("first-look", "First look (no AI)", first_look)
    if what == "c4":
        return start_job("c4", "C4 explorer", lambda log: env.build_c4(log=log))
    if what == "graph":
        return start_job("graph", "Code graphs", lambda log: env.build_graphs(log=log))
    if what == "wiki-graph" and repo in docs.repo_names():
        return start_job("wiki-graph", f"Wiki graph {repo}", lambda log: env.wiki_graph(repo, log=log))
    raise ValueError(f"unknown build {what!r}")


def wiki(b: dict) -> dict:
    """`choose`: add the repo to the ones with a wiki (its plan unit comes back); `starter`: write a starter brief
    (no AI) when repo-brief has not written one. The card says both before the click."""
    repo, mode, engine = b.get("repo", ""), b.get("mode", ""), b.get("engine", "")
    if repo not in docs.repo_names() or mode not in ("", "init", "update"):
        raise ValueError("unknown repo or mode")
    if repo not in docs.wiki_repos() and not env.wiki_pages(repo):
        if not b.get("choose"):
            raise ValueError(f"{repo} is not chosen for a wiki")
        docs.set_wiki_repos([*docs.wiki_repos(), repo])
        plan.sync()
    if b.get("starter"):
        env.starter_brief(repo)
    return start_job("wiki", f"OpenWiki {repo}", lambda log: env.openwiki_generate(repo, mode, log, engine))


def cdn_local(html: str) -> str:
    """Graph viewers pull libraries from CDNs; point them at /vendor/ (npm-fetched once) so they work offline."""
    return docs.CDN_RE.sub(lambda m: f"/vendor/{m.group(1)}@{m.group(2)}/{m.group(3)}", html)


def token_matches(got: str, want: str) -> bool:
    """Constant-time compare on bytes: a non-ASCII header makes compare_digest raise on str."""
    return hmac.compare_digest(got.encode("utf-8"), want.encode("utf-8"))


def _text(b: dict, key: str, required: bool = False) -> str | None:
    v = b.get(key)
    if v is None and not required:
        return None
    if not isinstance(v, str):
        raise ValueError(f"{key} must be text")
    return v


def _text_list(b: dict, key: str) -> list[str]:
    v = b.get(key)
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ValueError(f"{key} must be a list of text")
    return v


def _doc_refs(b: dict) -> list[str]:
    v = b.get("docs")
    if v is None:
        return []
    if not isinstance(v, list):
        raise ValueError("docs must be a list")
    refs = []
    for d in v:
        if isinstance(d, str):
            refs.append(d)
        elif isinstance(d, dict) and isinstance(d.get("path"), str) and isinstance(d.get("section", ""), (str, type(None))):
            refs.append(f"{d['path']}#{d['section']}" if d.get("section") else d["path"])
        else:
            raise ValueError("each doc is a text ref or {path, section} with text values")
    return refs


def kanban_state(writable: bool) -> dict:
    """The whole board for the Board view; read-only, so a GET never creates the layout."""
    from . import kanban
    from .kanban import ops
    data = ops.list_items(with_links=True) if kanban.enabled() else {"cards": [], "problems": []}
    cards = data["cards"]                     # each card brings its link states: the docs filter runs in the page
    uniq = lambda xs: sorted({str(x) for x in xs if x})                 # noqa: E731  (str: a hand-edited item cannot break the view)
    return {"enabled": kanban.enabled(), "writable": writable, "statuses": list(kanban.STATUSES),
            "types": list(kanban.TYPES), "priorities": list(kanban.PRIORITIES), **data,
            "epics": [c for c in cards if c["type"] == "epic"],
            "repos": uniq(r for c in cards for r in c["repos"]), "labels": uniq(l for c in cards for l in c["labels"])}


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

    def kanban_post(self, action: str, b: dict) -> None:
        from .kanban import ops
        if action not in ("init", "add", "move", "assign", "link", "archive"):
            return self.json({"error": "not found"}, 404)
        if not self.can_write():
            return self.json({"error": "writing the board needs the machine token: open the portal with `camaron up`", "token": True}, 403)
        surface = "app" if self.is_app() else "portal"
        try:                                   # every field is checked before anything is written: bad input is a 400
            by = (_text(b, "by") or "").strip() or None
            if action == "init":
                return self.json({"created": ops.init(log=lambda *_: None)})
            if action == "add":
                return self.json(ops.add(_text(b, "type", True), _text(b, "title", True), epic=_text(b, "epic") or None,
                                         repos=_text_list(b, "repos"), labels=_text_list(b, "labels"),
                                         priority=_text(b, "priority") or None, docs=_doc_refs(b), by=by, surface=surface))
            if action == "move":
                return self.json(ops.move(_text(b, "id", True), _text(b, "status", True), before=_text(b, "before"),
                                          after=_text(b, "after"), by=by, surface=surface))
            if action == "assign":
                return self.json(ops.assign(_text(b, "id", True), _text(b, "who", True), by=by, surface=surface))
            if action == "link":
                return self.json(ops.link(_text(b, "id", True), _text(b, "ref", True), by=by, surface=surface))
            return self.json(ops.archive(_text(b, "id", True), by=by, surface=surface))
        except ValueError as e:               # BoardError is a ValueError
            self.json({"error": str(e)}, 400)

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
        if name == "kitdev":
            from . import kitdev
            return self.json(kitdev.info())
        if name == "machine":
            from . import machine
            return self.json(machine.panel())
        if name == "creds":
            from . import creds
            return self.json({"backend": creds.backend_name(), "hosts": [
                {"host": h, "kind": m.get("kind", ""), "user": m.get("user", ""), "saved": bool(creds.get(h))}
                for h, m in creds.hosts().items()]})
        if name == "agents":
            from . import agents
            from .common import PREFS, load_json
            return self.json({"agents": agents.installed(), "last": load_json(PREFS, {}).get("last_agent")})
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
            if p.startswith("/api/app/"):
                if not self.is_app():
                    return self.json({"error": APP_ONLY_MSG, "app": True}, 403)
                return self.api_app_get(p[len("/api/app/"):], q)
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
        if name == "kanban":
            return self.json(kanban_state(self.can_write()))
        if name == "kanban/item":
            from .kanban import ops
            try:
                return self.json(ops.show(q.get("id", "")))
            except ops.BoardError as e:
                return self.json({"error": str(e)}, 400)
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
        if name == "interview":
            return self.json(api_interview(q.get("who", "")))
        if name == "sync":
            return self.json(env.sync_status(fetch=q.get("fetch") == "1"))
        if name == "inventory":
            return self.json(api_inventory())
        if name == "schemas":
            return self.json(api_schemas())
        if name == "ci":
            from . import ci
            return self.json(ci.status())
        if name == "kpis":
            from .harness import kpis
            return self.json(kpis.dashboard())
        if name == "c4/view":
            return self.json(api_c4_view(q.get("id", "")))
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
        try:                    # read the body first: answering before it is read resets the connection on Windows
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        except ValueError:
            raw = b""
        if STATIC:
            return self.json({"error": "read-only portal — run `camaron up` to edit"}, 405)
        if self.headers.get("X-Camarones") != "1" or self.foreign_host():
            return self.json({"error": "forbidden"}, 403)
        p = urllib.parse.urlparse(self.path).path
        if (APP_ONLY.match(p) or p.startswith("/api/app/")) and not self.is_app():
            return self.json({"error": APP_ONLY_MSG, "app": True}, 403)
        try:
            b = json.loads(raw or b"{}")
            by = (b.get("by") or reviewer()).strip()
            if p == "/api/app/cmd":
                from . import appapi
                try:
                    return self.json(appapi.start(b, start_job))
                except PermissionError as e:
                    return self.json({"error": str(e), "confirm": True}, 409)
                except KeyError as e:
                    return self.json({"error": f"unknown command {e}"}, 404)
            if p == "/api/app/kitdev":                  # the bench of a kit checkout: sandbox, pytest, npm, node --test
                return self.json(*app_kitdev(b))
            if p.startswith("/api/app/creds"):           # tokens only ever travel in this body, never on a command line
                return self.json(*app_creds(p[len("/api/app/creds"):], b))
            if p == "/api/app/agent":
                from . import agents
                agent, lang = str(b.get("agent", "")), b.get("lang") or "es"
                if b.get("unit") == "update":
                    return self.json(agents.launch_update(agent, lang))
                return self.json(agents.launch_unit(str(b.get("unit", "")), agent, lang, b.get("mode") or "new"))
            if m := re.fullmatch(r"/api/app/jobs/([\w.-]+)/cancel", p):
                from . import appapi
                return self.json(appapi.cancel(m.group(1)))
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
            if p == "/api/sync/share":             # the team action: checkpoint, pull the team's work, push
                return self.json({"result": env.share(log=lambda _: None), "sync": env.sync_status()})
            if p == "/api/interview/answer":
                from . import questionnaire
                questionnaire.answer(b)
                return self.json(questionnaire.status())
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
            if p == "/api/schemas":
                return self.json(schemas_write())
            if p == "/api/inventory":
                return self.json(inventory_job(b))
            if p == "/api/ci":
                from . import ci
                if b.get("forge") not in ("github", "gitlab"):
                    raise ValueError("forge: github or gitlab")
                env.install_ci(b["forge"], log=lambda _: None)
                return self.json(ci.status(b["forge"]))
            if p == "/api/kpis/miss":
                try:
                    return self.json(kpis_miss(b))
                except KeyError as e:
                    return self.json({"error": f"not in the list: {e}"}, 404)
            if m := re.fullmatch(r"/api/c4/(element|confirm|relation)", p):
                try:
                    return self.json(c4_change(m.group(1), b, by))
                except KeyError as e:
                    return self.json({"error": f"not in the model: {e}"}, 404)
            if p == "/api/ask/answer":
                from . import answers
                return self.json(answers.answer(str(b.get("q", ""))))
            if p.startswith("/api/kanban/"):
                return self.kanban_post(p[len("/api/kanban/"):], b)
            if p == "/api/units/approve":
                return self.json(*approve_unit(b.get("unit", "")))
            self.json({"error": "not found"}, 404)
        except (KeyError, ValueError, RuntimeError) as e:
            self.json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            self.json({"error": f"{type(e).__name__}: {e}"}, 500)


def run_server(port: int = 8080, static: bool = False) -> None:
    global STATIC, APP_TOKEN, PORTAL_TOKEN
    STATIC = static
    APP_TOKEN = os.environ.get("CAMARONES_APP_TOKEN", "")
    PORTAL_TOKEN = os.environ.get("CAMARONES_PORTAL_TOKEN", "")
    if static and not (SITE / "index.html").exists():
        raise RuntimeError("the portal is not exported yet — run `camaron portal` first")
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if APP_TOKEN:                            # the app reads the port (0 = any free one) from this first line
        print(json.dumps({"ready": True, "port": httpd.server_address[1]}), flush=True)
        sys.stdout.flush()
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
