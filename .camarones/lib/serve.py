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

from .common import KIT, ROOT, DOCS, CACHE, VERSIONS, out, rel_file
from . import docs, env, plan

UI = KIT / "portal" / "live"
SITE = CACHE / "site"
UI_LIBS = (("marked", "15.0.12", "lib/marked.umd.js"), ("dompurify", "3.2.6", "dist/purify.min.js"),
           ("mermaid", "11.4.1", "dist/mermaid.min.js"))
VENDOR_RE = re.compile(r"^/vendor/((?:@[\w.-]+/)?[\w.-]+)@([\w.+-]+)/([\w./+-]+)$")
STATIC = False


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
            "editBase": "", "docs": [{k: r[k] for k in ("path", "file", "title", "type", "trust", "owner", "i18n",
                                                        "orphan_sources")} for r in rows]}


def read(path: str, lang: str = "") -> dict:
    f = doc_file(path, lang)
    raw = f.read_text(encoding="utf-8") if f.exists() else ""
    fm, body = docs.split_fm(raw)
    row = next((r for r in docs.collect() if r["path"] == path), {})
    return {"path": path, "lang": lang, "file": rel_file(f), "raw": raw, "exists": f.exists(),
            "title": fm.get("title") or docs.first_heading(body) or Path(path).stem, "trust": row.get("trust"),
            "owner": row.get("owner"), "sources": fm.get("x-sources") or [], "confirmed": fm.get("x-confirmed"),
            "feedback": [l for l in docs.pending_feedback() if f"`{row.get('file')}`" in l]}


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


def status() -> dict:
    return {"queue": [{k: r[k] for k in ("path", "title", "trust", "type")} for r in docs.review_queue()],
            "feedback": docs.pending_feedback(), "changes": docs.changes(), "check": dict(zip(("errors", "warnings"),
                                                                                          docs.check())),
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
            if p in ("/", "/index.html"):
                return self.file(UI / "index.html")
            if self.static(UI, p):
                return
            if not Path(p).suffix:
                return self.file(UI / "index.html")
            self.not_found()
        except KeyError as e:
            self.json({"error": f"missing or unknown: {e}"}, 404)
        except Exception as e:  # noqa: BLE001
            self.json({"error": f"{type(e).__name__}: {e}"}, 500)

    def api_get(self, name: str, q: dict):
        if name == "tree":
            return self.json(tree())
        if name == "doc":
            return self.json(read(q["path"], q.get("lang", "")))
        if name == "status":
            return self.json(status())
        if name == "search":
            return self.json(docs.search(q.get("q", "")))
        if name == "wikis":
            return self.json(env.wikis())
        if name == "viewers":
            return self.json(env.viewers())
        if name == "jobs":
            return self.json([{k: v for k, v in j.items() if k != "log"} for j in JOBS.values()])
        if name.startswith("jobs/") and name[5:] in JOBS:
            j = JOBS[name[5:]]
            since = int(q.get("since", 0))
            return self.json({**j, "log": j["log"][since:], "lines": len(j["log"])})
        self.json({"error": "not found"}, 404)

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
                docs.add_feedback(read(b["path"])["file"], b["text"], by)
                plan.ensure("review-fixes", "review-fixes")
                return self.json(read(b["path"]))
            if p == "/api/commit":
                docs.llms()
                ok = env.checkpoint_commit(b.get("message") or "docs edited in the portal")
                return self.json({"committed": ok, "head": out(["git", "log", "-1", "--format=%h %s"], cwd=ROOT)})
            if p == "/api/build":
                return self.json(build(b))
            if p == "/api/wiki":
                return self.json(wiki(b))
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
