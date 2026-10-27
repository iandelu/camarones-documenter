"""The evidence pack of an ADR: what the project already knows about the files a decision touches, gathered from the
code graph, the doc pages and ADRs that cite those files, git, the C4 model, the library inventory and the open
questions. Deterministic, no model: the app shows it ("Ver paquete") and the lenses of an AI draft are given it.

Every source is read on its own and a missing or broken one (no graph, inventory, C4 model or git history) leaves its
part empty, so a fresh project gets an empty pack instead of an error."""
from __future__ import annotations

import re
from itertools import zip_longest
from pathlib import Path, PurePosixPath

from . import adr, c4edit, docs, history, inventory
from .common import DOCS, repo_dir
from .kanban import index

NEIGHBOURS, PAGES, ADRS, COMMITS, MONTHS, QUESTIONS, C4, LIBRARIES = 30, 15, 10, 40, 12, 10, 20, 30
LIMIT = 20000
CUT = "…(cut)"
CATEGORIES = ("data", "cache", "messaging", "security", "framework")
PARTS = ("touches", "neighbours", "pages", "adrs", "commits", "c4", "libraries", "questions")
_DOCS = f"{index.DOCS_REPO}:docs/"
_OPEN = re.compile(r"^\s*-\s+\[ \]\s+(.*\S)\s*$")


def _safely(read, *args) -> list:
    try:
        return read(*args)
    except Exception:
        return []


def _text(value) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def read_page(logical: str, f: Path) -> tuple[dict, str] | None:
    """(frontmatter, body) of a doc page; None when it cannot be read or is a decision (`type: decision`, or under
    `decisions/`): a decision has its own status and is never evidence about or affected by another."""
    try:
        fm, body = docs.split_fm(f.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None
    return None if fm.get("type") == "decision" or logical.startswith("decisions/") else (fm, body)


# ---------- the board index: neighbours and the pages citing the files ----------
def _connect():
    try:
        return index.connect()
    except Exception:
        return None


def _query(conn, read, touches: list[str]) -> list:
    return [] if conn is None else _safely(read, conn, touches)


def _neighbours(conn, touches: list[str]) -> list[str]:
    return sorted(index.neighbours(conn, touches))[:NEIGHBOURS]


def _citing(conn, touches: list[str]) -> list[tuple[str, Path]]:
    """(logical path, file) of the doc pages citing the touches, sorted; wiki pages are not under `docs/`."""
    files = dict(docs.iter_docs())
    found = []
    for touch in index.pages_citing(conn, touches):
        logical = touch[len(_DOCS):] if touch.startswith(_DOCS) else ""
        if logical in files:
            found.append((logical, files[logical]))
    return found


def _pages(cited: list[tuple[str, Path]]) -> list[dict]:
    found = []
    for logical, f in cited:
        read = read_page(logical, f)
        if read is None:
            continue
        fm, body = read
        found.append({"page": logical, "title": _text(fm.get("title") or docs.first_heading(body) or logical),
                      "description": _text(fm.get("description")), "trust": docs.trust_of(fm, docs.body_sha(body))})
        if len(found) == PAGES:
            break
    return found


def _adrs(cited: list[tuple[str, Path]], own: str | None) -> list[dict]:
    rows = {r["path"]: r for r in adr.list_adrs() if r["path"]}
    found = [rows[logical] for logical, _ in cited if logical in rows and rows[logical]["id"] != own]
    return [{key: row[key] for key in ("id", "title", "status", "path")} for row in found[:ADRS]]


# ---------- git, C4, inventory, open questions ----------
def _commits(touches: list[str]) -> list[dict]:
    """Per touched code repo, the commits that changed a touched file (only those files listed), in `git log` order;
    repos take turns so that a busy one does not hide the others."""
    per_repo = []
    for repo, paths in sorted(index.by_repo(touches).items()):
        if repo == index.DOCS_REPO or not (repo_dir(repo) / ".git").exists():
            continue
        found = []
        for c in history.commits(repo, MONTHS):
            files = [f for f in c["files"] if f in paths]
            if files:
                found.append({"repo": repo, "subject": c["subject"], "author": c["author"], "files": files})
        per_repo.append(found)
    return [c for turn in zip_longest(*per_repo) for c in turn if c][:COMMITS]


def _c4(touches: list[str]) -> list[dict]:
    repos = set(index.by_repo(touches))
    found = []
    for fqn, el in sorted(c4edit.index()["elements"].items()):
        repo = (el.get("metadata") or {}).get("repo")
        if repo in repos:
            found.append({"fqn": fqn, "title": el.get("title") or fqn, "technology": el.get("technology") or "",
                          "repo": repo})
    return found[:C4]


def _libraries(touches: list[str]) -> list[dict]:
    repos = set(index.by_repo(touches))
    rows = [r for r in inventory.load().get("libraries") or [] if r.get("repo") in repos and r.get("scope") == "runtime"]
    rows.sort(key=lambda r: CATEGORIES.index(r["category"]) if r.get("category") in CATEGORIES else len(CATEGORIES))
    return [{"repo": r["repo"], "name": r["name"], "version": r.get("version") or r.get("declared") or "",
             "category": r.get("category") or "", "manifest": r.get("manifest") or str(r.get("source") or "").partition(":")[2]}
            for r in rows[:LIBRARIES]]


def _questions(touches: list[str]) -> list[str]:
    """The open items of `interview/open-questions.md` that name a touched file by its name or repo-qualified path."""
    keys = set()
    for repo, paths in index.by_repo(touches).items():
        keys |= {PurePosixPath(p).name.lower() for p in paths} | {f"{repo}:{p}".lower() for p in paths}
    lines = (DOCS / "interview" / "open-questions.md").read_text(encoding="utf-8").splitlines()
    found = [m[1] for m in map(_OPEN.match, lines) if m and any(k in m[1].lower() for k in keys)]
    return found[:QUESTIONS]


# ---------- the pack ----------
def build(state: dict) -> dict:
    given = state.get("touches")
    touches = list(dict.fromkeys(t.strip() for t in given if isinstance(t, str) and t.strip())) \
        if isinstance(given, list) else []
    conn = _connect()
    try:
        neighbours, cited = _query(conn, _neighbours, touches), _query(conn, _citing, touches)
    finally:
        if conn is not None:
            conn.close()
    return {"touches": touches, "neighbours": neighbours, "pages": _safely(_pages, cited),
            "adrs": _safely(_adrs, cited, state.get("id")), "commits": _safely(_commits, touches),
            "c4": _safely(_c4, touches), "libraries": _safely(_libraries, touches),
            "questions": _safely(_questions, touches)}


def summary(pack: dict) -> dict:
    return {"files": len(pack.get("touches") or []), **{part: len(pack.get(part) or []) for part in PARTS[1:]}}


def _lines(pack: dict) -> dict[str, list[str]]:
    def commit(c: dict) -> str:
        files = c["files"]
        return f"- `{c['repo']}` {c['subject']} — {c['author']} ({', '.join(files[:5])}{f' +{len(files) - 5}' if len(files) > 5 else ''})"

    return {
        "Files": [f"- `{t}`" for t in pack["touches"]],
        "Neighbouring files": [f"- `{n}`" for n in pack["neighbours"]],
        "Doc pages": [f"- `{p['page']}` — {p['title']} ({p['trust']})" + (f": {p['description']}" if p["description"] else "")
                      for p in pack["pages"]],
        "Decisions": [f"- {a['id']} — {a['title']} ({a['status']}), `{a['path']}`" for a in pack["adrs"]],
        "Commits": [commit(c) for c in pack["commits"]],
        "C4 elements": [f"- `{e['fqn']}` — {e['title']}" + (f" ({e['technology']})" if e["technology"] else "")
                        + f", repo `{e['repo']}`" for e in pack["c4"]],
        "Libraries": [f"- `{x['repo']}` {x['name']} {x['version']}".rstrip() + (f" ({x['category']})" if x["category"] else "")
                      + (f", `{x['manifest']}`" if x["manifest"] else "") for x in pack["libraries"]],
        "Open questions": [f"- {q}" for q in pack["questions"]]}


def render(pack: dict) -> str:
    """Markdown, one `##` per non-empty part, cut at `LIMIT` characters at the end of a line."""
    parts = [f"## {title}\n\n" + "\n".join(lines) for title, lines in _lines(pack).items() if lines]
    text = "\n\n".join(parts) + "\n" if parts else ""
    if len(text) <= LIMIT:
        return text
    return text[:LIMIT].rpartition("\n")[0] + f"\n{CUT}"
