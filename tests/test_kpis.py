"""KPIs (R16): is Camarón working? Cost and speed from the run logs, coverage and quality from the docs, trust from
confirmations, usefulness from usage. Runs are rolled up per person and machine in docs/.work/kpis/, committed like
the usage stats, so the team's runs add up; `--compare` puts two runs side by side."""
from __future__ import annotations

import json, os, subprocess, sys

import pytest


def make_run(kit, run_id, units, wall, ts="2026-10-15T10:00:00.000Z"):
    """units: (unit, runner, seconds, outcome, tokens_in, tokens_out, cost) — events spread over `wall` seconds."""
    from lib.harness.events import EventLog
    log = EventLog(kit.common.CTX.runs / run_id / "events.jsonl")
    day, clock = ts[:10], 36000
    stamp = lambda s: f"{day}T{(clock + s) // 3600:02d}:{(clock + s) % 3600 // 60:02d}:{(clock + s) % 60:02d}.000Z"  # noqa: E731
    lines = [{"type": "run.started", "ts": stamp(0)}]
    for u, runner, secs, outcome, tin, tout, cost in units:
        lines += [{"type": "unit.started", "unit": u, "runner": runner, "isolation": "worktree", "ts": stamp(0)},
                  {"type": "usage", "unit": u, "runner": runner, "in": tin, "out": tout, "cost_usd": cost, "ts": stamp(1)},
                  {"type": "unit.finished", "unit": u, "runner": runner, "outcome": outcome,
                   "status": "done" if outcome == "ok" else "todo", "seconds": secs, "ts": stamp(secs)}]
    done = sum(1 for x in units if x[3] == "ok")
    lines.append({"type": "run.finished", "done": done, "ts": stamp(wall)})
    log.path.parent.mkdir(parents=True, exist_ok=True)
    log.path.write_text("".join(json.dumps({"v": 1, "run": run_id, **l}) + "\n" for l in lines), encoding="utf-8")


@pytest.fixture
def kpis(kit):
    from lib.harness import kpis
    return kpis


def test_a_run_gives_cost_speed_and_parallelism(kit, kpis):
    make_run(kit, "r-20261015-100000-1", [("discovery:api", "claude", 60, "ok", 1000, 100, 0.40),
                                          ("discovery:web", "claude", 60, "ok", 3000, 300, 0.60)], wall=60)
    m = kpis.run_metrics("r-20261015-100000-1")
    assert (m["done"], m["tokens_in"], round(m["cost_usd"], 2)) == (2, 4000, 1.00)
    assert m["parallelism"] == 2.0 and m["cost_per_unit"] == 0.5 and m["seconds_per_unit"] == 30.0


def test_compare_shows_what_changed_between_two_runs(kit, kpis):
    make_run(kit, "r-20261015-100000-1", [("a", "claude", 60, "ok", 1000, 100, 1.0), ("b", "claude", 60, "ok", 1000, 100, 1.0)], wall=120)
    make_run(kit, "r-20261016-100000-1", [("a", "claude", 60, "ok", 500, 50, 0.4), ("b", "codex", 60, "ok", 500, 50, 0.4)], wall=60,
             ts="2026-10-16T10:00:00.000Z")
    c = kpis.compare("r-20261015-100000-1", "r-20261016-100000-1")
    assert c["delta"]["cost_usd"] == pytest.approx(-1.2) and c["delta"]["seconds"] == -60
    assert c["delta"]["parallelism"] == 1.0 and c["a"]["run"] == "r-20261015-100000-1"


def test_runs_are_rolled_up_per_machine_and_month(kit, kpis):
    make_run(kit, "r-20261015-100000-1", [("a", "claude", 60, "ok", 1000, 100, 0.5)], wall=60)
    make_run(kit, "r-20261016-100000-1", [("b", "claude", 30, "limited", 10, 0, 0.0)], wall=30, ts="2026-10-16T10:00:00.000Z")
    for r in ("r-20261015-100000-1", "r-20261016-100000-1", "r-20261015-100000-1"):     # recording twice is harmless
        kpis.record_run(r)
    files = list((kit.root / "docs" / ".work" / "kpis").glob("*.json"))
    assert len(files) == 1 and len(json.loads(files[0].read_text(encoding="utf-8"))["runs"]) == 2
    month = kpis.report(today=kpis.date(2026, 10, 20))["runs"][0]
    assert (month["month"], month["runs"], month["units"], month["done"], month["limited"]) == ("2026-10", 2, 2, 1, 1)
    assert month["cost_usd"] == 0.5


def test_a_teammates_rollup_counts_too(kit, kpis):
    d = kit.root / "docs" / ".work" / "kpis"
    d.mkdir(parents=True)
    (d / "someone-else.json").write_text(json.dumps({"v": 1, "runs": {"r-20261001-090000-7": {
        "run": "r-20261001-090000-7", "started": "2026-10-01T09:00:00.000Z", "units": 4, "done": 4, "limited": 0,
        "failed": 0, "seconds": 600.0, "tokens_in": 10, "tokens_out": 1, "cost_usd": 2.0, "parallelism": 2.0}}}),
        encoding="utf-8")
    month = kpis.report(today=kpis.date(2026, 10, 20))["runs"][0]
    assert month["runs"] == 1 and month["cost_usd"] == 2.0


def test_recording_respects_the_stats_switch(kit, kpis):
    kit.usage.set_enabled(False)
    make_run(kit, "r-20261015-100000-1", [("a", "claude", 60, "ok", 1, 1, 0.1)], wall=60)
    kpis.record_run("r-20261015-100000-1")
    assert not (kit.root / "docs" / ".work" / "kpis").exists()


def test_coverage_counts_briefs_flows_and_c4_fragments(kit, kpis):
    docs = kit.root / "docs"
    (docs / "repos" / "api").mkdir(parents=True)
    (docs / "repos" / "api" / "brief.md").write_text("---\ntitle: api\n---\n# api\n", encoding="utf-8")
    (docs / "flows").mkdir()
    for n in ("checkout", "index"):
        (docs / "flows" / f"{n}.md").write_text(f"---\ntitle: {n}\n---\n# {n}\n", encoding="utf-8")
    (docs / "architecture" / "flows").mkdir(parents=True)
    (docs / "architecture" / "flows" / "checkout.c4").write_text("views {}\n", encoding="utf-8")
    cov = kpis.coverage(run_check=False)
    assert (cov["repos"], cov["repos_with_brief"], cov["flows"], cov["c4_files"]) == (3, 1, 1, 1)
    assert cov["check_errors"] is None


def test_the_kpis_command(kit):
    make_run(kit, "r-20261015-100000-1", [("a", "claude", 60, "ok", 1000, 100, 0.5)], wall=60)
    make_run(kit, "r-20261016-100000-1", [("a", "claude", 30, "ok", 500, 50, 0.2)], wall=30, ts="2026-10-16T10:00:00.000Z")
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    cli = lambda *a: subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "kpis", *a], env=env,   # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    data = json.loads(cli("--json", "--no-check").stdout)
    assert set(data) == {"runs", "coverage", "trust", "usefulness"}
    text = cli("--no-check").stdout
    assert "Cost and speed" in text and "Coverage" in text and "Trust" in text
    cmp = json.loads(cli("--compare", "r-20261015-100000-1", "r-20261016-100000-1", "--json").stdout)
    assert cmp["delta"]["seconds"] == -30
