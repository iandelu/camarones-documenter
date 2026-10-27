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
