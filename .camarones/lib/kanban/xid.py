"""Doc links by x-id (spec §5). A page gets `x-id` in its frontmatter the first time an item links it; the line is
inserted textually, so the body, the human-written frontmatter and `x-confirmed.body_sha` stay exactly as they were.
A stored link is `<x-id>[#<section-slug>][@<hash>]`; the hash is the section's (or the page's) body hash when linked."""
from __future__ import annotations

import re
import secrets

from .. import docs
from .ops import BoardError

PREFIXES = {"flows": "FLOW", "domain": "DOM", "architecture": "ARCH"}
ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"           # base32 without i, l, o, u
_DEC = re.compile(r"(?:.*/)?decisions/(\d{4})-")
_LINK = re.compile(r"^([^#@]+)(?:#([^@]*))?(?:@(\w+))?$")


def _decision(logical: str) -> str | None:
    m = _DEC.match(logical)
    return f"DEC-{m.group(1)}" if m else None


def _pages() -> dict[str, "docs.Path"]:
    return dict(docs.iter_docs())


def _read(f) -> tuple[str, str]:
    """(BOM or "", text) of a page, bytes as they are on disk (no newline translation)."""
    text = f.read_bytes().decode("utf-8")
    return ("\ufeff", text[1:]) if text.startswith("\ufeff") else ("", text)


def index() -> dict[str, str]:
    """x-id -> logical path, built from frontmatter on each call (decisions also answer to DEC-nnnn from their name)."""
    found: dict[str, str] = {}
    named: dict[str, str] = {}
    for logical, f in docs.iter_docs():
        fm = docs.parse_fm(_read(f)[1])[0]
        if fm.get("x-id"):
            found.setdefault(str(fm["x-id"]), logical)
        dec = _decision(logical)
        if dec:
            named.setdefault(dec, logical)
    for dec, logical in named.items():                      # an x-id a page carries wins over a number from a name
        found.setdefault(dec, logical)
    return found


def _folder(logical: str) -> str:
    """The first folder of the page, past a leading repos/<name>/ (a repo's wiki pages sort like the root ones)."""
    parts = logical.split("/")
    if parts[0] == "repos" and len(parts) > 2:
        parts = parts[2:]
    return parts[0]


def _new_id(logical: str, taken: dict[str, str]) -> str:
    dec = _decision(logical)
    if dec and taken.get(dec, logical) == logical:
        return dec
    prefix = "DEC" if dec else PREFIXES.get(_folder(logical), "DOC")
    while True:
        new = f"{prefix}-" + "".join(secrets.choice(ALPHABET) for _ in range(4))
        if new not in taken:
            return new


def ensure_xid(logical: str) -> str:
    """The page's x-id; written as the last frontmatter line if it has none (a page without frontmatter gets one)."""
    f = _pages().get(logical)
    if f is None:
        raise BoardError(f"no page {logical} in the docs")
    bom, text = _read(f)
    fm, _, valid = docs.parse_fm(text)
    if not valid:
        raise BoardError(f"{logical}: its frontmatter is unreadable, fix it before linking")
    if fm.get("x-id"):
        return str(fm["x-id"])
    new = _new_id(logical, index())
    m = docs.FM_RE.match(text)
    if m:
        at = m.end(1) - (1 if m.group(1).endswith("\r") else 0)
        eol = "\r\n" if m.group(1).endswith("\r") else "\n"
        text = text[:at] + f"{eol}x-id: {new}" + text[at:] if m.group(1).strip() else \
            text[:m.start(1)] + f"x-id: {new}" + text[m.end(1):]
    else:
        text = f"---\nx-id: {new}\n---\n" + text
    f.write_bytes((bom + text).encode("utf-8"))
    return new


def parse_link(s: str) -> dict:
    m = _LINK.match(str(s).strip())
    if not m:
        raise BoardError(f"not a doc link: {s!r}")
    return {"xid": m.group(1), "section": m.group(2) or None, "hash": m.group(3) or None}


def format_link(xid: str, section: str | None, hash_: str | None) -> str:
    return xid + (f"#{section}" if section else "") + (f"@{hash_}" if hash_ else "")


def _body(logical: str) -> str:
    f = _pages().get(logical)
    if f is None:
        raise BoardError(f"no page {logical} in the docs")
    return docs.parse_fm(_read(f)[1])[1]


def _section(body: str, section: str | None) -> tuple[str | None, str]:
    """(canonical slug, text) of the section, or (None, whole body)."""
    if not section:
        return None, body
    found = docs.section_text(body, section)
    if found is None:
        raise BoardError(f"no section {section!r} in that page")
    return found[0]["slug"], found[1]


def section_hash(logical: str, section: str | None) -> str:
    return docs.body_sha(_section(_body(logical), section)[1])[:8]


def resolve_ref(ref: str) -> str:
    """`FLOW-k3f9[#sec]` or `flows/payments.md[#sec]` -> the stored link with today's hash. Gives the page an x-id."""
    p = parse_link(ref)
    ids = index()
    logical = ids.get(p["xid"])
    if logical is None:
        logical = p["xid"] if p["xid"] in _pages() else None
    if logical is None:
        raise BoardError(f"unknown page {p['xid']} (use an x-id or a path like flows/payments.md)")
    slug, text = _section(_body(logical), p["section"])
    return format_link(ensure_xid(logical), slug, docs.body_sha(text)[:8])


def _fresh() -> dict[str, dict] | None:
    """Freshness of every page, but only when reading it writes nothing (all fingerprints already stamped)."""
    from ..harness import freshness
    pages = freshness._pages()
    if not freshness.FILE.exists():
        return None
    data = freshness._load()["pages"]
    if set(data) - set(pages):                               # stamp_all would drop pages that are gone
        return None
    for logical, (fm, sha) in pages.items():
        srcs = freshness._sources(fm)
        e = data.get(logical)
        if srcs and (not e or e.get("body_sha") != sha or set(e.get("sources", {})) != set(srcs)):
            return None
    return freshness.states()


def page_rows(paths=None) -> dict[str, dict]:
    """Trust, title and freshness of the given pages (default all), by logical path (what link_state reads). Read-only:
    unlike docs.collect() it writes no status file and stamps nothing; `fresh` is None when it cannot be read that way."""
    pages = _pages()
    fresh = _fresh()
    rows = {}
    for p in (pages if paths is None else paths):
        if p in pages:
            r = docs.doc_status(p, pages[p], [])
            r["fresh"] = None if fresh is None else (fresh.get(p) or {}).get("state")
            rows[p] = r
    return rows


def link_state(link: str, rows: dict[str, dict] | None = None, ids: dict[str, str] | None = None) -> dict:
    """Where a stored link points and how far to trust it. `rows`/`ids` let a caller with many links build them once."""
    try:
        p = parse_link(link)
    except BoardError:                                       # an empty or garbage entry people typed by hand
        return {"link": str(link), "xid": None, "path": None, "title": None, "trust": None, "fresh": None,
                "changed": False, "missing": True}
    ids = index() if ids is None else ids
    path = ids.get(p["xid"])
    out = {"link": link, "xid": p["xid"], "path": path, "title": None, "trust": None, "fresh": None,
           "changed": False, "missing": path is None}
    if path is None:
        return out
    row = (page_rows([path]) if rows is None else rows).get(path) or {}
    out.update(title=row.get("title"), trust=row.get("trust"), fresh=row.get("fresh"))
    if p["hash"]:
        try:
            out["changed"] = section_hash(path, p["section"]) != p["hash"]
        except BoardError:                                   # the section is gone: that is a change too
            out["changed"] = True
    return out
