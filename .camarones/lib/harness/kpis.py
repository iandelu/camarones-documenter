"""KPIs (R16): is Camarón working? Four families — cost and speed (run logs), coverage and quality (the docs), trust
(confirmations) and usefulness (usage stats). Each machine rolls its runs up in docs/.work/kpis/<person-machine>.json,
committed like the usage stats, so `share` adds up the team's runs; `compare` puts two runs side by side."""
from __future__ import annotations

import json
import os
from datetime import date  # noqa: F401  (re-exported for callers and tests)
from typing import Callable

from ..common import CACHE, WORK, load_json
from . import runs
from .locks import FileLock

DIR = WORK / "kpis"
LOCK = CACHE / "locks" / "kpis.lock"
KEEP = 500                     # runs kept per machine file
NUMERIC = ("units", "done", "limited", "failed", "seconds", "tokens_in", "tokens_cache", "tokens_out", "cost_usd", "parallelism",
           "cost_per_unit", "seconds_per_unit")


def _by_unit(rows: list[dict]) -> dict[str, dict]:
    """One entry per unit, its attempts added up; cost_usd only what the agent reported (None when it reported none)."""
    out: dict[str, dict] = {}
    for r in rows:
        u = out.setdefault(r["unit"], {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0, "cost_usd": None,
                                       "seconds": 0.0, "runner": None, "model": None})
        u["in"] += r["tokens_in"]
        u["out"] += r["tokens_out"]
        u["cache_read"] += r["cache_read"]
        u["cache_write"] += r["cache_write"]
        u["seconds"] = round(u["seconds"] + (r["seconds"] or 0), 1)
        u["runner"], u["model"] = r["runner"], r["model"]
        if r["cost_reported"]:
            u["cost_usd"] = round((u["cost_usd"] or 0) + r["cost_usd"], 6)
    return out


def run_metrics(run_id: str) -> dict:
    d = runs.detail(run_id)
    s = runs.summary(run_id)
    busy = sum(u["seconds"] or 0 for u in d["units"])
    s["parallelism"] = round(busy / s["seconds"], 2) if s["seconds"] else 0.0
    s["cost_per_unit"] = round(s["cost_usd"] / s["done"], 4) if s["done"] else None
    s["seconds_per_unit"] = round(s["seconds"] / s["done"], 1) if s["done"] else None
    s["by_unit"] = _by_unit(d["units"])
    return s


def compare(a: str, b: str) -> dict:
    ma, mb = run_metrics(a), run_metrics(b)
    delta = {k: round(mb[k] - ma[k], 4) for k in NUMERIC
             if isinstance(ma.get(k), (int, float)) and isinstance(mb.get(k), (int, float))}
    return {"a": ma, "b": mb, "delta": delta}


def update_rollup(change: Callable[[dict], None]) -> bool:
    """Edit this machine's roll-up in place under the lock; written only when it changed (looking never dirties
    cam-docs) and only while usage stats are on. True when it wrote."""
    from .. import usage
    if not usage.enabled():
        return False
    f = DIR / f"{usage.me()}.json"
    with FileLock(LOCK):
        try:
            before = f.read_text(encoding="utf-8")
        except FileNotFoundError:
            before = ""
        data = load_json(f, {})
        data = data if isinstance(data, dict) else {}
        change(data)
        data["v"] = 1
        text = json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        if text == before:
            return False
        DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE / f"kpis-{os.getpid()}.tmp"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, f)
        return True


def record_run(run_id: str) -> None:
    """Add one run to this machine's roll-up (idempotent). Follows the usage-stats switch; never breaks a run."""
    try:
        metrics = run_metrics(run_id)

        def change(data: dict) -> None:
            kept = data.get("runs") if isinstance(data.get("runs"), dict) else {}
            kept[run_id] = metrics
            data["runs"] = dict(sorted(kept.items())[-KEEP:])
        update_rollup(change)
    except Exception:  # noqa: BLE001 — stats must never fail a documentation run
        pass


def _team_runs() -> dict[str, dict]:
    """Every run of the team's roll-ups, plus this machine's runs not recorded yet."""
    out: dict[str, dict] = {}
    for f in sorted(DIR.glob("*.json")) if DIR.is_dir() else []:
        rs = load_json(f, {}).get("runs")
        out.update(rs if isinstance(rs, dict) else {})
    for r in runs.ids():
        if r not in out:
            try:
                out[r] = run_metrics(r)
            except (ValueError, KeyError, IndexError):
                continue
    return out


def coverage(run_check: bool = True) -> dict:
    from .. import docs
    from ..common import DOCS
    repos = docs.repo_names()
    flows = [f for f in (DOCS / "flows").glob("*.md") if f.stem != "index"] if (DOCS / "flows").is_dir() else []
    arch = DOCS / "architecture"
    errors = warnings = None
    if run_check:
        e, w = docs.check()
        errors, warnings = len(e), len(w)
    return {"repos": len(repos), "repos_with_brief": sum(1 for r in repos if (DOCS / "repos" / r / "brief.md").exists()),
            "flows": len(flows), "c4_files": len(list(arch.rglob("*.c4"))) if arch.is_dir() else 0,
            "check_errors": errors, "check_warnings": warnings}


def report(months: int = 3, today: date | None = None, run_check: bool = True) -> dict:
    from .. import usage
    keys = usage._months_back(months, today or date.today())
    team = _team_runs()
    rows = []
    for k in keys:
        rs = [r for r in team.values() if str(r.get("started") or "")[:7] == k]
        done = sum(r.get("done", 0) for r in rs)
        cost = round(sum(r.get("cost_usd", 0) or 0 for r in rs), 4)
        par = [r["parallelism"] for r in rs if r.get("parallelism")]
        rows.append({"month": k, "runs": len(rs), "units": sum(r.get("units", 0) for r in rs), "done": done,
                     "limited": sum(r.get("limited", 0) for r in rs), "failed": sum(r.get("failed", 0) for r in rs),
                     "hours": round(sum(r.get("seconds", 0) for r in rs) / 3600, 2),
                     "tokens_in": sum(r.get("tokens_in", 0) for r in rs),
                     "tokens_cache": sum(r.get("tokens_cache", 0) for r in rs),
                     "tokens_out": sum(r.get("tokens_out", 0) for r in rs), "cost_usd": cost,
                     "cost_per_unit": round(cost / done, 4) if done else None,
                     "parallelism": round(sum(par) / len(par), 2) if par else None})
    u = usage.report(months=1, today=today)
    health, _ = usage._health()
    month = u["months"][0] if u["months"] else {}
    from . import ab, evals
    last, comp = evals.latest() or {}, ab.latest() or {}
    from . import drafts
    return {"runs": rows, "coverage": coverage(run_check), "trust": {**health, **drafts.stats()},
            "usefulness": {**{k: month.get(k) for k in ("agent_queries", "human_queries", "searches", "no_results_pct")},
                           "eval_score": last.get("score"), "eval_judge": last.get("judge"), "eval_at": last.get("at"),
                           "ab": {"at": comp.get("at"), "questions": len(comp.get("questions") or []),
                                  "tokens_saved_pct": comp.get("tokens_saved_pct"), "delta": comp.get("delta")}
                           if comp else None}}


def dashboard(months: int = 6, today: date | None = None) -> dict:
    """Everything the portal's KPIs tab shows, in one call: the CLI's `kpis` and `stats`, plus coverage per repo,
    freshness, the C4 model's confirmed share and this machine's questions nobody found an answer to."""
    from .. import c4edit, docs, usage
    from . import freshness
    r = report(months=months, today=today, run_check=False)
    repos = docs.repo_names()
    by = {n: {"repo": n, "pages": 0, "confirmed": 0, "draft": 0, "needsReconfirm": 0} for n in [*repos, "(project)"]}
    for row in docs.collect():
        owner = next((n for n in repos if row["path"].startswith(f"repos/{n}/")), "(project)")
        key = {"confirmed": "confirmed", "draft": "draft", "needs-reconfirm": "needsReconfirm"}.get(row.get("trust"))
        by[owner]["pages"] += 1
        if key:
            by[owner][key] += 1
    states = freshness.states()
    fresh = {s: sum(1 for v in states.values() if v["state"] == s) for s in ("fresh", "suspect", "stale", "unverified")}
    els = c4edit.index()["elements"].values()
    u = usage.report(months=1, today=today)
    return {"runs": r["runs"], "trust": r["trust"], "usefulness": r["usefulness"],
            "coverage": {**r["coverage"], "byRepo": list(by.values())},
            "freshness": {**fresh, "outOfDate": sorted(p for p, v in states.items() if v["state"] in freshness.OUT_OF_DATE)},
            "c4": {"elements": len(els), "confirmed": sum(1 for e in els if e["confirmed"]),
                   "draft": sum(1 for e in els if e["draft"])},
            "topPages": u["top_pages"], "unreadPages": len(u["unread_pages"]), "people": u["people"],
            "recording": u["recording"], "misses": usage.misses()}
