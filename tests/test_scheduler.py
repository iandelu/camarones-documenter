"""Parallel scheduler (R13): ready units run at the same time, worktree units in their own copy of cam-docs and at most
one in-place unit at a time; finished worktree units are integrated before their dependents start; a usage limit
pauses only that runner and re-queues only its unit."""
from __future__ import annotations

import json, sys
from pathlib import Path

import pytest

FAKE = r'''
import json, os, sys, time
uid, mode = os.environ["CAMARONES_UNIT"], sys.argv[1]
root = os.environ["CAMARONES_ROOT"]
notes = os.path.join(root, "docs", "notes")
def mark(kind):
    with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"unit": uid, "kind": kind, "mode": mode, "t": time.time(), "root": root,
                             "seen": sorted(os.listdir(notes)) if os.path.isdir(notes) else []}) + "\n")
mark("start")
if mode == "limit":
    print("Error: usage limit reached, resets at 5pm")
    sys.exit(1)
time.sleep(float(os.environ.get("FAKE_SLEEP", "0.8")))
os.makedirs(notes, exist_ok=True)
with open(os.path.join(notes, uid.replace(":", "-") + ".md"), "w", encoding="utf-8") as fh:
    fh.write("---\ntitle: note\n---\n# note\n")
sys.path.insert(0, os.environ["KIT_DIR"])
from lib import plan
plan.set_status(uid, os.environ.get("FAKE_STATUS", "done"))
mark("end")
'''


@pytest.fixture
def fake(wired, tmp_path, monkeypatch):
    script = tmp_path / "fake_agent.py"
    script.write_text(FAKE, encoding="utf-8")
    log = tmp_path / "fake.log"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("KIT_DIR", str(wired.kit_dir))
    from lib.common import PREFS, save_json

    def configure(routing, sleep="0.8", status="done"):
        monkeypatch.setenv("FAKE_SLEEP", sleep)
        monkeypatch.setenv("FAKE_STATUS", status)
        save_json(PREFS, {"runners": {"fake": {"argv": [sys.executable, str(script), "ok"]},
                                      "lim": {"argv": [sys.executable, str(script), "limit"]}},
                          "routing": {"agentic-heavy": routing}})
    wired.plan.sync()

    def entries():
        return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    return {"configure": configure, "entries": entries}


def run(wired, **kw):
    from lib.harness import scheduler
    out = []
    kw.setdefault("gates", [])
    done = scheduler.run_parallel(echo=out.append, poll=0.05, **kw)
    return done, out


def spans(entries):
    s = {}
    for e in entries:
        s.setdefault(e["unit"], {})[e["kind"]] = e["t"]
    return s


def status(wired, uid):
    return next(u for u in wired.plan.load()["units"] if u["id"] == uid)["status"]


def test_independent_units_overlap_in_their_own_worktrees_and_land_in_main(wired, fake):
    fake["configure"](["fake"])
    wired.plan.set_status("setup", "done")
    done, _ = run(wired, max_parallel=3, per_runner={"fake": 3}, max_units=3)
    assert done == 3
    s = spans(fake["entries"]())
    disc = [f"discovery:{r}" for r in ("api", "web", "worker")]
    assert max(s[u]["start"] for u in disc) < min(s[u]["end"] for u in disc)            # they ran at the same time
    roots = {e["root"] for e in fake["entries"]() if e["kind"] == "start"}
    assert all(Path(r).parent.name == ".cw" for r in roots) and len(roots) == 3
    assert all((wired.root / "docs" / "notes" / f"{u.replace(':', '-')}.md").exists() for u in disc)
    assert not (wired.ws / ".cw").exists()


def test_dependents_start_only_after_integration(wired, fake):
    fake["configure"](["fake"], sleep="0.3")
    wired.plan.set_status("setup", "done")
    run(wired, max_parallel=3, per_runner={"fake": 3}, max_units=4)
    cross = next(e for e in fake["entries"]() if e["unit"] == "discovery-cross" and e["kind"] == "start")
    assert Path(cross["root"]).resolve() == wired.root.resolve()                        # in place, in main
    assert cross["seen"] == ["discovery-api.md", "discovery-web.md", "discovery-worker.md"]


def test_a_usage_limit_pauses_that_runner_and_requeues_only_its_unit(wired, fake):
    fake["configure"](["lim", "fake"], sleep="0.3")
    wired.plan.set_status("setup", "done")
    done, out = run(wired, max_parallel=2, per_runner={"lim": 1, "fake": 1}, max_units=4)
    starts = [e for e in fake["entries"]() if e["kind"] == "start"]
    assert [e["mode"] for e in starts].count("limit") == 1
    limited_unit = next(e["unit"] for e in starts if e["mode"] == "limit")
    assert status(wired, limited_unit) == "done" and done >= 3
    assert any(e["unit"] == limited_unit and e["mode"] == "ok" for e in starts)          # retried on the other runner
    assert any("usage limit" in l for l in out)


def test_in_place_units_never_overlap(wired, fake):
    fake["configure"](["fake"], sleep="0.3")
    wired.plan.add("doc-fixes:a", "Fix A", type_="doc-fixes", deps=[])
    wired.plan.add("doc-fixes:b", "Fix B", type_="doc-fixes", deps=[])
    run(wired, max_parallel=3, per_runner={"fake": 3}, max_units=2)
    s = spans(fake["entries"]())
    a, b = s["doc-fixes:a"], s["doc-fixes:b"]
    assert a["end"] <= b["start"] or b["end"] <= a["start"]


def test_a_unit_that_ends_without_done_stops_new_work(wired, fake):
    fake["configure"](["fake"], sleep="0.2", status="doing")
    wired.plan.set_status("setup", "done")
    done, out = run(wired, max_parallel=1, per_runner={"fake": 1})
    assert done == 0 and len([e for e in fake["entries"]() if e["kind"] == "start"]) == 1
    assert any("ended without" in l for l in out)
    from lib.harness.worktrees import Worktrees
    assert Worktrees(wired.common.CTX).list()                       # its worktree is kept for the next attempt


def test_a_run_is_recorded(wired, fake):
    fake["configure"](["fake"], sleep="0.1")
    wired.plan.set_status("setup", "done")
    run(wired, max_parallel=3, per_runner={"fake": 3}, max_units=3)
    from lib.harness.events import EventLog
    log = sorted(wired.common.CTX.runs.glob("*/events.jsonl"))[-1]
    kinds = [e["type"] for e in EventLog(log).read()[0]]
    assert kinds[0] == "run.started" and kinds[-1] == "run.finished"
    assert kinds.count("unit.started") == 3 and kinds.count("merge.ok") == 3


def test_a_runner_with_no_slots_stops_instead_of_spinning(wired, fake):
    fake["configure"](["fake"])
    wired.plan.set_status("setup", "done")
    done, out = run(wired, max_parallel=2, per_runner={"fake": 0})
    assert done == 0 and any("no agent slot" in l for l in out)
