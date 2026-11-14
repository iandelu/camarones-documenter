"""The docs area of the API: the index, a page (read, write, create, confirm, comment), search, Ask and its AI answer,
the checks and the review requests."""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path

from lib import docs, plan, sourcelinks, usage
from lib.app import portal_views
from lib.app.portal_views import doc_file, read, status, tree
from lib.core.paths import DOCS, ROOT
from lib.core.process import out
from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import Access, route


def api_ask(question: str) -> dict:
    """Ask the docs (R34): the sections that best answer a question, each with its citation, trust and freshness.
    No model: the same retrieval as the MCP `ask`, through the same freshness gate."""
    from lib.harness import freshness
    hits = docs.search(question, 20) if question.strip() else []
    usage.record("portal:ask", channel="human", hit=bool(hits), query=question)
    rows, out = {r["path"]: r for r in docs.collect()}, []
    for h in hits:
        r = rows.get(h["path"], {})
        ok, notice = freshness.gate(h["path"], r.get("trust", "draft"), r.get("freshness"))
        f = docs.find_page(h["path"])
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
    from lib import answers
    readable = any(not s["withheld_for_agents"] for s in out)          # the AI only reads what agents may read
    return {"question": question, "sections": out, "ai": answers.runner() if readable else None}


BLOCKS_TTL = 30.0                                   # seconds: code changes show up in the badges within this long
_blocks_cache: dict[tuple, tuple[float, list[dict]]] = {}
_blocks_lock = threading.Lock()                     # the server is threaded: one prune at a time


def _compute_blocks(text: str) -> list[dict]:
    """genblocks' states as they are (a repo not on this machine already leaves the marker to speak), so the badges,
    `check` and `blocks` always agree."""
    from lib import genblocks
    return [{"kind": m["kind"], "repo": m["repo"], "id": m["id"], "state": state}
            for m, state, _ in genblocks.states(text, genblocks.Scanner())]


def _blocks(f: Path, text: str) -> list[dict]:
    """The generated blocks of a page and where each stands (the portal's badges). A badge is a bonus: it never stops
    a page from opening (on any failure the markers decide), and a scan is reused for a few seconds per page version."""
    if "<!-- generated:" not in text:
        return []
    try:
        key = (str(f), f.stat().st_mtime_ns if f.exists() else 0, len(text))
        hit = _blocks_cache.get(key)
        if hit and time.monotonic() - hit[0] < BLOCKS_TTL:
            return hit[1]
        got = _compute_blocks(text)
    except Exception:
        return []
    try:
        with _blocks_lock:
            now = time.monotonic()
            for k, (at, _) in list(_blocks_cache.items()):
                if now - at >= BLOCKS_TTL:
                    _blocks_cache.pop(k, None)
            _blocks_cache[key] = (now, got)
    except Exception:
        pass                                        # a cache that could not be tidied still serves this page
    return got


def api_doc(q: dict) -> dict:
    """A page the reader opened (`track`), not the extra reads the UI does for fallbacks and the home page."""
    d = read(q["path"], q.get("lang", ""))
    d["blocks"] = _blocks(doc_file(q["path"], q.get("lang", "")), d["raw"])
    sourcelinks.with_files(d["sourceInfo"])        # this machine's portal: the reader's editor opens the file
    d["decisions"] = portal_views.covering(q["path"])   # the accepted ADRs that cover this page
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


@route("GET", "/api/tree")
def get_tree(req: Request) -> Response:
    return json_response(tree())


@route("GET", "/api/doc")
def get_doc(req: Request) -> Response:
    return json_response(api_doc(req.query))


@route("POST", "/api/doc")
def post_doc(req: Request) -> Response:
    b = req.body
    return json_response(write(b["path"], b["raw"], b.get("lang", "")))


@route("POST", "/api/new")
def post_new(req: Request) -> Response:
    return json_response(create(req.body["path"], req.body["title"]))


@route("POST", "/api/confirm")
def post_confirm(req: Request) -> Response:
    b = req.body
    docs.confirm([str(doc_file(b["path"], b.get("lang", "")))], req.by)
    return json_response(read(b["path"], b.get("lang", "")))


@route("POST", "/api/feedback")
def post_feedback(req: Request) -> Response:
    from lib import review
    b = req.body
    review.comment(b["path"], b["text"], req.by, b.get("slug", ""), b.get("snippet", ""))
    plan.ensure("review-fixes", "review-fixes")
    return json_response(read(b["path"]))


@route("GET", "/api/search")
def get_search(req: Request) -> Response:
    return json_response(api_search(req.query))


@route("GET", "/api/check")
def get_check(req: Request) -> Response:
    return json_response(dict(zip(("errors", "warnings"), docs.check())))


@route("GET", "/api/status")
def get_status(req: Request) -> Response:
    return json_response(status(check=req.query.get("check") != "0"))


@route("GET", "/api/ask")
def get_ask(req: Request) -> Response:
    return json_response(api_ask(req.query.get("q", "")))


@route("POST", "/api/ask/answer", access=Access.APP)
def post_ask_answer(req: Request) -> Response:
    from lib import answers
    return json_response(answers.answer(str(req.body.get("q", ""))))


@route("GET", "/api/reviews")
def get_reviews(req: Request) -> Response:
    from lib import review
    return json_response(review.open_requests())


@route("POST", "/api/review/decide")
def post_review_decide(req: Request) -> Response:
    from lib import review
    b = req.body
    return json_response(review.decide(b["id"], b["decision"], req.by, b.get("comments", "")))


@route("POST", "/api/commit")
def post_commit(req: Request) -> Response:
    docs.llms()
    ok = req.services.share.checkpoint_commit(req.body.get("message") or "docs edited in the portal")
    return json_response({"committed": ok, "head": out(["git", "log", "-1", "--format=%h %s"], cwd=ROOT)})
