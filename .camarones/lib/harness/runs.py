"""What past runs did and cost (R15), read back from their event logs (.camarones/.cache/runs/<run>/events.jsonl)."""
from __future__ import annotations

import datetime as dt

from ..common import CTX
from .events import EventLog

MERGE = {"merge.ok": "merged", "merge.conflict": "conflict", "gate.failed": "gate-failed", "merge.blocked": "main-dirty"}


def ids() -> list[str]:
    """Run ids, newest first (they start with their date)."""
    return sorted((d.name for d in CTX.runs.iterdir() if (d / "events.jsonl").is_file()), reverse=True) \
        if CTX.runs.is_dir() else []


def events(run_id: str) -> list[dict]:
    return EventLog(CTX.runs / run_id / "events.jsonl").read()[0]


def _ts(ev: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(ev["ts"].replace("Z", "+00:00"))


def summary(run_id: str) -> dict:
    evs = events(run_id)
    end = next((e for e in reversed(evs) if e["type"] == "run.finished"), None)
    finished = [e for e in evs if e["type"] == "unit.finished"]
    usage = [e for e in evs if e["type"] == "usage"]
    done = end["done"] if end and "done" in end else sum(1 for e in finished if e.get("outcome") == "ok"
                                                           and e.get("status") == "done")
    return {"run": run_id, "started": evs[0]["ts"] if evs else None, "finished": end is not None,
            "interrupted": bool(end and end.get("interrupted")),
            "seconds": round((_ts(evs[-1]) - _ts(evs[0])).total_seconds(), 1) if evs else 0.0,
            "units": sum(1 for e in evs if e["type"] == "unit.started"), "done": done,
            "limited": sum(1 for e in finished if e.get("outcome") == "limited"),
            "failed": sum(1 for e in finished if e.get("outcome") not in ("ok", "limited")),
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
                          "tokens_out": 0,
                          "cost_usd": 0.0}
            rows.append(open_[uid])
        elif e["type"] == "usage" and uid in open_:
            r = open_[uid]
            r["tokens_in"] += e.get("in", 0)
            r["tokens_cache"] += e.get("cache_read", 0) + e.get("cache_write", 0)
            r["tokens_out"] += e.get("out", 0)
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
