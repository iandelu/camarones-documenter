"""Team usage stats: how the docs are consulted (agents through MCP, people through the portal), which features are
used and what searches find nothing. Counters only, no query text: one file per person and machine in
docs/.work/usage/, committed, so `share` brings in the whole team's. Recording is decided per machine (setup asks;
an upgraded project records unless turned off) and never gets in the way of the tool."""
from __future__ import annotations

import hashlib, json, os, platform, getpass
from collections import Counter
from datetime import date, datetime
from functools import lru_cache

from .common import ROOT, CACHE, WORK, WS_FILE, run, out, load_json, save_json

DIR = WORK / "usage"
SETTING = CACHE / "usage.json"
TOP = 10


def enabled() -> bool:
    return bool(load_json(SETTING, {}).get("on", True))


def decided() -> bool:
    return SETTING.exists()


def set_enabled(on: bool) -> None:
    save_json(SETTING, {"on": bool(on)})


def _hash(s: str) -> str:
    return hashlib.sha256(s.strip().lower().encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def me() -> str:
    """<person>-<machine>: hashed git email (or login) and host, so one person on two computers never edits one file."""
    who = out(["git", "config", "user.email"], cwd=ROOT) or getpass.getuser()
    return f"{_hash(who)[:10]}-{_hash(platform.node())[:6]}"


def _inc(d: dict, key: str) -> None:
    d[key] = d.get(key, 0) + 1


def record(event: str, *, channel: str | None = None, hit: bool | None = None, page: str | None = None,
           now: datetime | None = None) -> None:
    """Count one use: `event` is "<source>:<what>"; a search adds hit/miss, a read adds the page, both per channel."""
    try:
        if not WS_FILE.exists() or not enabled():
            return
        now = now or datetime.now()
        f = DIR / f"{me()}.json"
        data = load_json(f, {})
        if not isinstance(data, dict):
            data = {}
        m = data.setdefault("months", {}).setdefault(now.strftime("%Y-%m"), {})
        _inc(m.setdefault("days", {}), now.strftime("%Y-%m-%d"))
        _inc(m.setdefault("events", {}), event)
        if hit is not None:
            _inc(m.setdefault("searches", {}).setdefault(channel or "human", {}), "hit" if hit else "miss")
        if page:
            _inc(m.setdefault("pages", {}).setdefault(channel or "human", {}), page.removeprefix("docs/"))
        data["v"] = 1
        DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE / f"usage-{os.getpid()}.tmp"            # the MCP server and the portal may write at the same time
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                       newline="\n")
        os.replace(tmp, f)
    except Exception:  # noqa: BLE001 — a stats failure must never break a search, a page or a command
        pass


# ---------- report ----------
def _months_back(n: int, today: date) -> list[str]:
    y, m = today.year, today.month
    keys = []
    for _ in range(max(n, 1)):
        keys.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return keys


def _doc_commits(keys: list[str]) -> dict[str, tuple[int, set]]:
    """Commits that changed docs per month, and who wrote them — not the stats or the generated status file."""
    by = {k: (0, set()) for k in keys}
    if not (ROOT / ".git").exists():
        return by
    r = run(["git", "log", "--format=%ad|%ae", "--date=format:%Y-%m", "--", "docs", "wikis",
             ":(exclude)docs/.work/usage", ":(exclude)docs/.status.json"], cwd=ROOT, check=False, capture=True)
    for line in (r.stdout or "").splitlines() if r.returncode == 0 else []:
        k, _, who = line.partition("|")
        if k in by:
            n, people = by[k]
            by[k] = (n + 1, people | {_hash(who)})
    return by


def _health() -> tuple[dict, list[str]]:
    from . import docs, plan
    rows = docs.collect() if (ROOT / "docs").exists() else []
    s = docs.summary(rows)
    done, total = plan.progress() if plan.PLAN.exists() else (0, 0)
    try:
        stale = sum(1 for c in docs.changes().values() if c.get("status") in ("changed", "history-rewritten"))
    except Exception:  # noqa: BLE001 — a repo that cannot be read does not hide the rest of the report
        stale = 0
    return {"pages": s["total"], "confirmed": s["confirmed"], "draft": s["draft"],
            "needs_reconfirm": s["needs-reconfirm"], "confirmed_pct": round(100 * s["confirmed"] / s["total"]) if s["total"] else 0,
            "repos_changed": stale, "plan_done": done, "plan_total": total}, [r["path"] for r in rows]


def report(months: int = 3, today: date | None = None) -> dict:
    """The team's KPIs for the last `months` months (newest first), from everyone's stats files plus git and the docs."""
    keys = _months_back(months, today or date.today())
    people_files = {f.stem: load_json(f, {}) for f in sorted(DIR.glob("*.json"))} if DIR.is_dir() else {}
    commits = _doc_commits(keys)
    rows, everyone = [], set()
    pages: dict[str, Counter] = {}
    features: Counter = Counter()
    for k in keys:
        people, days = set(), set()
        ev: Counter = Counter()
        hits = misses = 0
        for stem, data in people_files.items():
            m = (data.get("months") or {}).get(k) if isinstance(data, dict) else None
            if not m:
                continue
            person = stem.split("-")[0]
            people.add(person)
            days |= {(person, d) for d in m.get("days", {})}
            ev.update(m.get("events", {}))
            for s in m.get("searches", {}).values():
                hits, misses = hits + s.get("hit", 0), misses + s.get("miss", 0)
            for channel, counts in m.get("pages", {}).items():
                for path, n in counts.items():
                    pages.setdefault(path, Counter())[channel] += n
        everyone |= people
        features.update(ev)
        n_commits, writers = commits[k]
        rows.append({"month": k, "people": len(people), "active_days": len(days),
                     "agent_queries": sum(n for e, n in ev.items() if e.startswith("mcp:")),
                     "human_queries": sum(n for e, n in ev.items() if e.startswith("portal:")),
                     "searches": hits + misses, "no_results_pct": round(100 * misses / (hits + misses)) if hits + misses else 0,
                     "doc_commits": n_commits, "writers": len(writers)})
    health, all_pages = _health()
    top = sorted(pages.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[:TOP]
    return {"months": rows, "people": len(everyone), "recording": enabled(), "health": health,
            "top_pages": [{"path": p, "reads": sum(c.values()), "agent": c.get("agent", 0), "human": c.get("human", 0)}
                          for p, c in top],
            "unread_pages": [p for p in all_pages if p not in pages],
            "top_features": [{"event": e, "count": n} for e, n in sorted(features.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP]]}


def render_md(r: dict) -> str:
    h = r["health"]
    lines = [f"# Camarón usage — {r['months'][-1]['month']} → {r['months'][0]['month']}", "",
             f"People who used it: **{r['people']}** · recording on this machine: {'on' if r['recording'] else 'off'}", "",
             "| Month | People | Active days | Agent queries | Human queries | Searches | No results | Doc commits | Writers |",
             "|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {m['month']} | {m['people']} | {m['active_days']} | {m['agent_queries']} | {m['human_queries']} | "
              f"{m['searches']} | {m['no_results_pct']}% | {m['doc_commits']} | {m['writers']} |" for m in r["months"]]
    lines += ["", "## Most read pages", ""]
    lines += [f"{i}. `{p['path']}` — {p['reads']} (agents {p['agent']} · people {p['human']})"
              for i, p in enumerate(r["top_pages"], 1)] or ["No reads yet."]
    lines += ["", f"Never read in this period: {len(r['unread_pages'])} of {h['pages']} pages", "", "## Most used", ""]
    lines += [f"- {f['event']}: {f['count']}" for f in r["top_features"]] or ["Nothing recorded yet."]
    lines += ["", "## Docs health (now)", "",
              f"- Pages: {h['pages']} · confirmed {h['confirmed']} ({h['confirmed_pct']}%) · draft {h['draft']} · "
              f"needs re-confirm {h['needs_reconfirm']}",
              f"- Repos changed since last documented: {h['repos_changed']}",
              f"- Plan: {h['plan_done']}/{h['plan_total']} units done"]
    return "\n".join(lines) + "\n"
