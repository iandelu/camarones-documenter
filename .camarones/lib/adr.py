"""An ADR's working state and the actions that need no model (`docs/.work/adr/<NNNN>.yaml`, spec §3.2).

Owns the numbers (reserved when a decision is framed, taken again when its file is written if a pull took them
meanwhile), the working state of each ADR, the list the app shows, and the review actions that change the proposed file:
editing a part, adding, choosing, deferring or removing a decision point, and the attendees. Every action holds one lock
for its whole read-check-write, and a save whose `base_sha` is not the file's current body (a pull, an editor) is an
`AdrConflict` that carries that sha. An edit replaces one section and keeps every other byte of the file.
The person's decision closes the review: `accept` and `reject` set the status, hand the file to a human (`x-owner`) and
confirm it, `accept` also marking the ADR it supersedes; `covering` lists the accepted ADRs a page falls under.
`pack` gathers the evidence of a decision (`adr_pack`) into the cache and moves a framed ADR on to `evidence`.
Never rewrites an ADR the kit did not write before that decision: a file with no state (a legacy ADR) is listed and read
as it is, and `start_review` only creates its state. Never calls a model."""
from __future__ import annotations

import datetime as dt
import json
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


def _load_or_none(id: str) -> dict | None:
    try:
        return load_state(id)
    except AdrError:                                        # one damaged state never hides the others
        return None


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
        state = _load_or_none(id)
        path = files.get(id)
        if path or state:
            rows.append(_row(id, path, state, _read(path) if path else ""))
    return rows


def parts_of(state: dict, sections: dict) -> list[str]:
    points = [f"point:{p['id']}" for p in state.get("points") or []]
    return ["context", "drivers", *points, "options", *(["diagram"] if sections.get("diagram") else []),
            "consequences", "confirmation", "affected"]


def _affected(state: dict | None) -> list[str]:
    from . import adr_pack
    return adr_pack.affected((state or {}).get("touches") or [])


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
            "points": list((state or {}).get("points") or []), "affected": _affected(state),
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


# ---------- the evidence pack ----------
def pack(id: str) -> dict:
    """Gather what the project knows about the files this decision touches, keep it in the cache and move a framed ADR
    on to `evidence`. Allowed at any phase, to refresh the pack; it never moves a phase back."""
    from . import adr_pack
    state = _need_state(id)
    built = adr_pack.build(state)
    markdown = adr_pack.render(built)
    folder = CACHE / "adr" / id
    with FileLock(LOCK):
        current = _need_state(id)
        _write(folder / "pack.json", json.dumps(built, ensure_ascii=False, indent=2) + "\n")
        _write(folder / "pack.md", markdown)
        if current.get("phase") == "problem":
            save_state({**current, "phase": "evidence"})
    return {"summary": adr_pack.summary(built), "markdown": markdown}


def read_pack(id: str) -> dict | None:
    """The pack `pack` kept in the cache, None when there is none (or it cannot be read: it is rebuilt on demand)."""
    from . import adr_pack
    folder = CACHE / "adr" / _id(id)
    try:
        built = json.loads(_read(folder / "pack.json"))
        markdown = _read(folder / "pack.md")
    except (OSError, ValueError):
        return None
    return {"summary": adr_pack.summary(built), "markdown": markdown} if isinstance(built, dict) else None


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


def _names(names) -> list[str]:
    if not isinstance(names, (list, tuple)) or not all(isinstance(n, str) for n in names):
        raise AdrError("attendees must be a list of text")
    return list(dict.fromkeys(n.strip() for n in names if n.strip()))


def set_attendees(id: str, names: list[str]) -> dict:
    names = _names(names)
    with FileLock(LOCK):
        state = _need_state(id)
        save_state({**state, "attendees": names})
    return get(id)


# ---------- the decision: accept, reject, supersede ----------
def today() -> str:
    return dt.date.today().isoformat()


def _who(by) -> str:
    name = " ".join(by.split()) if isinstance(by, str) else ""
    if not name:
        raise AdrError("a decision needs the name of who takes it")
    return name


def _outcome(state: dict, raw: str) -> str | None:
    """The Decision section an accepted ADR gets, None to keep the one written. What a person wrote there stays, in front
    of one paragraph per point; the placeholder and the points subsection go. Refuses what nobody has decided."""
    points = state.get("points") or []
    for p in points:
        label = str(p.get("id")).upper()
        if p.get("deferred"):
            raise AdrError(f"point {label} is deferred: decide it or remove it")
        if not _decided(p):
            raise AdrError(f"point {label} has no choice yet")
    prose = _prose(raw)
    written = "" if prose == adr_doc.PLACEHOLDER else prose
    if not points:
        if not written:
            raise AdrError("write the Decision section or add a decision point")
        return None
    paragraphs = adr_doc.render_decision(points)
    return written if paragraphs in written else "\n\n".join(t for t in (written, paragraphs) if t)


def _supersession(state: dict, id: str, name: str) -> tuple[Path, str] | None:
    """The ADR this one replaces and its new text, worked out before anything is written."""
    old = str(state.get("supersedes") or "").strip()
    if not old:
        return None
    old = f"{int(old):04d}" if re.fullmatch(r"[0-9]{1,4}", old) else old
    if old == id:
        raise AdrError(f"{id} cannot supersede itself")
    path = _files().get(old)
    if path is None:
        raise AdrError(f"{id} supersedes {old}, but there is no ADR {old}")
    raw = _read(path)
    if "�" in raw:
        raise AdrError(f"{path.name} is not UTF-8: convert it before superseding it")
    return path, adr_doc.replace_status(raw, f"Superseded by [{id}]({name})")


def _owned(raw: str, name: str, id: str, state: dict) -> str:
    """The file with `x-owner: human` and every other key as it was. A file with no frontmatter gets the few keys a page
    needs to be confirmed; one whose frontmatter cannot be read is never rewritten."""
    fm, body, valid = docs.parse_fm(raw)
    if not valid:
        raise AdrError(f"the frontmatter of {name} cannot be read: fix it before deciding")
    fm = {**fm, "x-owner": "human"} if fm else {"type": "decision", "title": f"{id} — {state.get('title') or id}",
                                                 "x-owner": "human"}
    return docs.join_fm(fm, body)


def _seal(path: Path, text: str, who: str) -> None:
    _write(path, text)
    docs.confirm([str(path)], who)


def _closed(state: dict, phase: str, date: str, who: str, **more) -> dict:
    return {**state, "phase": phase, "decided": {"date": date, "by": who, "driver": who}, **more}


def accept(id: str, by: str, attendees: list[str] | None, base_sha: str) -> dict:
    """The person's decision: every point chosen, `Accepted (date)`, who decided, owned by a human and confirmed. The
    ADR it supersedes is marked in the same action. Attendees given replace those of the review; none keeps them."""
    who, given = _who(by), _names(attendees) if attendees is not None else []
    with FileLock(LOCK):
        state, path, raw = _open(id, base_sha)
        outcome, old = _outcome(state, raw), _supersession(state, id, path.name)
        date, names = today(), given or _names(state.get("attendees") or [])
        text = adr_doc.replace_status(raw, f"Accepted ({date})")
        if outcome is not None:
            text = adr_doc.replace_section(text, "decision", outcome)
        text = adr_doc.replace_section(text, "decided_by", adr_doc.render_decided_by(
            date, names, who, str(state.get("mode") or "manual")))
        _seal(path, _owned(text, path.name, id, state), who)
        if old:
            old_path, old_text = old
            _write(old_path, old_text)
            if docs.split_fm(old_text)[0]:                  # a file with no frontmatter cannot be confirmed, and gets none
                docs.confirm([str(old_path)], who)
        save_state(_closed(state, "accepted", date, who, attendees=names))
    return get(id)


def reject(id: str, why: str, by: str, base_sha: str) -> dict:
    reason = " ".join(why.split()) if isinstance(why, str) else ""
    if not reason:
        raise AdrError("a rejection needs a reason")
    who = _who(by)
    with FileLock(LOCK):
        state, path, raw = _open(id, base_sha)
        date = today()
        _seal(path, _owned(adr_doc.replace_status(raw, f"Rejected ({date}): {reason}"), path.name, id, state), who)
        save_state(_closed(state, "rejected", date, who))
    return get(id)


# ---------- what an accepted ADR covers ----------
def covering(logical: str) -> list[dict]:
    """The accepted ADRs a page falls under: they share a source with it (fragments and `repo://` ignored) or cite it as
    `docs/<logical>`. Read from the files, so an accepted ADR written elsewhere covers too. A decision page (`type:
    decision`, or under `decisions/`) is never covered: it has its own status."""
    page = dict(docs.iter_docs()).get(logical)
    if page is None:
        return []
    mine = docs.split_fm(_read(page))[0]
    if mine.get("type") == "decision" or logical.startswith("decisions/"):
        return []
    cited, found = set(_touches_of(_sources(mine))), []
    for id, path in sorted(_files().items()):
        fm, body = docs.split_fm(_read(path))
        theirs = set(_touches_of(_sources(fm)))
        if adr_doc.status_of(body)[0] != "accepted":
            continue
        if cited & theirs or f"{CAM_DIR}:docs/{logical}" in theirs:
            state = _load_or_none(id) or {}
            found.append({"id": id, "title": _title(id, fm, body), "path": f"decisions/{path.name}",
                          "kind": state.get("kind") or "retro", "implementation": state.get("implementation") or "n/a"})
    return found
