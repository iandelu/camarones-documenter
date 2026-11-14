"""What the server answers outside /api/: the portal's build, the docs' images, the viewers (the C4 explorer, the code
and wiki graphs, the C4 draft), the desktop app's own UI and the graph libraries for offline use. In static mode
(`up --static`) the exported site answers instead (`static_site`), except for a route declared `static=True`."""
from __future__ import annotations

import mimetypes
from pathlib import Path

from lib import docs
from lib.app.portal_views import APP
from lib.common import CACHE, DOCS, KIT
from lib.interfaces.http.messages import Request, Response, not_found, redirect
from lib.interfaces.http.router import route

DESKTOP = KIT / "desktop" / "renderer-build"  # the desktop app's own UI (desktop/renderer): its project windows load it here
SITE = CACHE / "site"
mimetypes.add_type("text/javascript", ".js")    # Windows may map .js to text/plain in the registry
mimetypes.add_type("font/woff2", ".woff2")    # the portal theme fonts; older Pythons do not know the type


def cdn_local(html: str) -> str:
    """Graph viewers pull libraries from CDNs; point them at /vendor/ (npm-fetched once) so they work offline."""
    return docs.CDN_RE.sub(lambda m: f"/vendor/{m.group(1)}@{m.group(2)}/{m.group(3)}", html)


def file_response(f: Path, local_cdn: bool = False) -> Response:
    ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
        ctype += "; charset=utf-8"
    body = f.read_bytes()
    if local_cdn and f.suffix == ".html":
        body = cdn_local(body.decode("utf-8", errors="replace")).encode()
    return Response(200, body, ctype)


def static_response(base: Path, rel: str, local_cdn: bool = False, spa: bool = False) -> Response | None:
    """Serve base/rel like a static host: dir → index.html; `spa` falls back to the app's index.html."""
    base = base.resolve()
    f = (base / rel.lstrip("/")).resolve()
    if base != f and base not in f.parents:
        return None
    for cand in (f, f / "index.html"):
        if cand.is_file():
            return file_response(cand, local_cdn)
    if spa and (base / "index.html").is_file():
        return file_response(base / "index.html", local_cdn)
    return None


def static_site(p: str) -> Response:
    """Static mode: the exported site, as a static host serves it."""
    if p.startswith("/architecture/") and (
            got := static_response(SITE / "architecture", p[len("/architecture/"):], spa=True)):
        return got
    if got := static_response(SITE, p):
        return got
    if not Path(p).suffix:
        return file_response(SITE / "index.html")
    return not_found()


@route("GET", "/firstlook", static=True)
def firstlook(req: Request) -> Response:
    """The C4 draft's interactive view (read-only, like the docs)."""
    from lib import onboard
    f = onboard.last_draft().get("html")
    return file_response(Path(f), local_cdn=True) if f and Path(f).is_file() else not_found()


@route("GET", "/raw/wikis/{rest:.*}")
def raw_wiki(req: Request) -> Response:
    """Images next to a wiki page (wikis/<repo>/<page>)."""
    repo, _, rel = req.params["rest"].partition("/")
    ok = repo in docs.repo_names() and static_response(docs.wiki_dir(repo), rel)
    return ok or not_found()


@route("GET", "/raw/{rest:.*}")
def raw(req: Request) -> Response:
    """Images and diagrams referenced by the docs."""
    return static_response(DOCS, req.params["rest"]) or not_found()


@route("GET", "/vendor/{pkg:(?:@[\\w.-]+/)?[\\w.-]+}@{ver:[\\w.+-]+}/{file:[\\w./+-]+}")
def vendor(req: Request) -> Response:
    pkg, ver, file = req.params["pkg"], req.params["ver"], req.params["file"]
    f = docs.vendor_file(pkg, ver, file)
    if f:
        return file_response(f)
    return redirect(302, f"https://cdn.jsdelivr.net/npm/{pkg}@{ver}/{file}")


@route("GET", "/architecture/{rest:.*}")
def architecture(req: Request) -> Response:
    return static_response(req.services.viewers.VIEWERS / "architecture", req.params["rest"], spa=True) or not_found()


@route("GET", "/code-graph/{repo:(?:[\\w.-]+/?)?}")
def code_graph(req: Request) -> Response:
    f = req.services.viewers.code_graphs().get(req.params["repo"].rstrip("/") or "all")
    return file_response(f, local_cdn=True) if f else not_found()


@route("GET", "/wiki-graph/{repo:[\\w.-]+}/{rest:.*}")
def wiki_graph(req: Request) -> Response:
    return static_response(req.services.viewers.VIEWERS / "wiki-graph" / req.params["repo"], req.params["rest"],
                           local_cdn=True) or not_found()


@route("GET", "/next")
@route("GET", "/next/{rest:.*}")
def next_portal(req: Request) -> Response:
    """The preview address of 3.26–4.16: one portal now."""
    return redirect(301, "/")


@route("GET", "/desktop")
def desktop(req: Request) -> Response:
    """Its assets are relative to /desktop/."""
    return redirect(301, "/desktop/")


@route("GET", "/desktop/{rest:.*}")
def desktop_file(req: Request) -> Response:
    return static_response(DESKTOP, req.params["rest"], spa=True) or not_found()


@route("GET", "/")
@route("GET", "/index.html")
def index(req: Request) -> Response:
    return file_response(APP / "index.html")


@route("GET", "/{rest:.*}")
def portal(req: Request) -> Response:
    """A file of the portal's build; any other address without a suffix is one of the portal's own pages."""
    p = req.path
    if got := static_response(APP, p):
        return got
    if not Path(p).suffix:
        return file_response(APP / "index.html")
    return not_found()
