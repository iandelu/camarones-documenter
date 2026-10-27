"""Claude Code transcripts (`~/.claude/projects/<cwd>/<session>.jsonl`) → tokens per model and active time, for the plan
bill. Claude Code writes one line per content block of a message, each with the message's usage: a message id counts
once. Subagents live in `<session>/subagents/*.jsonl` and add their tokens, not their time (they run inside the main
session's turns). Active time sums the gaps between lines, each capped at IDLE: a window left open all night adds five
minutes, not ten hours."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

IDLE = 300
KINDS = ("in", "out", "cache_read", "cache_write_5m", "cache_write_1h")


def files(path: Path) -> list[Path]:
    path = Path(path)
    subs = sorted((path.with_suffix("") / "subagents").glob("*.jsonl"))
    return ([path] if path.is_file() else []) + subs


def size(path: Path) -> int:
    total = 0
    for f in files(path):
        try:
            total += f.stat().st_size
        except OSError:
            continue
    return total


def _lines(f: Path):
    """Complete JSON lines only: a damaged one is skipped, a last one still being written is left for next time."""
    try:
        with f.open("rb") as fh:
            for raw in fh:
                if not raw.endswith(b"\n"):
                    return
                try:
                    ev = json.loads(raw.decode("utf-8", errors="replace"))
                except ValueError:
                    continue
                if isinstance(ev, dict):
                    yield ev
    except OSError:
        return


def _when(ts) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def _add(models: dict, msg: dict) -> None:
    u = msg.get("usage") or {}
    m = models.setdefault(str(msg.get("model") or "unknown"), dict.fromkeys(KINDS, 0))
    split = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else None
    hour = int((split or {}).get("ephemeral_1h_input_tokens") or 0)
    m["in"] += int(u.get("input_tokens") or 0)
    m["out"] += int(u.get("output_tokens") or 0)
    m["cache_read"] += int(u.get("cache_read_input_tokens") or 0)
    m["cache_write_1h"] += hour
    m["cache_write_5m"] += int(u.get("cache_creation_input_tokens") or 0) - hour


def read(path: Path) -> dict | None:
    path = Path(path)
    if not path.is_file():
        return None
    models: dict = {}
    seen: set = set()
    first = last = prev = None
    active = 0.0
    for f in files(path):
        main = f == path
        for ev in _lines(f):
            if main and ev.get("timestamp"):
                when = _when(ev["timestamp"])
                if when:
                    if prev and when > prev:
                        active += min((when - prev).total_seconds(), IDLE)
                    prev = when if not prev or when > prev else prev
                    first = first or ev["timestamp"]
                    last = ev["timestamp"]
            msg = ev.get("message")
            if ev.get("type") != "assistant" or not isinstance(msg, dict):
                continue
            mid = msg.get("id")
            if mid:
                if mid in seen:
                    continue
                seen.add(mid)
            _add(models, msg)
    return {"models": models, "first": first, "last": last, "active_seconds": round(active, 1), "bytes": size(path)}
