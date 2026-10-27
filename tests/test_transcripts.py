"""Claude Code transcripts of interactive unit sessions → tokens per model and active time, for the plan bill. One
message is written as several lines (one per content block) with the same usage: it counts once."""
from __future__ import annotations

import json

import pytest

T0 = "2026-10-27T10:00:00.000Z"


@pytest.fixture
def transcripts(kit):
    from lib.harness import transcripts
    return transcripts


def write(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8", newline="\n")
    return path


def a(mid, model, ts, **usage):
    return {"type": "assistant", "timestamp": ts, "isSidechain": False,
            "message": {"id": mid, "model": model, "usage": {"input_tokens": 0, "output_tokens": 0, **usage}}}


def test_one_message_id_counts_once(tmp_path, transcripts):
    f = write(tmp_path / "s.jsonl", [a("m1", "claude-opus-5-5", T0, input_tokens=10, output_tokens=5)] * 3)
    m = transcripts.read(f)["models"]["claude-opus-5-5"]
    assert (m["in"], m["out"]) == (10, 5)


def test_cache_writes_split_by_ttl_with_a_fallback(tmp_path, transcripts):
    f = write(tmp_path / "s.jsonl", [
        a("m1", "x", T0, cache_creation_input_tokens=30, cache_creation={"ephemeral_5m_input_tokens": 10,
                                                                         "ephemeral_1h_input_tokens": 20}),
        a("m2", "x", T0, cache_creation_input_tokens=7, cache_read_input_tokens=3)])
    m = transcripts.read(f)["models"]["x"]
    assert (m["cache_write_5m"], m["cache_write_1h"], m["cache_read"]) == (17, 20, 3)


def test_subagents_add_tokens_not_time(tmp_path, transcripts):
    f = write(tmp_path / "s.jsonl", [a("m1", "x", "2026-10-27T10:00:00Z", output_tokens=1),
                                     a("m2", "x", "2026-10-27T10:01:00Z", output_tokens=1)])
    write(tmp_path / "s" / "subagents" / "agent-1.jsonl", [a("m9", "y", "2026-10-27T12:00:00Z", output_tokens=4)])
    r = transcripts.read(f)
    assert r["models"]["y"]["out"] == 4 and r["active_seconds"] == 60 and r["last"] == "2026-10-27T10:01:00Z"
    assert r["first"] == "2026-10-27T10:00:00Z"
    assert r["bytes"] == transcripts.size(f) > f.stat().st_size


def test_idle_gaps_are_capped(tmp_path, transcripts):
    f = write(tmp_path / "s.jsonl", [a("m1", "x", "2026-10-27T10:00:00Z"), a("m2", "x", "2026-10-27T22:00:00Z")])
    assert transcripts.read(f)["active_seconds"] == transcripts.IDLE


def test_damaged_and_half_written_lines_are_skipped(tmp_path, transcripts):
    f = write(tmp_path / "s.jsonl", [a("m1", "x", T0, output_tokens=2)])
    with f.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("{not json\n" + json.dumps(a("m2", "x", T0, output_tokens=50))[:-5])   # no newline: being written
    assert transcripts.read(f)["models"]["x"]["out"] == 2


def test_missing_transcript_is_none(tmp_path, transcripts):
    assert transcripts.read(tmp_path / "nope.jsonl") is None and transcripts.size(tmp_path / "nope.jsonl") == 0
