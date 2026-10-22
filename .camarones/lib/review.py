"""Anchored, live review (R34, X6). A comment can point at a section (its slug plus a short quote, so it is found again
after a heading is renamed). An agent can ask a person to review a page and wait for the answer: `camaron review
request <page>` then `camaron review wait <id>`, which returns the decision (approve / changes) as JSON. People answer
in the portal's Review tab."""
from __future__ import annotations

import datetime as dt
import itertools, time

from .common import WORK, load_json, save_json
from . import docs

FILE = WORK / "reviews.json"
DECISIONS = ("approve", "changes")


def _now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def _load() -> dict:
    data = load_json(FILE, {})
    return data if isinstance(data.get("requests"), dict) else {"requests": {}}


def resolve_anchor(path: str, slug: str, snippet: str = "") -> str | None:
    """The section a comment points at now: its slug if it still exists, else the section holding the quoted text."""
    f = dict(docs.iter_docs()).get(path.removeprefix("docs/"))
    if not f:
        return None
    body = docs.split_fm(f.read_text(encoding="utf-8"))[1]
    secs = docs.sections(body)
    if any(s["slug"] == slug for s in secs):
        return slug
    lines = body.splitlines()
    needle = " ".join(snippet.split())[:80]
    for s in secs:
        if needle and needle in " ".join(" ".join(lines[s["start"]:s["end"]]).split()):
            return s["slug"]
    return None


def comment(path: str, text: str, by: str, slug: str = "", snippet: str = "") -> str:
    """A review comment, anchored to a section when slug/snippet are given."""
    logical = path.removeprefix("docs/")
    row = next((r for r in docs.collect() if r["path"] == logical), None)
    if not row:
        raise KeyError(path)
    where = f" § {slug}" + (f' ("{" ".join(snippet.split())[:80]}")' if snippet else "") if slug else ""
    docs.add_feedback(row["file"], f"{text.strip()}{where}", by)
    return logical


def request(path: str, by: str = "agent", note: str = "") -> str:
    data = _load()
    rid = next(f"rv-{n}" for n in itertools.count(len(data["requests"]) + 1) if f"rv-{n}" not in data["requests"])
    data["requests"][rid] = {"path": path.removeprefix("docs/"), "by": by, "note": note, "at": _now(),
                             "decision": None}
    save_json(FILE, data)
    return rid


def decide(rid: str, decision: str, by: str, comments: str = "") -> dict:
    if decision not in DECISIONS:
        raise ValueError(f"decision is one of {', '.join(DECISIONS)}")
    data = _load()
    r = data["requests"].get(rid)
    if not r:
        raise KeyError(rid)
    r.update(decision=decision, decided_by=by, decided_at=_now(), comments=comments)
    save_json(FILE, data)
    if decision == "changes" and comments:
        comment(r["path"], comments, by)
    return {"id": rid, **r}


def open_requests() -> list[dict]:
    return [{"id": k, **v} for k, v in _load()["requests"].items() if not v.get("decision")]


def wait(rid: str, timeout: float = 3600, poll: float = 2.0) -> dict:
    """Block until a person decides; returns {id, path, decision, comments…} or {decision: None} after `timeout`."""
    end = time.monotonic() + timeout
    while True:
        r = _load()["requests"].get(rid)
        if r is None:
            raise KeyError(rid)
        if r.get("decision") or time.monotonic() >= end:
            return {"id": rid, **r}
        time.sleep(poll)
