"""The plan bill: what documenting this project took from zero — tokens, time and API-equivalent dollars of every run,
interactive unit session and agent-written wiki of the current plan, for the whole team.

Runs are already in each machine's KPIs roll-up (docs/.work/kpis/<person-machine>.json, `runs.<id>.by_unit`). This
module harvests the interactive sessions into the same file (`sessions.<id>`), read from Claude Code's transcripts of
the units' own conversations, and adds the team's files up."""
from __future__ import annotations

import datetime as dt
import json

from .. import sessions
from ..common import WORKSPACE, load_json
from . import kpis, pricing, runs, transcripts

KEEP = 500                     # sessions kept per machine file
WHY = {"codex-session": "Codex session", "openwiki-native": "native OpenWiki", "transcript-missing": "transcript not found"}


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


# ---------- the bill ----------
def _when(ts) -> dt.datetime | None:
    """`…Z`, `…+00:00` or naive (local time, as plan.now() writes): always an aware datetime, or None."""
    if not ts:
        return None
    try:
        d = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.astimezone()


def _team(notes: list[str]) -> tuple[dict, dict]:
    """Every machine's runs and sessions: {id: (entry, person)}; the first file that has an id keeps it."""
    team_runs, team_sessions = {}, {}
    for f in sorted(kpis.DIR.glob("*.json")) if kpis.DIR.is_dir() else []:
        data = load_json(f, None)
        if not isinstance(data, dict):
            notes.append(f"{f.name}: not a readable roll-up, skipped")
            continue
        person = f.stem.rsplit("-", 1)[0]
        for key, into in (("runs", team_runs), ("sessions", team_sessions)):
            block = data.get(key, {})
            if not isinstance(block, dict):
                notes.append(f"{f.name}: {key} is not a mapping, skipped")
                continue
            for k, v in block.items():
                if isinstance(v, dict):
                    into.setdefault(k, (v, person))
    return team_runs, team_sessions


def _phase_of(plan_units: dict, uid: str | None):
    from .. import plan
    if uid is None:
        return None
    if uid in plan_units:
        return plan_units[uid].get("phase")
    t = plan.TYPES.get(uid.split(":", 1)[0])
    return t[0] if t else None


def _tokens(t: dict | None = None) -> dict:
    t = t or {}
    return {"in": t.get("in", 0), "out": t.get("out", 0), "cache_read": t.get("cache_read", 0),
            "cache_write": t.get("cache_write", 0) + t.get("cache_write_5m", 0) + t.get("cache_write_1h", 0)}


def _add_tokens(into: dict, more: dict) -> None:
    for k, v in more.items():
        into[k] = into.get(k, 0) + v


def _add_cost(a, b):
    return b if a is None else a if b is None else round(a + b, 6)


def _unmeasured(epoch, team_sessions: dict, rows: dict, plan_units: dict) -> list[dict]:
    from .. import docs, env
    out = []
    folder = sessions.claude_dir(WORKSPACE)
    for rec in _records():
        launched = dt.datetime.fromtimestamp(float(rec.get("launched") or 0), dt.timezone.utc)
        if epoch and launched < epoch:
            continue
        if rec.get("agent") != "claude":
            out.append({"unit": rec["unit"], "why": f"{rec.get('agent') or 'agent'}-session"})
            continue
        for sid in _claude_ids(rec):
            if sid not in team_sessions and not transcripts.size(folder / f"{sid}.jsonl"):
                out.append({"unit": rec["unit"], "why": "transcript-missing"})
    for uid, u in plan_units.items():
        if u.get("type") != "repo-wiki" or u.get("status") != "done" or uid in rows or not u.get("repo"):
            continue
        stamp = load_json(docs.wiki_dir(u["repo"]) / env.WIKI_STAMP, {})
        if isinstance(stamp, dict) and stamp.get("engine") == "openwiki":
            out.append({"unit": uid, "why": "openwiki-native"})
    return [dict(t) for t in dict.fromkeys(tuple(sorted(x.items())) for x in out)]


def bill() -> dict:
    """The current plan's bill for the whole team (spec: docs/superpowers/specs/2026-10-27-plan-cost-design.md §9)."""
    from .. import docs, plan, usage
    notes: list[str] = []
    workspace = docs.workspace()
    tbl, problems = pricing.table(workspace)
    data = plan.load()
    plan_units = {u["id"]: u for u in data.get("units") or []}
    epoch = _when(data.get("epoch"))
    team_runs, team_sessions = _team(notes)
    me = usage.me().rsplit("-", 1)[0]
    for rid in runs.ids():
        if rid not in team_runs:
            try:
                team_runs[rid] = (kpis.run_metrics(rid), me)
            except (ValueError, KeyError, IndexError, OSError):
                continue
    own = {sid: e for sid, (e, person) in team_sessions.items() if person == me}
    for sid, entry in local_sessions(known=own).items():
        team_sessions[sid] = (entry, me)

    rows: dict = {}
    unpriced: list[dict] = []
    people: set = set()
    secs = {"unattended": 0.0, "with_person": 0.0}
    span: list[dt.datetime] = []
    before = {"cost_usd": 0.0, "seconds": 0.0, "units": set()}
    any_before = False

    def row(uid):
        return rows.setdefault(uid, {"unit": uid, "phase": _phase_of(plan_units, uid), "cost_usd": None,
                                     "seconds": 0.0, "tokens": _tokens(), "runs": 0, "sessions": 0})

    def in_plan(start) -> bool:
        return not epoch or start is None or start >= epoch

    for rid, (r, person) in sorted(team_runs.items()):
        start = _when(r.get("started"))
        by_unit = r.get("by_unit") if isinstance(r.get("by_unit"), dict) else None
        parts = by_unit.items() if by_unit is not None else [(None, None)]
        for uid, u in parts:
            if by_unit is not None and not isinstance(u, dict):
                continue
            if u is None:
                tokens = {"in": r.get("tokens_in", 0), "out": r.get("tokens_out", 0),
                          "cache_read": r.get("tokens_cache", 0), "cache_write": 0}
                cost, seconds = r.get("cost_usd"), float(r.get("seconds") or 0)
            else:
                tokens = _tokens(u)
                cost, seconds = u.get("cost_usd"), float(u.get("seconds") or 0)
                if cost is None:
                    cost = pricing.cost(tokens, u.get("model"), u.get("runner"), tbl)
                    if cost is None and any(tokens.values()):
                        unpriced.append({"source": "run", "id": rid, "unit": uid,
                                         "model": u.get("model") or u.get("runner")})
            if not in_plan(start):
                any_before = True
                before["cost_usd"] = _add_cost(before["cost_usd"], cost)
                before["seconds"] += seconds
                before["units"].add(uid)
                continue
            x = row(uid)
            x["cost_usd"] = _add_cost(x["cost_usd"], cost)
            x["seconds"] += seconds
            x["runs"] += 1
            _add_tokens(x["tokens"], tokens)
            secs["unattended"] += seconds
        if in_plan(start):
            people.add(person)
            if start:
                span += [start, start + dt.timedelta(seconds=float(r.get("seconds") or 0))]

    for sid, (s, person) in sorted(team_sessions.items()):
        start, end = _when(s.get("started")), _when(s.get("ended"))
        seconds = float(s.get("active_seconds") or 0)
        cost, tokens = None, _tokens()
        models = s.get("models") if isinstance(s.get("models"), dict) else {}
        for model, t in models.items():
            t = t if isinstance(t, dict) else {}
            _add_tokens(tokens, _tokens(t))
            c = pricing.cost(t, model, None, tbl)
            if c is None and any(t.values()):
                unpriced.append({"source": "session", "id": sid, "unit": s.get("unit"), "model": model})
            cost = _add_cost(cost, c)
        if not in_plan(start):
            any_before = True
            before["cost_usd"] = _add_cost(before["cost_usd"], cost)
            before["seconds"] += seconds
            before["units"].add(s.get("unit"))
            continue
        x = row(s.get("unit"))
        x["cost_usd"] = _add_cost(x["cost_usd"], cost)
        x["seconds"] += seconds
        x["sessions"] += 1
        _add_tokens(x["tokens"], tokens)
        secs["with_person"] += seconds
        people.add(person)
        span += [d for d in (start, end) if d]

    unmeasured = _unmeasured(epoch, team_sessions, rows, plan_units)
    named = {u["unit"] for u in unmeasured} | before["units"]
    unrecorded = sum(1 for uid, u in plan_units.items() if u.get("status") == "done" and u.get("runner") == "agent"
                     and uid not in rows and uid not in named)
    units = sorted(rows.values(), key=lambda u: (-(u["cost_usd"] or 0), str(u["unit"])))
    for u in units:
        u["seconds"] = round(u["seconds"], 1)
    phases: dict = {}
    for u in units:
        ph = phases.setdefault(u["phase"], {"phase": u["phase"], "cost_usd": None, "seconds": 0.0, "tokens": _tokens()})
        ph["cost_usd"] = _add_cost(ph["cost_usd"], u["cost_usd"])
        ph["seconds"] = round(ph["seconds"] + u["seconds"], 1)
        _add_tokens(ph["tokens"], u["tokens"])
    tokens = _tokens()
    for u in units:
        _add_tokens(tokens, u["tokens"])
    over = (workspace.get("pricing") or {}) if isinstance(workspace.get("pricing"), dict) else {}
    return {
        "epoch": data.get("epoch"),
        "since": data.get("epoch") or (min(span).isoformat() if span else None),
        "people": len(people),
        "seconds": {"unattended": round(secs["unattended"], 1), "with_person": round(secs["with_person"], 1),
                    "calendar": round((max(span) - min(span)).total_seconds(), 1) if span else 0.0},
        "tokens": tokens,
        "cost_usd": round(sum(u["cost_usd"] or 0 for u in units), 6),
        "complete": not unpriced and not unmeasured,
        "phases": sorted(phases.values(), key=lambda p: (p["phase"] is None, p["phase"] or 0)),
        "units": units,
        "unpriced": unpriced,
        "unmeasured": unmeasured,
        "unrecorded": unrecorded,
        "before": {"cost_usd": before["cost_usd"], "seconds": round(before["seconds"], 1)} if any_before else None,
        "pricing": {"revised": str(tbl.get("revised") or ""), "problems": problems,
                    "overridden": sorted(over.get("models") or {}) if isinstance(over.get("models"), dict) else []},
        "notes": notes,
    }


def _money(usd) -> str:
    return "—" if usd is None else f"${usd:,.2f}"


def _duration(s) -> str:
    if s is None:
        return "—"
    s = float(s)
    if s < 60:
        return f"{s:.0f} s"
    if s < 3600:
        return f"{s // 60:.0f} min"
    if s < 172800:
        return f"{s // 3600:.0f} h {s % 3600 // 60:.0f} min"
    return f"{s / 86400:.0f} days"


def _count(n) -> str:
    return f"{n / 1e6:.1f} M" if n >= 1e6 else f"{n / 1e3:.0f} k" if n >= 1e3 else str(n)


def lines(b: dict) -> list[str]:
    since = str(b["since"] or "")[:10] or "the start"
    who = f", {b['people']} {'person' if b['people'] == 1 else 'people'}" if b["people"] else ""
    out = [f"Plan from zero (since {since}{who})"]
    if not b["units"]:
        out.append("  Nothing recorded yet: runs, unit sessions and agent-written wikis appear here as they happen.")
    else:
        s, t = b["seconds"], b["tokens"]
        out += [f"  Time      unattended {_duration(s['unattended'])} · with a person {_duration(s['with_person'])}"
                f" · calendar {_duration(s['calendar'])}",
                f"  Tokens    in {_count(t['in'])} · cache {_count(t['cache_read'] + t['cache_write'])}"
                f" · out {_count(t['out'])}",
                f"  Cost      {_money(b['cost_usd'])} API-equivalent (prices revised {b['pricing']['revised']})",
                "  By phase  " + " · ".join(f"{'other' if p['phase'] is None else p['phase']} {_money(p['cost_usd'])}"
                                            for p in b["phases"]),
                "  Top units " + " · ".join(f"{u['unit'] or 'unit unknown'} {_money(u['cost_usd'])}"
                                            for u in b["units"][:3])]
    if b["unpriced"]:
        models = sorted({str(x["model"]) for x in b["unpriced"]})
        out.append(f"  Unpriced  {len(b['unpriced'])} without a price for: {', '.join(models)} "
                   "(add them under pricing: in workspace.yaml)")
    if b["unmeasured"]:
        out.append("  Not measured  " + " · ".join(f"{u['unit']} ({WHY.get(u['why'], u['why'].replace('-', ' '))})"
                                                   for u in b["unmeasured"]))
    if b["unrecorded"]:
        n = b["unrecorded"]
        out.append(f"  No record  {n} unit{'' if n == 1 else 's'} done with no run or session (by hand, or before kit 4.68)")
    if b["before"]:
        out.append(f"  Before the last reset  {_money(b['before']['cost_usd'])} · {_duration(b['before']['seconds'])}")
    out += [f"  ! {n}" for n in [*b["pricing"]["problems"], *b["notes"]]]
    return out
