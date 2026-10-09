"""Run event log: one JSON object per line, safe under concurrent writers, readable incrementally by offset."""
from __future__ import annotations

import json, threading

import pytest


@pytest.fixture
def log(kit):
    from lib.harness.events import EventLog
    return EventLog(kit.root / ".camarones" / ".cache" / "runs" / "r-1" / "events.jsonl")


def test_emit_writes_one_versioned_line(log):
    ev = log.emit("unit.started", run="r-1", unit="discovery:api", runner="claude")
    line = log.path.read_text(encoding="utf-8").splitlines()[0]
    assert json.loads(line) == ev
    assert ev["v"] == 1 and ev["type"] == "unit.started" and ev["unit"] == "discovery:api" and ev["ts"].endswith("Z")


def test_concurrent_writers_never_corrupt_lines(log):
    def burst(n):
        for i in range(500):
            log.emit("log", unit=f"u{n}", data={"i": i, "text": "x" * 200})
    threads = [threading.Thread(target=burst, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    events, _ = log.read()
    assert len(events) == 2000
    assert {e["unit"] for e in events} == {"u0", "u1", "u2", "u3"}


def test_read_resumes_from_the_returned_offset(log):
    log.emit("a")
    log.emit("b")
    first, offset = log.read()
    log.emit("c")
    rest, end = log.read(offset)
    assert [e["type"] for e in first] == ["a", "b"] and [e["type"] for e in rest] == ["c"]
    assert log.read(end) == ([], end)


def test_a_partial_last_line_waits_for_its_newline(log):
    log.emit("a")
    with log.path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write('{"v": 1, "type": "half')
    events, offset = log.read()
    assert [e["type"] for e in events] == ["a"]
    with log.path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write('"}\n')
    more, _ = log.read(offset)
    assert [e["type"] for e in more] == ["half"]


def test_reading_a_missing_log_is_empty(kit):
    from lib.harness.events import EventLog
    assert EventLog(kit.root / "nope.jsonl").read() == ([], 0)
