"""The plan bill: what documenting this project took from zero — every run, interactive unit session and wiki of the
current plan, priced and timed, for the whole team. Sessions are harvested from Claude Code's transcripts into the
machine's KPIs roll-up (docs/.work/kpis/<person-machine>.json), written only when something changed."""
from __future__ import annotations

import json, time

import pytest

T0 = "2026-10-27T10:00:00.000Z"


@pytest.fixture
def ledger(kit):
    from lib.harness import ledger
    return ledger


def a(mid, model, ts, **usage):
    return {"type": "assistant", "timestamp": ts,
            "message": {"id": mid, "model": model, "usage": {"input_tokens": 0, "output_tokens": 0, **usage}}}


def transcript(kit, sid, lines):
    from lib import sessions
    f = sessions.claude_dir(kit.common.WORKSPACE) / f"{sid}.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8", newline="\n")
    return f


def record(kit, uid, sid, agent="claude"):
    from lib import sessions
    return sessions.start(uid, agent, sid)


def kpis_files(kit):
    return sorted((kit.root / "docs" / ".work" / "kpis").glob("*.json"))


def rollup(kit) -> dict:
    files = kpis_files(kit)
    assert len(files) == 1
    return json.loads(files[0].read_text(encoding="utf-8"))


# ---------- harvest: interactive sessions into the roll-up ----------
def test_harvest_writes_a_unit_session(kit, ledger):
    record(kit, "domain", "s-1")
    transcript(kit, "s-1", [a("m1", "claude-opus-5-5", T0, output_tokens=7)])
    assert ledger.harvest() == 1
    s = rollup(kit)["sessions"]["s-1"]
    assert (s["unit"], s["agent"], s["started"]) == ("domain", "claude", T0)
    assert s["models"]["claude-opus-5-5"]["out"] == 7


def test_an_unchanged_transcript_is_neither_read_nor_written(kit, ledger, monkeypatch):
    record(kit, "domain", "s-1")
    transcript(kit, "s-1", [a("m1", "x", T0, output_tokens=7)])
    ledger.harvest()
    f = kpis_files(kit)[0]
    before = f.stat().st_mtime_ns
    from lib.harness import transcripts
    monkeypatch.setattr(transcripts, "read", lambda p: pytest.fail("read again"))
    time.sleep(0.05)
    assert ledger.harvest() == 0 and f.stat().st_mtime_ns == before


def test_a_grown_transcript_is_read_again_whole(kit, ledger):
    record(kit, "domain", "s-1")
    transcript(kit, "s-1", [a("m1", "x", T0, output_tokens=7)])
    ledger.harvest()
    transcript(kit, "s-1", [a("m1", "x", T0, output_tokens=7), a("m2", "x", T0, output_tokens=5)])
    assert ledger.harvest() == 1
    assert rollup(kit)["sessions"]["s-1"]["models"]["x"]["out"] == 12


def test_a_restarted_unit_keeps_its_earlier_session(kit, ledger):
    from lib import sessions
    record(kit, "domain", "s-1")
    record(kit, "domain", "s-2")
    record(kit, "domain", "s-2")                                   # continue: the same conversation again
    assert sessions.load("domain")["previous"] == ["s-1"]
    transcript(kit, "s-1", [a("m1", "x", T0, output_tokens=1)])
    transcript(kit, "s-2", [a("m2", "x", T0, output_tokens=2)])
    assert ledger.harvest() == 2
    assert set(rollup(kit)["sessions"]) == {"s-1", "s-2"}


def test_with_stats_off_nothing_is_written_but_the_bill_sees_it(kit, ledger):
    kit.usage.set_enabled(False)
    record(kit, "domain", "s-1")
    transcript(kit, "s-1", [a("m1", "x", T0, output_tokens=7)])
    assert ledger.harvest() == 0 and not kpis_files(kit)
    assert ledger.local_sessions()["s-1"]["unit"] == "domain"


def test_marking_a_unit_done_harvests_only_that_unit(kit, ledger):
    kit.plan.sync()
    for uid, sid in (("domain", "s-1"), ("data", "s-2")):
        record(kit, uid, sid)
        transcript(kit, sid, [a(f"m-{sid}", "x", T0, output_tokens=1)])
    kit.plan.set_status("domain", "done")
    assert set(rollup(kit)["sessions"]) == {"s-1"}


def test_a_codex_session_is_not_harvested(kit, ledger):
    record(kit, "domain", None, agent="codex")
    assert ledger.harvest() == 0 and ledger.local_sessions() == {}


# ---------- the epoch: where "from zero" starts ----------
def test_a_new_plan_starts_its_epoch(kit):
    import re
    kit.plan.sync()
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", kit.plan.load()["epoch"])


def test_an_old_plan_gets_no_epoch(kit):
    kit.plan.sync()
    data = kit.plan.load()
    data.pop("epoch")
    kit.plan.save(data)
    kit.plan.sync()
    assert "epoch" not in kit.plan.load()


# ---------- the bill ----------
P2 = {"revised": "2026-10-27", "source": "test", "aliases": {},
      "models": {"m-1": {"in": 1, "out": 10, "cache_read": 0.1, "cache_write_5m": 1.25, "cache_write_1h": 2},
                 "gpt-5.6-terra": {"in": 1, "out": 10, "cache_read": 0.1, "cache_write_5m": 0, "cache_write_1h": 0}},
      "runners": {"claude": "m-1", "codex": "gpt-5.6-terra"}}
M = 1_000_000


@pytest.fixture
def priced(kit, monkeypatch):
    from lib.harness import pricing
    monkeypatch.setattr(pricing, "_kit", lambda: P2)
    kit.plan.sync()
    return kit


def set_epoch(kit, value):
    data = kit.plan.load()
    data.pop("epoch", None)
    if value:
        data["epoch"] = value
    kit.plan.save(data)


def teammate(kit, name, runs=None, sessions=None, raw=None):
    d = kit.root / "docs" / ".work" / "kpis"
    d.mkdir(parents=True, exist_ok=True)
    body = raw if raw is not None else {"v": 1, "runs": runs or {}, "sessions": sessions or {}}
    (d / f"{name}.json").write_text(json.dumps(body), encoding="utf-8")


def run_entry(started, unit, cost=None, runner="claude", model=None, tin=0, seconds=60):
    return {"run": "r", "started": started, "seconds": seconds, "units": 1, "done": 1, "cost_usd": cost or 0,
            "tokens_in": tin, "tokens_out": 0, "tokens_cache": 0,
            "by_unit": {unit: {"in": tin, "out": 0, "cache_read": 0, "cache_write": 0, "cost_usd": cost,
                               "seconds": seconds, "runner": runner, "model": model}}}


def session_entry(unit, started, ended, model="m-1", active=0, **tokens):
    return {"unit": unit, "agent": "claude", "started": started, "ended": ended, "active_seconds": active, "bytes": 1,
            "models": {model: {"in": 0, "out": 0, "cache_read": 0, "cache_write_5m": 0, "cache_write_1h": 0, **tokens}}}


def units_by_id(b):
    return {u["unit"]: u for u in b["units"]}


def test_two_machines_add_up_without_counting_twice(priced, ledger):
    set_epoch(priced, None)
    teammate(priced, "aaaa-111", runs={"r-1": run_entry("2026-10-21T10:00:00Z", "domain", cost=1.0)})
    teammate(priced, "bbbb-222", runs={"r-1": run_entry("2026-10-21T10:00:00Z", "domain", cost=1.0),
                                       "r-2": run_entry("2026-10-21T11:00:00Z", "data", cost=2.0)})
    b = ledger.bill()
    assert b["cost_usd"] == 3.0 and b["people"] == 2 and b["complete"] is True


def test_only_what_started_after_the_epoch_counts(priced, ledger):
    set_epoch(priced, "2026-10-20T00:00:00Z")
    teammate(priced, "aaaa-111", runs={"r-1": run_entry("2026-10-19T10:00:00Z", "domain", cost=2.0),
                                       "r-2": run_entry("2026-10-21T10:00:00Z", "data", cost=3.0)})
    b = ledger.bill()
    assert b["cost_usd"] == 3.0 and b["before"]["cost_usd"] == 2.0 and b["epoch"] == "2026-10-20T00:00:00Z"


def test_a_plan_without_epoch_counts_everything(priced, ledger):
    set_epoch(priced, None)
    teammate(priced, "aaaa-111", runs={"r-1": run_entry("2026-10-19T10:00:00Z", "domain", cost=2.0),
                                       "r-2": run_entry("2026-10-21T10:00:00Z", "data", cost=3.0)})
    b = ledger.bill()
    assert b["cost_usd"] == 5.0 and b["before"] is None


def test_reported_cost_wins_and_codex_is_priced_by_the_table(priced, ledger):
    set_epoch(priced, None)
    teammate(priced, "aaaa-111", runs={
        "r-1": run_entry("2026-10-21T10:00:00Z", "domain", cost=0.40, tin=M),
        "r-2": run_entry("2026-10-21T11:00:00Z", "data", cost=None, runner="codex", tin=M)})
    u = units_by_id(ledger.bill())
    assert (u["domain"]["cost_usd"], u["data"]["cost_usd"]) == (0.4, 1.0)


def test_an_unknown_model_is_unpriced_and_the_bill_incomplete(priced, ledger):
    set_epoch(priced, None)
    teammate(priced, "aaaa-111", sessions={"s-1": session_entry("domain", T0, T0, model="zz-9", **{"in": 1000})})
    b = ledger.bill()
    assert units_by_id(b)["domain"]["cost_usd"] is None
    assert b["unpriced"][0]["model"] == "zz-9" and b["complete"] is False


def test_sessions_count_as_time_with_a_person(priced, ledger):
    set_epoch(priced, None)
    teammate(priced, "aaaa-111", runs={"r-1": run_entry("2026-10-27T10:00:00Z", "data", cost=0.1, seconds=60)},
             sessions={"s-1": session_entry("domain", "2026-10-27T10:00:00Z", "2026-10-27T10:02:00Z", active=120)})
    b = ledger.bill()
    assert b["seconds"] == {"unattended": 60, "with_person": 120, "calendar": 120}
    assert units_by_id(b)["domain"]["sessions"] == 1 and units_by_id(b)["data"]["runs"] == 1


def test_phases_and_the_most_expensive_units(priced, ledger):
    set_epoch(priced, None)
    teammate(priced, "aaaa-111", runs={"r-1": run_entry("2026-10-21T10:00:00Z", "discovery:api", cost=1.0),
                                       "r-2": run_entry("2026-10-21T11:00:00Z", "domain", cost=3.0),
                                       "r-3": run_entry("2026-10-21T12:00:00Z", "data", cost=2.0)})
    b = ledger.bill()
    assert [u["unit"] for u in b["units"]][:3] == ["domain", "data", "discovery:api"]
    assert next(p for p in b["phases"] if p["phase"] == 1)["cost_usd"] == 1.0


def test_a_removed_unit_keeps_its_phase_from_its_type(priced, ledger):
    set_epoch(priced, None)
    teammate(priced, "aaaa-111", runs={"r-1": run_entry("2026-10-21T10:00:00Z", "discovery:gone", cost=1.0),
                                       "r-2": run_entry("2026-10-21T11:00:00Z", "weird", cost=1.0)})
    u = units_by_id(ledger.bill())
    assert (u["discovery:gone"]["phase"], u["weird"]["phase"]) == (1, None)


def test_mixed_timestamp_forms_compare(priced, ledger):
    set_epoch(priced, "2026-10-20T00:00:00Z")
    teammate(priced, "aaaa-111", runs={"r-1": run_entry("2026-10-21T10:00:00+00:00", "data", cost=1.0)},
             sessions={"s-1": session_entry("domain", "2026-10-21T10:00:00", "2026-10-21T10:05:00")})
    assert set(units_by_id(ledger.bill())) == {"data", "domain"}


def test_a_damaged_teammate_file_is_skipped_with_a_note(priced, ledger):
    set_epoch(priced, None)
    teammate(priced, "bad-1", raw={"runs": [], "sessions": "x"})
    teammate(priced, "aaaa-111", runs={"r-1": run_entry("2026-10-21T10:00:00Z", "data", cost=1.0)})
    b = ledger.bill()
    assert b["cost_usd"] == 1.0 and any("bad-1.json" in n for n in b["notes"])


def test_unmeasured_and_unrecorded_are_named(priced, ledger):
    kit = priced
    set_epoch(kit, None)
    kit.docs.set_wiki_repos(["api"])
    kit.plan.sync()
    record(kit, "interview-context", None, agent="codex")
    wiki = kit.docs.wiki_dir("api")
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / kit.env.WIKI_STAMP).write_text(json.dumps({"scope": 2, "engine": "openwiki"}), encoding="utf-8")
    for uid in ("repo-wiki:api", "domain"):
        kit.plan.set_status(uid, "done", record=False)
    b = ledger.bill()
    whys = {u["unit"]: u["why"] for u in b["unmeasured"]}
    assert whys == {"interview-context": "codex-session", "repo-wiki:api": "openwiki-native"}
    assert b["unrecorded"] == 1 and b["complete"] is False


def test_the_bill_is_json(priced, ledger):
    json.dumps(ledger.bill())


def test_lines_read_like_the_spec(priced, ledger):
    test_two_machines_add_up_without_counting_twice(priced, ledger)
    out = "\n".join(ledger.lines(ledger.bill()))
    assert "Plan from zero" in out and "API-equivalent" in out and "$3.00" in out and "2 people" in out


def test_a_damaged_entry_inside_a_rollup_does_not_break_the_bill(priced, ledger):
    set_epoch(priced, None)
    teammate(priced, "aaaa-111", runs={"r-1": {"started": "2026-10-21T10:00:00Z", "by_unit": {"domain": "x"}},
                                       "r-2": run_entry("2026-10-21T11:00:00Z", "data", cost=1.0)},
             sessions={"s-1": {"unit": "domain", "started": "2026-10-21T10:00:00Z", "models": "y"}})
    assert ledger.bill()["cost_usd"] == 1.0


# ---------- camaron plan cost ----------
def cli(kit, *args):
    import os, subprocess, sys
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8")


def test_plan_cost_prints_the_bill_and_its_json(kit):
    kit.plan.sync()
    teammate(kit, "aaaa-111", runs={"r-1": run_entry(kit.plan.utcnow(), "domain", cost=1.5)})
    r = cli(kit, "plan", "cost")
    assert r.returncode == 0, r.stderr
    assert "Plan from zero" in r.stdout and "$1.50" in r.stdout and "API-equivalent" in r.stdout
    j = cli(kit, "plan", "cost", "--json")
    assert j.returncode == 0, j.stderr
    b = json.loads(j.stdout)
    assert b["cost_usd"] == 1.5 and b["units"][0]["unit"] == "domain"
