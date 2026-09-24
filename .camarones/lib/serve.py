"""Living portal: a local server (stdlib, no Docker, no npm build) where people read the docs as they are right now,
edit them, confirm them, leave review comments and commit — the same actions as the CLI, on the same files.
Binds 127.0.0.1 only. Mutating calls need the X-Camarones header, which a cross-site page cannot send without a
CORS preflight this server never grants."""
from __future__ import annotations

import json, mimetypes, re, tarfile, tempfile, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .common import KIT, ROOT, DOCS, CACHE, VERSIONS, run, out, rel_file
from . import docs, env, plan

UI = KIT / "portal" / "live"
SITE = CACHE / "site"
VENDOR_CACHE = CACHE / "vendor-cache"
VENDOR_RE = re.compile(r"^/vendor/((?:@[\w.-]+/)?[\w.-]+)@([\w.+-]+)/([\w./+-]+)$")


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
            "site": (SITE / "index.html").exists(), "codeGraph": (CACHE / "graph" / "graph.html").exists(),
            "docs": [{k: r[k] for k in ("path", "file", "title", "type", "trust", "owner", "i18n", "orphan_sources")}
                     for r in rows]}


def read(path: str, lang: str = "") -> dict:
    f = doc_file(path, lang)
    raw = f.read_text(encoding="utf-8") if f.exists() else ""
    fm, body = docs.split_fm(raw)
    row = next((r for r in docs.collect() if r["path"] == path), {})
    return {"path": path, "lang": lang, "file": rel_file(f), "raw": raw, "body": body, "exists": f.exists(),
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


def vendor_file(pkg: str, ver: str, path: str) -> Path | None:
    """Browser libraries (markdown, diagrams) fetched once through npm — an internal npm mirror works on-prem."""
    pkg_dir = VENDOR_CACHE / f"{pkg}@{ver}".replace("/", "__")
    if not pkg_dir.exists():
        VENDOR_CACHE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            r = run(["npm", "pack", f"{pkg}@{ver}", "--silent", "--pack-destination", tmp], check=False, capture=True)
            tgz = next(Path(tmp).glob("*.tgz"), None)
            if r.returncode != 0 or not tgz:
                return None
            with tarfile.open(tgz) as t:
                try:
                    t.extractall(pkg_dir, filter="data")
                except TypeError:
                    t.extractall(pkg_dir)
    f = (pkg_dir / "package" / path).resolve()
    return f if f.is_file() and pkg_dir.resolve() in f.parents else None


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

    def file(self, f: Path) -> None:
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self.send(200, f.read_bytes(), ctype)

    def static(self, base: Path, rel: str) -> bool:
        """Serve base/rel like a static host: dir → index.html, SPA fallback for the C4 app's client routes."""
        base = base.resolve()
        f = (base / rel.lstrip("/")).resolve()
        if base != f and base not in f.parents:
            return False
        for cand in (f, f / "index.html", f.with_suffix(".html")):
            if cand.is_file():
                self.file(cand)
                return True
        if rel.startswith("architecture/") and (base / "architecture" / "index.html").is_file():
            self.file(base / "architecture" / "index.html")
            return True
        return False

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        p = urllib.parse.unquote(u.path)
        try:
            if p == "/api/tree":
                return self.json(tree())
            if p == "/api/doc":
                return self.json(read(q["path"], q.get("lang", "")))
            if p == "/api/status":
                return self.json(status())
            if p.startswith("/raw/"):                 # images and diagrams referenced by the docs
                return self.static(DOCS, p[len("/raw/"):]) or self.send(404, b"not found", "text/plain")
            if m := VENDOR_RE.match(p):
                f = vendor_file(*m.groups())
                if f:
                    return self.file(f)
                return self.send(302, b"", "text/plain", {"Location": f"https://cdn.jsdelivr.net/npm/{m.group(1)}@"
                                                                      f"{m.group(2)}/{m.group(3)}"})
            if p in ("/code-graph", "/code-graph/") and (CACHE / "graph" / "graph.html").is_file():
                return self.file(CACHE / "graph" / "graph.html")
            if p.startswith("/site/") and self.static(SITE, p[len("/site/"):]):
                return
            if p.startswith(("/architecture/", "/wiki-graph/", "/vendor/")) and self.static(SITE, p):
                return
            if p in ("/", "/index.html"):
                return self.file(UI / "index.html")
            if (UI / p.lstrip("/")).is_file() and self.static(UI, p):
                return
            if self.static(SITE, p):                      # the static build's own absolute links and /_astro assets
                return
            if not Path(p).suffix:
                return self.file(UI / "index.html")
            self.send(404, b"not found", "text/plain")
        except KeyError as e:
            self.json({"error": f"missing or unknown: {e}"}, 404)
        except Exception as e:  # noqa: BLE001
            self.json({"error": f"{type(e).__name__}: {e}"}, 500)

    def do_PUT(self):
        self.do_POST()

    def do_POST(self):
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
            self.json({"error": "not found"}, 404)
        except (KeyError, ValueError, RuntimeError) as e:
            self.json({"error": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            self.json({"error": f"{type(e).__name__}: {e}"}, 500)


def run_server(port: int = 8080) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()

