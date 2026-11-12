"""Interactive agent sessions on plan units, as the board sees them. The app and the wizard write one record per unit in
the git-ignored cache (`<cache>/sessions/<unit>.json`) and the terminal window runs the agent inside session_run.py,
which adds its pid while the agent runs and when it ended. From that: whether a unit marked doing still has its window
open (else it is paused: its notes are kept and Continue picks it up), and, for Claude Code, what the agent did last,
read from the end of its transcript (the session gets its own conversation id, so this is that unit's and no other's)."""
from __future__ import annotations

import datetime as dt
import json
import socket
import sys
import time
from pathlib import Path

from .common import CACHE, HOME, IS_WIN, retry_busy, save_json
from .harness.locks import FileLock, pid_alive

DIR = CACHE / "sessions"
GRACE = 30                      # seconds a launched window has to start its wrapper before it counts as never opened
TAIL = 256 * 1024               # how much of a transcript's end is read for its last steps
ARG_KEYS = ("file_path", "path", "command", "pattern", "url", "description")


def slug(uid: str) -> str:
    """A unit's id as a file name (`discovery:api` → `discovery_api`)."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in uid)


def path(uid: str) -> Path:
    return DIR / (slug(uid) + ".json")


def lock(uid: str) -> FileLock:
    """One writer of a unit's record at a time: the server's threads, the wizard and session_run.py (which takes the
    same file), so a read-modify-write never drops what another wrote meanwhile. The folder first: the lock knows its
    holder by the folder's resolved path, which changes once it exists (/var → /private/var on macOS)."""
    f = path(uid)
    f.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(f.with_name(f.name + ".lock"), wait=10)


def load(uid: str) -> dict | None:
    try:
        rec = json.loads(retry_busy(lambda: path(uid).read_text(encoding="utf-8")))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {}                               # damaged
    return rec if isinstance(rec, dict) else {}


def _save(uid: str, rec: dict) -> Path:
    f = path(uid)
    save_json(f, rec)
    return f


def start(uid: str, agent: str, session: str | None, since: float | None = None) -> Path:
    """A fresh record for a window about to open; the wrapper fills in its pid. A Claude conversation it replaces is
    kept in `previous`, so the plan bill still counts it.

    `since`: a run wrote to this conversation too, on the run's own bill, so this record only counts it from then to
    its `ended`. Earlier such stretches stay in `spans` by conversation, and reopening one of those is another stretch."""
    with lock(uid):
        old = load(uid) or {}
        previous = [s for s in old.get("previous") or [] if s]
        if old.get("agent") == "claude" and old.get("session") and old["session"] != session \
                and old["session"] not in previous:
            previous.append(old["session"])
        spans = dict(old.get("spans") or {})
        if old.get("session") and old.get("since") is not None:
            spans[old["session"]] = [*spans.get(old["session"], []), [old["since"], old.get("ended") or time.time()]]
        if since is None and session in spans:
            since = time.time()
        return _save(uid, {"unit": uid, "agent": agent, "session": session, "launched": time.time(),
                           **({"previous": previous} if previous else {}), **({"spans": spans} if spans else {}),
                           **({"since": since} if since is not None else {})})


def update(uid: str, **fields) -> None:
    with lock(uid):
        _save(uid, {**(load(uid) or {}), **fields})


def last_opened(agent: str) -> str | None:
    """The unit whose session with `agent` opened last here."""
    recs = [load(f.stem) for f in DIR.glob("*.json")] if DIR.is_dir() else []
    mine = [r for r in recs if r and r.get("agent") == agent]
    return max(mine, key=lambda r: float(r.get("launched") or 0)).get("unit") if mine else None


def windows(rec: dict, sid: str) -> list | None:
    """The person's stretches of conversation `sid` ([from, to] in epoch seconds, `to` None while it is open); None: it
    is all theirs, as in every record of a kit before takeovers."""
    closed = (rec.get("spans") or {}).get(sid) or []
    if sid == rec.get("session") and rec.get("since") is not None:
        return [*closed, [rec["since"], rec.get("ended")]]
    return closed or None


def bound(uid: str) -> None:
    """A run takes over a session that was all the person's: from where it ended, the conversation is on the run's bill."""
    with lock(uid):
        rec = load(uid)
        if rec and rec.get("session") and rec.get("since") is None:
            update(uid, since=0.0, ended=rec.get("ended") or time.time())


def wrap(record: Path | None, cmd: list[str]) -> list[str]:
    """The command the terminal runs: the agent inside session_run.py, with this interpreter (stdlib only). No record
    (the docs update) is `-`."""
    return [sys.executable, str(Path(__file__).with_name("session_run.py")), "-" if record is None else str(record),
            "--", *cmd]


def running(rec: dict | None) -> bool:
    """Its wrapper is alive on this machine and the agent has not exited."""
    if not rec or rec.get("ended") or not rec.get("pid"):
        return False
    return rec.get("host") in (None, socket.gethostname()) and pid_alive(int(rec["pid"]))


def live(rec: dict | None) -> bool:
    """Running, or launched a moment ago and its window still opening."""
    if running(rec):
        return True
    return bool(rec) and not rec.get("ended") and not rec.get("pid") and \
        time.time() - float(rec.get("launched") or 0) < GRACE


def taken(units: list[dict]) -> list[str]:
    """Ids of `units` with a session open right now: the person's to finish, not a run's to start."""
    return [u["id"] for u in units if live(load(u["id"]))]


def claude_dir(cwd: Path) -> Path:
    """Claude Code's saved conversations for `cwd`: its projects dir is the path with every non-alphanumeric → -.
    That name repeats the whole workspace path, so on Windows it often passes MAX_PATH: Claude Code (node) copes, and
    Python too through the extended-length form (a \\\\?\\ prefix)."""
    d = HOME / ".claude" / "projects" / "".join(c if c.isalnum() else "-" for c in str(cwd.resolve()))
    return Path("\\\\?\\" + str(d.absolute())) if IS_WIN and not str(d).startswith("\\\\") else d


def _tail(f: Path) -> list[dict]:
    try:
        with f.open("rb") as fh:
            fh.seek(max(0, f.stat().st_size - TAIL))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue                            # the first, cut line; or one being written
        if isinstance(ev, dict) and ev.get("type") in ("user", "assistant") and not ev.get("isSidechain"):
            out.append(ev)
    return out


def activity(transcript: Path) -> dict | None:
    """The agent's last steps: working (it called a tool or got an answer) or waiting (its turn ended: it is asking
    you something in the terminal), its last tool and the last thing it said."""
    evs = _tail(transcript)
    if not evs:
        return None
    tool = arg = text = None
    for ev in reversed(evs):
        content = (ev.get("message") or {}).get("content")
        if ev["type"] != "assistant" or not isinstance(content, list):
            continue
        for c in reversed(content):
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use" and tool is None:
                inp = c.get("input") or {}
                tool, arg = c.get("name"), next((str(inp[k]) for k in ARG_KEYS if inp.get(k)), "")
            elif c.get("type") == "text" and text is None and str(c.get("text", "")).strip():
                text = str(c["text"]).strip()
        if tool is not None and text is not None:
            break
    last = evs[-1]
    content = (last.get("message") or {}).get("content")
    said_only = last["type"] == "assistant" and isinstance(content, list) and \
        not any(isinstance(c, dict) and c.get("type") == "tool_use" for c in content)
    return {"state": "waiting" if said_only else "working", "tool": tool, "arg": arg,
            "text": text[:300] if text else None, "ts": last.get("timestamp")}


def _iso(ts) -> str | None:
    return dt.datetime.fromtimestamp(float(ts), dt.timezone.utc).isoformat().replace("+00:00", "Z") if ts else None


def state(uid: str, cwd: Path | None = None) -> dict | None:
    """What the board shows of a unit's session, None when it never had one from this kit."""
    rec = load(uid)
    if rec is None:
        return None
    from .common import WORKSPACE
    act = None
    if rec.get("agent") == "claude" and rec.get("session"):
        act = activity(claude_dir(cwd or WORKSPACE) / f"{rec['session']}.jsonl")
    return {"agent": rec.get("agent"), "live": live(rec), "launched": _iso(rec.get("launched")),
            "ended": _iso(rec.get("ended")), "activity": act}


def headless(busy: bool | None = None) -> set[str]:
    """Units the latest parallel run is running right now: doing, but with no window of their own. Only while a run
    holds the run lock: one killed before it logged run.finished works on nothing. `busy` is that answer when the
    caller already probed the lock (a probe holds it for an instant, so one read asks once); None probes."""
    from .harness import runs, scheduler
    latest = runs.ids(wiki=False)
    if busy is None:
        busy = scheduler.busy() is not None
    if not latest or not busy:
        return set()
    evs = runs.events(latest[0])
    if any(e["type"] == "run.finished" for e in evs):
        return set()
    last = {e.get("unit"): e["type"] for e in evs if e["type"] in ("unit.started", "unit.finished")}
    return {uid for uid, kind in last.items() if kind == "unit.started"}     # a unit can start again: handed back, a limit


def board(u: dict, busy: set[str]) -> dict:
    """A unit's session and whether it is paused: an agent unit marked doing that no window and no run is working on."""
    s = state(u["id"]) if u.get("runner") == "agent" else None
    paused = u.get("status") == "doing" and u.get("runner") == "agent" and u["id"] not in busy and \
        not (s and s["live"])
    return {"session": s, "paused": paused}
