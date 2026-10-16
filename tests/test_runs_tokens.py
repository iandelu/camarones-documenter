"""Token accounting includes the cache: agents such as Claude report input_tokens without cached context."""
from __future__ import annotations


def test_runs_count_cached_tokens(kit):
    from lib.harness import runs
    from lib.harness.events import EventLog
    log = EventLog(kit.common.CTX.runs / "r-1" / "events.jsonl")
    log.emit("unit.started", run="r-1", unit="a", runner="claude", isolation="none")
    log.emit("usage", run="r-1", unit="a", runner="claude", **{"in": 8, "out": 100, "cache_read": 5000, "cache_write": 1000})
    log.emit("unit.finished", run="r-1", unit="a", runner="claude", outcome="ok", status="done", seconds=1.0)
    assert runs.summary("r-1")["tokens_cache"] == 6000
    assert runs.detail("r-1")["units"][0]["tokens_cache"] == 6000


def test_eval_asks_add_up_cached_tokens(kit, monkeypatch):
    import json, subprocess
    from lib.harness import evals
    from lib.harness.ports import RunRequest
    line = json.dumps({"type": "result", "result": '{"answer": "a", "cited": []}', "total_cost_usd": 0.1,
                       "usage": {"input_tokens": 8, "output_tokens": 5, "cache_read_input_tokens": 700,
                                 "cache_creation_input_tokens": 300}})
    monkeypatch.setattr(evals.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, line + "\n", ""))
    got = evals._ask("claude", RunRequest(prompt="p", cwd=kit.ws, allow_tools=("Read",), stream=True))
    assert (got["tokens_in"], got["tokens_cache"], got["tokens_out"]) == (8, 1000, 5)
