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


def index() -> dict[str, str]:
    """x-id -> logical path, built from frontmatter on each call (decisions also answer to DEC-nnnn from their name)."""
    found: dict[str, str] = {}
    for logical, f in docs.iter_docs():
        fm = docs.parse_fm(f.read_bytes().decode("utf-8"))[0]
        if fm.get("x-id"):
            found.setdefault(str(fm["x-id"]), logical)
        dec = _decision(logical)
        if dec:
            found.setdefault(dec, logical)
    return found


def _new_id(logical: str, taken) -> str:
    dec = _decision(logical)
    if dec:
        return dec
    prefix = PREFIXES.get(logical.split("/", 1)[0], "DOC")
    while True:
        new = f"{prefix}-" + "".join(secrets.choice(ALPHABET) for _ in range(4))
        if new not in taken:
            return new


def ensure_xid(logical: str) -> str:
    """The page's x-id; written as the last frontmatter line if it has none (a page without frontmatter gets one)."""
    f = _pages().get(logical)
    if f is None:
        raise BoardError(f"no page {logical} in the docs")
    text = f.read_bytes().decode("utf-8")
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
    f.write_bytes(text.encode("utf-8"))
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
    return docs.parse_fm(f.read_bytes().decode("utf-8"))[1]


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


def page_rows() -> dict[str, dict]:
    """Trust and freshness of every page, by logical path (what link_state reads)."""
    return {r["path"]: r for r in docs.collect()}


def link_state(link: str, rows: dict[str, dict] | None = None, ids: dict[str, str] | None = None) -> dict:
    """Where a stored link points and how far to trust it. `rows`/`ids` let a caller with many links build them once."""
    p = parse_link(link)
    ids = index() if ids is None else ids
    path = ids.get(p["xid"])
    out = {"link": link, "xid": p["xid"], "path": path, "title": None, "trust": None, "fresh": None,
           "changed": False, "missing": path is None}
    if path is None:
        return out
    row = (page_rows() if rows is None else rows).get(path) or {}
    out.update(title=row.get("title"), trust=row.get("trust"), fresh=row.get("fresh"))
    if p["hash"]:
        try:
            out["changed"] = section_hash(path, p["section"]) != p["hash"]
        except BoardError:                                   # the section is gone: that is a change too
            out["changed"] = True
    return out
