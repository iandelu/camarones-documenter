"""Interactive agent sessions on plan units, as the board sees them. agents.launch_unit writes one record per unit in
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

from .common import CACHE, HOME, IS_WIN
from .harness.locks import pid_alive

DIR = CACHE / "sessions"
GRACE = 30                      # seconds a launched window has to start its wrapper before it counts as never opened
TAIL = 256 * 1024               # how much of a transcript's end is read for its last steps
ARG_KEYS = ("file_path", "path", "command", "pattern", "url", "description")


def path(uid: str) -> Path:
    return DIR / ("".join(c if c.isalnum() or c in "-_." else "_" for c in uid) + ".json")


def load(uid: str) -> dict | None:
    try:
        rec = json.loads(path(uid).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {}                               # being replaced by the wrapper right now
    return rec if isinstance(rec, dict) else {}


def _save(uid: str, rec: dict) -> Path:
    f = path(uid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(rec), encoding="utf-8")
    return f


def start(uid: str, agent: str, session: str | None) -> Path:
    """A fresh record for a window about to open; the wrapper fills in its pid."""
    return _save(uid, {"unit": uid, "agent": agent, "session": session, "launched": time.time()})


def update(uid: str, **fields) -> None:
    _save(uid, {**(load(uid) or {}), **fields})


def wrap(record: Path, cmd: list[str]) -> list[str]:
    """The command the terminal runs: the agent inside session_run.py, with this interpreter (stdlib only)."""
    return [sys.executable, str(Path(__file__).with_name("session_run.py")), str(record), "--", *cmd]


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


def headless() -> set[str]:
    """Units the latest parallel run is running right now: doing, but with no window of their own. Only while a run
    holds the run lock: one killed before it logged run.finished works on nothing."""
    from .harness import runs, scheduler
    latest = runs.ids()
    if not latest or not scheduler.busy():
        return set()
    evs = runs.events(latest[0])
    if any(e["type"] == "run.finished" for e in evs):
        return set()
    return {e.get("unit") for e in evs if e["type"] == "unit.started"} - \
        {e.get("unit") for e in evs if e["type"] == "unit.finished"}


def board(u: dict, busy: set[str]) -> dict:
    """A unit's session and whether it is paused: an agent unit marked doing that no window and no run is working on."""
    s = state(u["id"]) if u.get("runner") == "agent" else None
    paused = u.get("status") == "doing" and u.get("runner") == "agent" and u["id"] not in busy and \
        not (s and s["live"])
    return {"session": s, "paused": paused}
