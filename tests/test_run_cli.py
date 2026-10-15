"""Commands for the harness (R15): `run` (parallel scheduler), `runs` (what past runs did and cost) and
`pipeline show | validate`. --json output is for scripts and CI: its keys are pinned here."""
from __future__ import annotations

import json, os, subprocess, sys

import pytest
import yaml

from test_scheduler import FAKE


def cli(kit, *args, env=None):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root), **(env or {})}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8")


@pytest.fixture
def fake_agent(wired, tmp_path):
    script = tmp_path / "fake_agent.py"
    script.write_text(FAKE, encoding="utf-8")
    from lib.common import PREFS, save_json
    save_json(PREFS, {"runners": {"fake": {"argv": [sys.executable, str(script), "ok"]}},
                      "routing": {"agentic-heavy": ["fake"]}})
    wired.plan.sync()
    wired.plan.set_status("setup", "done")
    return {"FAKE_LOG": str(tmp_path / "fake.log"), "KIT_DIR": str(wired.kit_dir), "FAKE_SLEEP": "0.2"}


def test_run_documents_units_in_parallel_and_runs_reports_it(wired, fake_agent):
    r = cli(wired, "run", "--parallel", "3", "--per-runner", "fake=3", "--max-units", "3", env=fake_agent)
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("merged into") == 3
    rows = json.loads(cli(wired, "runs", "--json").stdout)
    assert len(rows) == 1
    run = rows[0]
    assert set(run) == {"run", "started", "finished", "interrupted", "seconds", "units", "done", "limited", "failed",
                        "tokens_in", "tokens_out", "cost_usd"}
    assert run["units"] == 3 and run["done"] == 3 and run["finished"] and not run["interrupted"]
    detail = json.loads(cli(wired, "runs", run["run"], "--json").stdout)
    assert set(detail["units"][0]) == {"unit", "runner", "isolation", "outcome", "status", "seconds", "merge",
                                       "tokens_in", "tokens_out", "cost_usd"}
    assert {u["merge"] for u in detail["units"]} == {"merged"}
    text = cli(wired, "runs").stdout
    assert run["run"] in text and "3/3" in text
    one = cli(wired, "runs", run["run"]).stdout.splitlines()
    assert "3/3 done" in one[0] and "{" not in one[0] and len(one) == 4          # header + one line per unit


def test_runs_sums_tokens_and_cost(kit):
    from lib.harness import runs
    from lib.harness.events import EventLog
    log = EventLog(kit.common.CTX.runs / "r-1" / "events.jsonl")
    log.emit("run.started", run="r-1")
    log.emit("unit.started", run="r-1", unit="a", runner="claude", isolation="none")
    log.emit("usage", run="r-1", unit="a", runner="claude", **{"in": 100, "out": 10, "cost_usd": 0.25})
    log.emit("usage", run="r-1", unit="a", runner="claude", **{"in": 50, "out": 5, "cost_usd": 0.05})
    log.emit("unit.finished", run="r-1", unit="a", runner="claude", outcome="ok", status="done", seconds=3.0)
    log.emit("unit.started", run="r-1", unit="b", runner="codex", isolation="worktree")
    log.emit("unit.finished", run="r-1", unit="b", runner="codex", outcome="limited", status="todo", seconds=1.0)
    s = runs.summary("r-1")
    assert (s["tokens_in"], s["tokens_out"], round(s["cost_usd"], 2)) == (150, 15, 0.30)
    assert (s["units"], s["done"], s["limited"], s["finished"]) == (2, 1, 1, False)
    a = next(u for u in runs.detail("r-1")["units"] if u["unit"] == "a")
    assert (a["tokens_in"], a["merge"]) == (150, None)


def test_pipeline_show_lists_the_units_with_how_they_run(wired):
    r = cli(wired, "pipeline", "show", "--json")
    data = json.loads(r.stdout)
    assert set(data) == {"pipeline", "override", "problems", "units"}
    assert data["pipeline"] == "full" and data["override"] is False and data["problems"] == []
    disc = next(u for u in data["units"] if u["id"] == "discovery:api")
    assert disc == {"id": "discovery:api", "type": "discovery", "needs": ["setup"], "tier": "agentic-heavy",
                    "isolation": "worktree", "runner": None, "disabled": False}
    assert "discovery:api" in cli(wired, "pipeline", "show").stdout


def test_pipeline_validate_fails_on_a_broken_override(wired):
    assert cli(wired, "pipeline", "validate").returncode == 0
    (wired.root / ".camarones" / "pipeline.yaml").write_text(
        yaml.safe_dump({"patch": [{"op": "disable", "node": "nope"}]}), encoding="utf-8")
    r = cli(wired, "pipeline", "validate")
    assert r.returncode == 1 and "patch[0].node: unknown node 'nope'" in r.stdout


def test_per_runner_flag_is_parsed(kit):
    from lib.harness import scheduler
    assert scheduler.parse_slots("claude=2, codex=1") == {"claude": 2, "codex": 1}
    with pytest.raises(ValueError):
        scheduler.parse_slots("claude")
