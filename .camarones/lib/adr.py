"""An ADR's working state and the actions that need no model (`docs/.work/adr/<NNNN>.yaml`, spec §3.2).

Owns the numbers (reserved when a decision is framed, taken again when its file is written if a pull took them
meanwhile), the working state of each ADR, the list the app shows, and the review actions that change the proposed file:
editing a part, adding, choosing, deferring or removing a decision point, and the attendees. Every action holds one lock
for its whole read-check-write, and a save whose `base_sha` is not the file's current body (a pull, an editor) is an
`AdrConflict` that carries that sha. An edit replaces one section and keeps every other byte of the file.
Never rewrites an ADR the kit did not write: a file with no state (a legacy ADR) is listed and read as it is, and
`start_review` only creates its state. Never calls a model."""
from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import threading
from pathlib import Path

import yaml

from . import adr_doc, docs
from .common import CACHE, CAM_DIR, DOCS, WORK, retry_busy
from .harness.locks import FileLock

KINDS = ("new", "retro")
PHASES = ("problem", "evidence", "review", "accepted", "rejected")
CHIPS = ("running", "review", "proposed", "accepted", "superseded", "rejected", "deprecated", "unknown")
PART_ACTIONS = {"approve": "approved", "edit": "edited", "defer": "deferred"}
POINT_OPS = ("add", "choose", "defer", "remove")
TEXT_PARTS = ("context", "drivers", "options", "decision", "diagram", "consequences", "confirmation")

LOCK = CACHE / "locks" / "adr.lock"
_ID = re.compile(r"[0-9]{4}")
_ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_POINTS_RE = re.compile("^" + re.escape(adr_doc.POINTS_HEADING) + r"[ \t]*$", re.M)


class AdrError(ValueError):
    """What the person asked for cannot be done (400); the message is for them."""


class AdrConflict(AdrError):
    """The file is not the one the person started from (409). `sha` is the body it has now."""

    def __init__(self, message: str, sha: str):
        self.sha = sha
        super().__init__(message)


# ---------- files and state ----------
def _id(id) -> str:
    if not isinstance(id, str) or not _ID.fullmatch(id):
        raise KeyError(id)
    return id


def state_file(id: str) -> Path:
    return WORK / "adr" / f"{_id(id)}.yaml"


def _write(path: Path, text: str) -> None:
    """Whole or not at all, bytes as given: a reader sees the old file or the new one, and a CRLF file keeps its CRLF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    dst = path.resolve()
    tmp = dst.with_name(f".{dst.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_bytes(text.encode("utf-8"))
        if dst.exists():
            shutil.copymode(dst, tmp)
        retry_busy(lambda: os.replace(tmp, dst))
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _read(path: Path) -> str:
    return retry_busy(path.read_bytes).decode("utf-8", errors="replace")


def load_state(id: str) -> dict | None:
    path = state_file(id)
    try:
        text = retry_busy(lambda: path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    try:
        state = yaml.safe_load(text)
    except yaml.YAMLError:
        state = None
    if not isinstance(state, dict):
        raise AdrError(f"{path.name} is not a readable working state: fix it or remove it")
    state["id"] = id                                        # the file name is the identity, whatever the field says
    return state


def save_state(st: dict) -> None:
    path = state_file(st["id"])
    with FileLock(LOCK):
        _write(path, yaml.safe_dump(st, sort_keys=False, allow_unicode=True))


def _files() -> dict[str, Path]:
    folder = DOCS / "decisions"
    found: dict[str, Path] = {}
    for f in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        number = adr_doc.number_of(f.name)
        if number and number not in found:
            found[number] = f
    return found


def _state_ids() -> list[str]:
    folder = WORK / "adr"
    return sorted(f.stem for f in folder.glob("*.yaml") if _ID.fullmatch(f.stem)) if folder.is_dir() else []


def next_id() -> str:
    return adr_doc.next_number({*_files(), *_state_ids()})


# ---------- reading ----------
def chip(state: dict | None, status: str) -> str:
    phase = (state or {}).get("phase")
    if phase in ("problem", "evidence"):
        return "running"
    if phase == "review":
        return "review"
    return status if status in CHIPS else "unknown"


def _title(id: str, fm: dict, body: str) -> str:
    heading = docs.first_heading(body) or str(fm.get("title") or "")
    bare = re.sub(rf"^\s*(?:ADR[\s_-]*)?0*{int(id)}\b[\s.:—–-]*", "", heading, flags=re.I).strip()
    return bare or heading or id


def _split(ref: str) -> tuple[str, str] | None:
    """(repo, path) of a `repo:path` or `repo://repo/path` reference; None for a URL or a bare path."""
    if ref.startswith("repo://"):
        ref = ref[len("repo://"):].replace("/", ":", 1)
    repo, sep, path = ref.partition(":")
    return (repo, path) if sep and path and re.fullmatch(r"[\w.-]+", repo) and not path.startswith("//") else None


def _refs(sources) -> list[str]:
    return [str(s).split("#", 1)[0].strip() for s in sources if isinstance(s, str)]


def _repos(refs) -> list[str]:
    parts = (_split(ref) for ref in _refs(refs))
    return sorted({repo for repo, _ in filter(None, parts) if repo != CAM_DIR})


def _touches_of(sources) -> list[str]:
    """What an ADR written elsewhere cites, named as the board does: `repo:path`, `docs/<p>` as `cam-docs:docs/<p>`."""
    found = set()
    for ref in _refs(sources):
        parts = _split(ref)
        if parts:
            found.add(f"{parts[0]}:{parts[1]}")
        elif ref.startswith("docs/"):
            found.add(f"{CAM_DIR}:{ref}")
    return sorted(found)


def _sources(fm: dict) -> list:
    return fm.get("x-sources") if isinstance(fm.get("x-sources"), list) else []


def _decided(point: dict) -> bool:
    return not point.get("deferred") and bool(point.get("chosen") or point.get("other"))


def _decided_on(state: dict | None, status: str, body: str) -> str:
    decided = (state or {}).get("decided")
    date = str(decided.get("date") or "") if isinstance(decided, dict) else ""
    if date or status not in ("accepted", "rejected"):
        return date
    line = next((l for l in (adr_doc.section(body, "status") or "").splitlines() if l.strip()), "")
    found = _ISO.search(docs.COMMENT_RE.sub("", line))
    return found[0] if found else ""


def _stamp(*paths: Path | None) -> str:
    times = []
    for p in filter(None, paths):
        try:
            times.append(p.stat().st_mtime)
        except OSError:
            pass
    return dt.datetime.fromtimestamp(max(times), dt.timezone.utc).replace(microsecond=0).isoformat() if times else ""


def _row(id: str, path: Path | None, state: dict | None, text: str) -> dict:
    fm, body = docs.split_fm(text)
    status = adr_doc.status_of(body)[0] if path else "proposed"
    points = (state or {}).get("points") or []
    return {"id": id, "slug": path.stem[5:] if path else (state or {}).get("slug", ""),
            "title": _title(id, fm, body) if path else (state or {}).get("title", ""),
            "kind": (state or {}).get("kind") or "retro", "status": status, "chip": chip(state, status),
            "repos": _repos([*((state or {}).get("touches") or []), *_sources(fm)]),
            "points": {"total": len(points), "decided": sum(1 for p in points if _decided(p))},
            "path": f"decisions/{path.name}" if path else "", "updated": _stamp(path, state_file(id) if state else None),
            "decided": _decided_on(state, status, body), "legacy": path is not None and state is None}


def list_adrs() -> list[dict]:
    files, rows = _files(), []
    for id in sorted({*files, *_state_ids()}, reverse=True):
        try:
            state = load_state(id)
        except AdrError:                                    # one damaged state never hides the others
            state = None
        path = files.get(id)
        if path or state:
            rows.append(_row(id, path, state, _read(path) if path else ""))
    return rows


def parts_of(state: dict, sections: dict) -> list[str]:
    points = [f"point:{p['id']}" for p in state.get("points") or []]
    return ["context", "drivers", *points, "options", *(["diagram"] if sections.get("diagram") else []),
            "consequences", "confirmation", "affected"]


def get(id: str) -> dict:
    id = _id(id)
    path, state = _files().get(id), load_state(id)
    if path is None and state is None:
        raise KeyError(id)
    text = _read(path) if path else ""
    body = docs.split_fm(text)[1]
    sections = {key: adr_doc.section(body, key) or "" for key in adr_doc.KEYS}
    parts = (state or {}).get("parts") or {}
    return {**_row(id, path, state, text), "state": state, "sections": sections,
            "parts": [{"id": p, "status": parts.get(p) or "pending"} for p in parts_of(state, sections)] if state else [],
            "points": list((state or {}).get("points") or []), "affected": [],
            "sha": docs.body_sha(body) if path else "", "raw": text, "notice": None}


# ---------- framing ----------
def _texts(source: dict, key: str) -> list[str]:
    value = source.get(key)
    if value is None:
        return []
    if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) for v in value):
        raise AdrError(f"{key} must be a list of text")
    return list(dict.fromkeys(t for t in (v.strip() for v in value) if t))


def _framing(fields) -> dict:
    if not isinstance(fields, dict):
        raise AdrError("the decision needs a title and a kind")
    title = " ".join(str(fields.get("title") or "").split())
    if not title:
        raise AdrError("a decision needs a title")
    if fields.get("kind") not in KINDS:
        raise AdrError(f"kind must be one of {', '.join(KINDS)}")
    problem = fields.get("problem")
    if problem is not None and not isinstance(problem, str):
        raise AdrError("problem must be text")
    supersedes = str(fields.get("supersedes") or "").strip()
    if supersedes and not re.fullmatch(r"[0-9]{1,4}", supersedes):
        raise AdrError("supersedes must be the number of an ADR")
    return {"title": title, "kind": fields["kind"], "problem": (problem or "").strip(),
            **{key: _texts(fields, key) for key in ("drivers", "constraints", "options_hint", "touches")},
            "supersedes": f"{int(supersedes):04d}" if supersedes else None}


def new(fields: dict) -> dict:
    f = _framing(fields)
    with FileLock(LOCK):
        id = next_id()
        save_state({"id": id, "slug": adr_doc.slugify(f["title"]), "kind": f["kind"], "mode": "manual",
                    "title": f["title"], "problem": f["problem"], "drivers": f["drivers"],
                    "constraints": f["constraints"], "options_hint": f["options_hint"], "touches": f["touches"],
                    "phase": "problem", "parts": {}, "points": [], "attendees": [], "supersedes": f["supersedes"],
                    "implementation": "pending" if f["kind"] == "new" else "n/a"})
    return get(id)


# ---------- the Decision section: prose, then the decision points ----------
def _decision(prose: str, points: list[dict]) -> str:
    block = f"{adr_doc.POINTS_HEADING}\n\n{adr_doc.render_points(points)}" if points else ""
    return "\n\n".join(part for part in (prose.strip(), block) if part)


def _prose(raw: str) -> str:
    section = adr_doc.section(docs.split_fm(raw)[1], "decision") or ""
    found = _POINTS_RE.search(section)
    return (section[:found.start()] if found else section).strip()


def _with_points(raw: str, points: list[dict]) -> str:
    return adr_doc.replace_section(raw, "decision", _decision(_prose(raw), points))


# ---------- writing the proposed file ----------
def _move_cache(old: str, new_id: str) -> None:
    src, dst = CACHE / "adr" / old, CACHE / "adr" / new_id
    try:
        if src.is_dir() and not dst.exists():
            retry_busy(lambda: os.replace(src, dst))
    except OSError:                                         # the cache is disposable: the pack is rebuilt on demand
        pass


def write_without_ai(id: str) -> dict:
    id = _id(id)
    with FileLock(LOCK):
        state, files = load_state(id), _files()
        if state is None:
            if id in files:
                raise AdrError(f"{id} was not created here: review it instead of writing it")
            raise KeyError(id)
        if state.get("phase") in ("accepted", "rejected") or (state.get("phase") == "review" and id in files):
            return get(id)
        number = adr_doc.next_number({*files, *_state_ids()}) if id in files else id
        raw = adr_doc.render_new({k: state.get(k) for k in ("title", "problem", "drivers", "constraints", "options_hint",
                                                            "touches")}, number)
        if state.get("points"):
            raw = _with_points(raw, state["points"])
        _write(DOCS / "decisions" / f"{number}-{state.get('slug') or adr_doc.slugify(state.get('title') or '')}.md", raw)
        save_state({**state, "id": number, "phase": "review"})
        if number != id:
            retry_busy(lambda: state_file(id).unlink(missing_ok=True))
            _move_cache(id, number)
    out = get(number)
    if number != id:
        out["notice"] = {"renumbered": {"from": id, "to": number}}
    return out


def start_review(id: str) -> dict:
    id = _id(id)
    with FileLock(LOCK):
        if load_state(id) is None:
            path = _files().get(id)
            if path is None:
                raise KeyError(id)
            fm, body = docs.split_fm(_read(path))
            save_state({"id": id, "slug": path.stem[5:], "kind": "retro", "mode": "manual", "title": _title(id, fm, body),
                        "problem": "", "drivers": [], "constraints": [], "options_hint": [],
                        "touches": _touches_of(_sources(fm)),
                        "phase": "review", "parts": {}, "points": [], "attendees": [], "supersedes": None,
                        "implementation": "n/a"})
    return get(id)


# ---------- review actions ----------
def _unwritten(id: str) -> AdrError:
    return AdrError(f"write the ADR first: camaron adr write {id}")


def _need_state(id: str) -> dict:
    state = load_state(_id(id))
    if state is None:
        if id not in _files():
            raise KeyError(id)
        raise AdrError(f"{id} was not created here: start its review first")
    return state


def _open(id: str, base_sha: str) -> tuple[dict, Path, str]:
    """The state, the file and its text of an ADR a review action may change; call it holding the lock. The file must
    be ours and still in review, and the person must have seen it as it is now."""
    state, path = _need_state(id), _files().get(id)
    if path is None or state.get("phase") in ("problem", "evidence"):
        raise _unwritten(id)
    if state.get("phase") != "review":
        raise AdrError(f"{id} is already {state.get('phase')}: it can no longer be edited")
    raw = _read(path)
    sha = docs.body_sha(docs.split_fm(raw)[1])
    if base_sha != sha:
        raise AdrConflict(f"{id} changed while you were editing it: reload it", sha)
    if "�" in raw:
        raise AdrError(f"{path.name} is not UTF-8: convert it before editing")
    return state, path, raw


def part(id: str, part: str, action: str, text: str | None, base_sha: str) -> dict:
    if action not in PART_ACTIONS:
        raise AdrError(f"unknown action {action}: use {', '.join(PART_ACTIONS)}")
    with FileLock(LOCK):
        state, path, raw = _open(id, base_sha)
        if part not in TEXT_PARTS:
            if part == "affected" or part in {f"point:{p['id']}" for p in state.get("points") or []}:
                if action == "edit":
                    raise AdrError("the affected pages are computed" if part == "affected"
                                   else "edit a decision point with the point action")
            else:
                raise AdrError(f"unknown part {part}")
        if action == "edit":
            if not isinstance(text, str):
                raise AdrError("edit needs the new text")
            _write(path, adr_doc.replace_section(raw, "decision", _decision(text, state.get("points") or []))
                   if part == "decision" else adr_doc.replace_section(raw, part, text))
        save_state({**state, "parts": {**(state.get("parts") or {}), part: PART_ACTIONS[action]}})
    return get(id)


def _option_id(i: int) -> str:
    return chr(ord("A") + i) if i < 26 else str(i + 1)


def _new_point(points: list[dict], data: dict) -> dict:
    question = " ".join(str(data.get("question") or "").split())
    if not question:
        raise AdrError("a decision point needs a question")
    given = data.get("options")
    if not isinstance(given, list):
        raise AdrError("options must be a list")
    options = [o for o in given if isinstance(o, dict) and " ".join(str(o.get("name") or "").split())]
    if len(options) < 2:
        raise AdrError("a decision point needs at least two options")
    taken = [int(m[1]) for p in points if (m := re.fullmatch(r"p([0-9]+)", str(p.get("id"))))]
    return {"id": f"p{max(taken, default=0) + 1}", "question": question,
            "options": [{"id": _option_id(i), "name": " ".join(str(o["name"]).split()), "pros": _texts(o, "pros"),
                         "cons": _texts(o, "cons")} for i, o in enumerate(options)],
            "chosen": None, "other": None, "rationale": "", "deferred": False}


def _find_point(points: list[dict], data: dict) -> dict:
    wanted = str(data.get("point") or "").strip().lower()
    found = next((p for p in points if str(p["id"]).lower() == wanted), None)
    if found is None:
        raise AdrError(f"no decision point {wanted or '(none given)'}")
    return found


def _choose(point: dict, data: dict) -> None:
    chosen = str(data.get("chosen") or "").strip()
    other = " ".join(str(data.get("other") or "").split())
    if bool(chosen) == bool(other):
        raise AdrError("choose one option, or write another one")
    if chosen:
        option = next((o for o in point["options"] if str(o["id"]).lower() == chosen.lower()), None)
        if option is None:
            raise AdrError(f"{str(point['id']).upper()} has no option {chosen}")
        point["chosen"], point["other"] = option["id"], None
    else:
        point["chosen"], point["other"] = None, other
    point["rationale"] = " ".join(str(data.get("rationale") or "").split())
    point["deferred"] = False


def point(id: str, op: str, data: dict, base_sha: str) -> dict:
    if op not in POINT_OPS:
        raise AdrError(f"unknown op {op}: use {', '.join(POINT_OPS)}")
    if not isinstance(data, dict):
        raise AdrError("the decision point needs its data as an object")
    with FileLock(LOCK):
        state, path, raw = _open(id, base_sha)
        points, parts = [dict(p) for p in state.get("points") or []], dict(state.get("parts") or {})
        if op == "add":
            points.append(_new_point(points, data))
        else:
            target = _find_point(points, data)
            key = f"point:{target['id']}"
            if op == "remove":
                points.remove(target)
                parts.pop(key, None)
            elif op == "defer":
                target["deferred"], parts[key] = True, "deferred"
            else:
                _choose(target, data)
                parts[key] = "approved"
        _write(path, _with_points(raw, points))
        save_state({**state, "points": points, "parts": parts})
    return get(id)


def set_attendees(id: str, names: list[str]) -> dict:
    if not isinstance(names, (list, tuple)) or not all(isinstance(n, str) for n in names):
        raise AdrError("attendees must be a list of text")
    with FileLock(LOCK):
        state = _need_state(id)
        save_state({**state, "attendees": list(dict.fromkeys(n.strip() for n in names if n.strip()))})
    return get(id)
