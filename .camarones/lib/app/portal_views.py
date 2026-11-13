"""The docs as the portal shows them: the index, a page with its trust and sources, the review status, the decisions
that cover a page. The live server's routes and the static export (`env.export_site`) both build their JSON here."""
from __future__ import annotations

import logging
from pathlib import Path

from lib import adr, adr_doc, codemap, docs, plan, sourcelinks
from lib.app import services
from lib.common import VERSIONS
from lib.core.ctx import KIT
from lib.core.paths import DOCS, ROOT, rel_file
from lib.core.process import out

_adr_log = logging.getLogger("camaron.adr_api")

APP = KIT / "portal" / "app-build"           # the portal: React views + the docs views (portal/app), built in the kit's CI
UI = APP                                     # the old name, kept for callers
UI_LIBS = (("marked", "15.0.12", "lib/marked.umd.js"), ("dompurify", "3.2.6", "dist/purify.min.js"),
           ("mermaid", "11.4.1", "dist/mermaid.min.js"), ("@highlightjs/cdn-assets", "11.11.1", "highlight.min.js"),
           ("vis-network", "9.1.6", "standalone/umd/vis-network.min.js"))     # the code map, loaded on its tab only


def reviewer() -> str:
    return out(["git", "config", "user.name"], cwd=ROOT) or "human"


def doc_file(path: str, lang: str = "") -> Path:
    """Only pages the docs model knows about (or their translations) can be read or written through the API."""
    canon = dict(docs.iter_docs())
    path = docs.link_target(path, canon)                  # a wiki page's pre-4.81 path still names it
    if path not in canon:
        raise KeyError(f"unknown page {path}")
    if not lang:
        return canon[path]
    f = docs.translation_file(path, lang).resolve()
    if DOCS.resolve() not in f.parents:
        raise KeyError(path)
    return f


def tree() -> dict:
    rows = docs.collect()
    ws = docs.workspace()
    return {"project": ws["project"]["name"], "langs": ws["project"].get("translations", []), "reviewer": reviewer(),
            "summary": docs.summary(rows), "feedback": len(docs.pending_feedback()), "kit": VERSIONS["kit"],
            "repos": docs.repo_names(), "codeGraphs": list(services.current().viewers.code_graphs()),
            "engines": services.current().wiki.wiki_engines(), "engineHelp": services.current().wiki.wiki_engine_help(),
            "kitGuides": sorted(docs.kit_guides()),
            "sections": docs.SECTIONS, "views": services.current().diagrams.c4_views(), "codeMaps": codemap.available(), "editBase": "",
            "docs": _with_adr_status(rows)}


def _with_adr_status(rows: list[dict]) -> list[dict]:
    """The docs index rows; a decision page (`adr_doc.is_decision`) also says its ADR's status, read from the file as it
    stands."""
    keys = ("path", "file", "title", "description", "type", "space", "trust", "owner", "i18n", "orphan_sources")
    files = dict(docs.iter_docs()) if any(_is_decision(r) for r in rows) else {}
    out = []
    for r in rows:
        row = {k: r[k] for k in keys}
        if _is_decision(r) and r["path"] in files:
            try:
                row["adr_status"] = adr_doc.status_of(docs.split_fm(files[r["path"]].read_text(encoding="utf-8"))[1])[0]
            except OSError:
                pass
        out.append(row)
    return out


def _is_decision(row: dict) -> bool:
    return adr_doc.is_decision(row["path"], row["type"])


def read(path: str, lang: str = "") -> dict:
    f = doc_file(path, lang)
    raw = f.read_text(encoding="utf-8") if f.exists() else ""
    fm, body = docs.split_fm(raw)
    row = next((r for r in docs.collect() if r["path"] == path), {})
    return {"path": path, "lang": lang, "file": rel_file(f), "raw": raw, "exists": f.exists(),
            "title": fm.get("title") or docs.first_heading(body) or Path(path).stem, "trust": row.get("trust"),
            "owner": row.get("owner"), "sources": fm.get("x-sources") or [], "confirmed": fm.get("x-confirmed"),
            "fresh": row.get("fresh"), "freshness": row.get("freshness"),
            "sourceInfo": _source_info(path, fm.get("x-sources") or [], row.get("freshness")),
            "feedback": [l for l in docs.pending_feedback() if f"`{row.get('file')}`" in l]}


def _source_info(path: str, refs: list, state: dict | None) -> list[dict]:
    """The Sources card is a bonus: a repo that cannot be read never stops a page from opening."""
    try:
        return sourcelinks.describe(path, refs, state)
    except Exception:  # noqa: BLE001
        return []


def status(check: bool = True) -> dict:
    """`check=False` skips the full quality check (seconds on a big project): the page shows the rest at once."""
    return {"queue": [{k: r[k] for k in ("path", "title", "trust", "type")} for r in docs.review_queue()],
            "feedback": docs.pending_feedback(), "changes": docs.changes(),
            "check": dict(zip(("errors", "warnings"), docs.check())) if check else None,
            "plan": dict(zip(("done", "total"), plan.progress()))}


def covering(logical: str) -> list[dict]:
    try:
        return adr.covering(logical)
    except Exception as e:  # noqa: BLE001 — a page is read even when its decisions cannot be
        _adr_log.warning("decisions covering %s unavailable (%s); the page loads without them", logical, e)
        return []


def code_map(repo: str) -> dict | None:
    """A repo's code map (the portal's Code map tab); None when the repo is not one of the project's or has none."""
    return codemap.load(repo) if repo in docs.repo_names() else None
