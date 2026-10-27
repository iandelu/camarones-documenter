"""The plan bill: what documenting this project took from zero — tokens, time and API-equivalent dollars of every run,
interactive unit session and agent-written wiki of the current plan, for the whole team.

Runs are already in each machine's KPIs roll-up (docs/.work/kpis/<person-machine>.json, `runs.<id>.by_unit`). This
module harvests the interactive sessions into the same file (`sessions.<id>`), read from Claude Code's transcripts of
the units' own conversations, and adds the team's files up."""
from __future__ import annotations

import json

from .. import sessions
from ..common import WORKSPACE, load_json
from . import kpis, transcripts

KEEP = 500                     # sessions kept per machine file


def _records() -> list[dict]:
    out = []
    for f in sorted(sessions.DIR.glob("*.json")) if sessions.DIR.is_dir() else []:
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict) and rec.get("unit"):
            out.append(rec)
    return out


def _claude_ids(rec: dict) -> list[str]:
    ids = [s for s in rec.get("previous") or [] if isinstance(s, str) and s]
    if rec.get("agent") == "claude" and rec.get("session"):
        ids.append(rec["session"])
    return list(dict.fromkeys(ids))


def local_sessions(known: dict | None = None, units: list[str] | None = None) -> dict[str, dict]:
    """This machine's Claude unit sessions with a transcript; an entry of `known` whose files have not grown is reused
    without reading them again."""
    known = known or {}
    folder = sessions.claude_dir(WORKSPACE)
    out: dict[str, dict] = {}
    for rec in _records():
        if units is not None and rec["unit"] not in units:
            continue
        for sid in _claude_ids(rec):
            path = folder / f"{sid}.jsonl"
            size = transcripts.size(path)
            old = known.get(sid)
            if not size:
                continue
            if isinstance(old, dict) and old.get("bytes") == size and old.get("unit") == rec["unit"]:
                out[sid] = old
                continue
            r = transcripts.read(path)
            if r is None:
                continue
            out[sid] = {"unit": rec["unit"], "agent": "claude", "started": r["first"], "ended": r["last"],
                        "active_seconds": r["active_seconds"], "bytes": r["bytes"], "models": r["models"]}
    return out


def harvest(units: list[str] | None = None) -> int:
    """Write this machine's unit sessions into its roll-up; how many entries changed. Never fails its caller."""
    from .. import usage
    try:
        if not usage.enabled():
            return 0
        mine = load_json(kpis.DIR / f"{usage.me()}.json", {})
        known = mine.get("sessions") if isinstance(mine, dict) and isinstance(mine.get("sessions"), dict) else {}
        found = local_sessions(known, units)
        changed = [sid for sid, entry in found.items() if known.get(sid) != entry]
        if not changed:
            return 0

        def change(data: dict) -> None:
            kept = data.get("sessions") if isinstance(data.get("sessions"), dict) else {}
            kept.update({sid: found[sid] for sid in changed})
            newest = sorted(kept.items(), key=lambda kv: str((kv[1] or {}).get("started") or ""))[-KEEP:]
            data["sessions"] = dict(newest)
        return len(changed) if kpis.update_rollup(change) else 0
    except Exception:  # noqa: BLE001 — stats must never fail a run or closing a unit
        return 0
