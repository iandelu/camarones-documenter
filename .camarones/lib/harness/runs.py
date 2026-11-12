"""What past runs did and cost (R15), read back from their event logs (.camarones/.cache/runs/<run>/events.jsonl)."""
from __future__ import annotations

import datetime as dt

from ..common import CTX
from . import routing
from .events import EventLog

MERGE = {"merge.ok": "merged", "merge.conflict": "conflict", "gate.failed": "gate-failed", "merge.blocked": "main-dirty"}
WIKI = "-wiki-"                 # a wiki written by an agent runner: a run of its own, never the plan's latest run


def ids(wiki: bool = True) -> list[str]:
    """Run ids, newest first (they start with their date)."""
    found = (d.name for d in CTX.runs.iterdir() if (d / "events.jsonl").is_file()) if CTX.runs.is_dir() else ()
    return sorted((r for r in found if wiki or WIKI not in r), reverse=True)


def events(run_id: str) -> list[dict]:
    return EventLog(CTX.runs / run_id / "events.jsonl").read()[0]


def _ts(ev: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(ev["ts"].replace("Z", "+00:00"))


def _kind(evs: list[dict]) -> str | None:
    """autopilot or parallel, from how the run started; None for a log with no start (or a wiki's)."""
    start = next((e for e in evs if e["type"] == "run.started"), {})
    return "parallel" if "parallel" in start else "autopilot" if "agents" in start else None


def active() -> dict | None:
    """The plan run in progress on this machine, which may be another process: the newest log, while someone holds the
    run lock and it has not logged its end."""
    from . import scheduler
    latest = ids(wiki=False)
    if not latest or scheduler.busy() is None:
        return None
    evs = events(latest[0])
    return None if any(e["type"] == "run.finished" for e in evs) else {"run": latest[0], "kind": _kind(evs)}


def running(run_id: str, uid: str) -> bool:
    """The run's agent is at work on the unit: its last start has no finish after it."""
    last = [e["type"] for e in events(run_id) if e.get("unit") == uid and e["type"] in ("unit.started", "unit.finished")]
    return bool(last) and last[-1] == "unit.started"


def last_session(uid: str, run_id: str | None = None) -> dict | None:
    """The conversation of the unit's last attempt in that run (default: the newest), and its agent: `id` is None for a
    runner with no conversation of its own. None when that run never worked on the unit."""
    if run_id is None:
        run_id = next(iter(ids(wiki=False)), None)
    found = None
    for e in events(run_id) if run_id else ():
        if e.get("unit") == uid and e["type"] in ("unit.started", "session"):
            found = {"id": e.get("resume") if e["type"] == "unit.started" else e.get("id"),
                     "agent": routing.parse(e.get("runner") or "").runner}
    return found


def slots(run_id: str) -> dict:
    """While a run works: the `parallel` it was asked for, the units its agents are on (in the order they started) and
    the ready units it left out with why (the scheduler's last run.slots: shared, runner, limit). Empty once it ended."""
    evs = events(run_id)
    start = next((e for e in evs if e["type"] == "run.started"), {})
    if any(e["type"] == "run.finished" for e in evs):
        return {"parallel": start.get("parallel"), "running": [], "waiting": {}}
    last: dict[str, str] = {}
    for e in evs:
        if e["type"] in ("unit.started", "unit.finished") and e.get("unit"):
            last.pop(e["unit"], None)
            last[e["unit"]] = e["type"]
    told = next((e for e in reversed(evs) if e["type"] == "run.slots"), {})
    return {"parallel": start.get("parallel"), "running": [u for u, kind in last.items() if kind == "unit.started"],
            "waiting": told.get("waiting") or {}}


def summary(run_id: str) -> dict:
    evs = events(run_id)
    end = next((e for e in reversed(evs) if e["type"] == "run.finished"), None)
    finished = [e for e in evs if e["type"] == "unit.finished"]
    usage = [e for e in evs if e["type"] == "usage"]
    done = end["done"] if end and "done" in end else sum(1 for e in finished if e.get("outcome") == "ok"
                                                           and e.get("status") == "done")
    return {"run": run_id, "kind": _kind(evs), "started": evs[0]["ts"] if evs else None, "finished": end is not None,
            "interrupted": bool(end and end.get("interrupted")),
            "seconds": round((_ts(evs[-1]) - _ts(evs[0])).total_seconds(), 1) if evs else 0.0,
            "units": sum(1 for e in evs if e["type"] == "unit.started"), "done": done,
            "limited": sum(1 for e in finished if e.get("outcome") == "limited"),
            "failed": sum(1 for e in finished if e.get("outcome") not in ("ok", "limited", "handed") and not e.get("stopped")),
            "tokens_in": sum(e.get("in", 0) for e in usage), "tokens_out": sum(e.get("out", 0) for e in usage),
            "tokens_cache": sum(e.get("cache_read", 0) + e.get("cache_write", 0) for e in usage),
            "cost_usd": round(sum(e.get("cost_usd", 0) or 0 for e in usage), 6)}


def detail(run_id: str) -> dict:
    """The run's summary plus one row per unit attempt (a unit re-queued after a usage limit has two)."""
    rows, open_ = [], {}
    for e in events(run_id):
        uid = e.get("unit")
        if e["type"] == "unit.started":
            open_[uid] = {"unit": uid, "runner": e.get("runner"), "isolation": e.get("isolation"), "outcome": None,
                          "status": None, "seconds": None, "merge": None, "tokens_in": 0, "tokens_cache": 0,
                          "tokens_out": 0, "cache_read": 0, "cache_write": 0,
                          "model": routing.parse(e.get("runner") or "").model, "cost_reported": False,
                          "cost_usd": 0.0}
            rows.append(open_[uid])
        elif e["type"] == "usage" and uid in open_:
            r = open_[uid]
            r["tokens_in"] += e.get("in", 0)
            r["tokens_cache"] += e.get("cache_read", 0) + e.get("cache_write", 0)
            r["cache_read"] += e.get("cache_read", 0)
            r["cache_write"] += e.get("cache_write", 0)
            r["tokens_out"] += e.get("out", 0)
            r["model"] = e.get("model") or r["model"]
            r["cost_reported"] = r["cost_reported"] or e.get("cost_usd") is not None
            r["cost_usd"] = round(r["cost_usd"] + (e.get("cost_usd") or 0), 6)
        elif e["type"] == "unit.finished" and uid in open_:
            open_[uid].update(outcome=e.get("outcome"), status=e.get("status"), seconds=e.get("seconds"))
        elif e["type"] in MERGE:
            last = next((r for r in reversed(rows) if r["unit"] == uid), None)
            if last:
                last["merge"] = MERGE[e["type"]]
    return {**summary(run_id), "units": rows}


def rows() -> list[dict]:
    return [summary(r) for r in ids()]
