"""Freshness (R23: H14 level 1, H27). When a page is written, each of its x-sources (`repo:path#Lx-Ly` or a whole
file) is fingerprinted: its lines without whitespace, blank or comment-only lines. Later the page is `fresh` (same
code, or the same code moved elsewhere in the file), `suspect` (the cited code changed), `stale` (file or lines gone)
or `unverified` (no sources). Fingerprints live in docs/.work/fresh.json (main cam-docs, never in unit worktrees).

The AI gate: with `freshness: {ai_policy: block}` (the default) agents never get suspect or stale pages, nor
unreviewed pages without sources — better no information than wrong information. People still see them."""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from pathlib import Path

from ..common import CAM_DIR, CTX, ROOT, WORK, load_json, repo_dir, save_json
from .locks import FileLock

FILE = WORK / "fresh.json"
LOCK = CTX.state_root / ".camarones" / ".cache" / "locks" / "fresh.lock"
COMMENT = re.compile(r"^(//|#|/\*|\*|<!--|-->|--\s|;)")
OUT_OF_DATE = ("suspect", "stale")


def _now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def parse(ref: str) -> tuple[str | None, str, tuple[int, int] | None]:
    ref = str(ref).strip()
    if ref.startswith("repo://"):
        ref = ref[len("repo://"):].replace("/", ":", 1)
    ref, _, anchor = ref.partition("#")
    repo, _, path = ref.partition(":") if ":" in ref else (None, "", ref)
    m = re.fullmatch(r"L(\d+)(?:-L?(\d+))?", anchor or "")
    span = (int(m.group(1)), int(m.group(2) or m.group(1))) if m else None
    return repo, path, span


def _file(repo: str | None, path: str) -> Path:
    if repo in (None, "", "umbrella", ".", CAM_DIR):
        return ROOT / path
    return repo_dir(repo) / path


def _norm(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        s = re.sub(r"\s+", " ", line.strip())
        if s and not COMMENT.match(s):
            out.append(s)
    return out


def _hash(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()[:16]


def _lines(repo, path) -> list[str] | None:
    f = _file(repo, path)
    try:
        return f.read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, ValueError):
        return None


def fingerprint(ref: str, read=None) -> dict | None:
    """The cited code as {h, n}: hash and number of meaningful lines. None when the file or the range is missing.
    `read(repo, path)` gives the file's lines some other way (another commit); default: the working tree."""
    repo, path, span = parse(ref)
    lines = (read or _lines)(repo, path)
    if lines is None or (span and span[1] > len(lines)):
        return None
    block = _norm(lines[span[0] - 1:span[1]] if span else lines)
    return {"h": _hash(block), "n": len(block)}


def check_source(ref: str, stamp: dict | None, read=None) -> str:
    """fresh | changed | missing, for one source against its fingerprint."""
    if stamp is None:
        return "missing"
    repo, path, span = parse(ref)
    lines = (read or _lines)(repo, path)
    if lines is None:
        return "missing"
    now = fingerprint(ref, read)
    if now and now["h"] == stamp["h"]:
        return "fresh"
    if span:                                    # the same code moved inside the file (lines added above it)
        norm, n = _norm(lines), stamp["n"]
        if n and any(_hash(norm[i:i + n]) == stamp["h"] for i in range(0, len(norm) - n + 1)):
            return "fresh"
        if span[1] > len(lines):
            return "missing"
    return "changed"


def _pages() -> dict:
    """logical path → (frontmatter, body sha) for every page."""
    from .. import docs
    out = {}
    for logical, f in docs.iter_docs():
        fm, body = docs.split_fm(f.read_text(encoding="utf-8"))
        out[logical] = (fm or {}, docs.body_sha(body))
    return out


def _sources(fm: dict) -> list[str]:
    return [str(s) for s in (fm.get("x-sources") or []) if s]


def _load() -> dict:
    data = load_json(FILE, {})
    return data if isinstance(data.get("pages"), dict) else {"v": 1, "pages": {}}


def _stamp(entry_for: dict, logical: str, fm: dict, sha: str, by: str | None = None) -> None:
    entry_for[logical] = {"body_sha": sha, "at": _now(), **({"by": by} if by else {}),
                          "sources": {s: fingerprint(s) for s in _sources(fm)}}


def stamp_all(pages: dict | None = None) -> int:
    """Fingerprint pages that are new, rewritten, or cite other sources since their last stamp: a page written now
    reflects the code as it is now. Pages that did not change keep their old fingerprints."""
    pages = pages if pages is not None else _pages()
    with FileLock(LOCK):
        data = _load()
        n = 0
        for logical, (fm, sha) in pages.items():
            srcs = _sources(fm)
            e = data["pages"].get(logical)
            if srcs and (not e or e.get("body_sha") != sha or set(e.get("sources", {})) != set(srcs)):
                _stamp(data["pages"], logical, fm, sha)
                n += 1
        for gone in set(data["pages"]) - set(pages):
            del data["pages"][gone]
            n += 1
        if n or not FILE.exists():
            save_json(FILE, data)
        return n


def ack(logicals: list[str], by: str) -> list[str]:
    """A person says the page still holds for the current code: take today's code as its reference."""
    pages = _pages()
    with FileLock(LOCK):
        data = _load()
        done = []
        for logical in logicals:
            logical = logical.removeprefix("docs/")
            if logical in pages:
                _stamp(data["pages"], logical, *pages[logical], by=by)
                done.append(logical)
        save_json(FILE, data)
    return done


def states() -> dict[str, dict]:
    """Every page's freshness: {state, changed, missing}. New or rewritten pages get their fingerprints first."""
    pages = _pages()
    stamp_all(pages)
    data = _load()["pages"]
    out = {}
    for logical, (fm, _) in pages.items():
        srcs = _sources(fm)
        if not srcs:
            out[logical] = {"state": "unverified", "changed": [], "missing": []}
            continue
        stamps = (data.get(logical) or {}).get("sources", {})
        results = {s: check_source(s, stamps.get(s)) for s in srcs}
        changed = [s for s, r in results.items() if r == "changed"]
        missing = [s for s, r in results.items() if r == "missing"]
        out[logical] = {"state": "stale" if missing else "suspect" if changed else "fresh", "changed": changed,
                        "missing": missing}
    return out


def status(logical: str) -> dict:
    return states().get(logical.removeprefix("docs/"), {"state": "unverified", "changed": [], "missing": []})


def policy() -> str:
    from .. import docs
    return (docs.workspace().get("freshness") or {}).get("ai_policy", "block")


def code_paths(refs: list[str]) -> list[str]:
    """Sources as paths an agent can open from the workspace: <repo>/<path>[#Lx-Ly]."""
    out = []
    for ref in refs:
        repo, path, span = parse(ref)
        out.append(f"{repo + '/' if repo else ''}{path}" + (f"#L{span[0]}-L{span[1]}" if span else ""))
    return out


def gate(logical: str, trust: str, state: dict | None = None) -> tuple[bool, str | None]:
    """Whether an agent may read this page, and the notice to show with it (or instead of it)."""
    st = state or status(logical)
    blocking = policy() == "block"
    if st["state"] in OUT_OF_DATE:
        what = st["missing"] + st["changed"]
        why = ("its code is gone" if st["state"] == "stale" else "its code changed since it was written")
        notice = (f"{'withheld' if blocking else 'may be out of date'}: {logical} — {why}. Read the code instead: "
                  + ", ".join(code_paths(what)))
        return (not blocking), notice
    if st["state"] == "unverified" and trust != "confirmed":
        notice = (f"{'withheld' if blocking else 'unreviewed'}: {logical} has no sources to check it against and "
                  "awaits review by a person.")
        return (not blocking), notice
    return True, None


def refresh_unit() -> dict:
    """An agent unit that re-documents the out-of-date pages (what changed is in its note)."""
    from .. import plan
    out = {p: s for p, s in states().items() if s["state"] in OUT_OF_DATE}
    note = "; ".join(f"{p} ({s['state']}: {', '.join(code_paths(s['missing'] + s['changed']))})" for p, s in out.items())
    u = plan.ensure("refresh-docs", "refresh-docs", title="Refresh the pages whose code changed")
    return plan.set_status(u["id"], "todo", note or "nothing out of date", record=False)
