from __future__ import annotations

from datetime import datetime, timezone

import pytest


def card(uid="01jb7p0a", status="Ready", ordinal=1000, assignee=(), t=None):
    return {"uid": uid, "status": status, "ordinal": ordinal, "assignee": list(assignee), "t": dict(t or {})}


def test_dump_is_one_line_per_card_sorted(kit):
    from lib.kanban.state import dump_board, load_board
    cards = {
        "WI-10": card("aaaaaaaa", ordinal=3000),
        "WI-2": card("bbbbbbbb", "In Progress", 1000, ["ana"], {"status": "2026-10-20T09:00:00Z luis@x"}),
        "WI-3": card("12345678", ordinal=2000),
    }
    text = dump_board(cards)
    lines = text.splitlines()
    assert lines[:2] == ["version: 1", "cards:"]
    assert [ln.split(":")[0].strip() for ln in lines[2:]] == ["WI-2", "WI-3", "WI-10"]
    assert text.endswith("\n") and len(lines) == 5
    assert lines[2].startswith("  WI-2: {uid: bbbbbbbb, status: In Progress, ordinal: 1000, assignee: [ana], t: {")
    assert load_board(text) == cards


def test_load_rejects_garbage(kit):
    from lib.kanban.state import load_board
    with pytest.raises(ValueError):
        load_board("cards: [1")
    with pytest.raises(ValueError):
        load_board("version: 2\ncards: {}\n")


def test_next_id(kit):
    from lib.kanban.state import next_id
    assert next_id(["WI-1", "WI-9", "WI-3~ab"]) == "WI-10"
    assert next_id([]) == "WI-1"


def test_id_key_is_natural_and_temp_keys_follow(kit):
    from lib.kanban.state import id_key
    ids = ["WI-10", "WI-42~zz", "WI-2", "WI-42"]
    assert sorted(ids, key=id_key) == ["WI-2", "WI-10", "WI-42", "WI-42~zz"]


def test_place_at_end_and_start(kit):
    from lib.kanban.state import place
    col = [("a", 1000), ("b", 2000)]
    assert place(col) == {"*": 3000}
    assert place(col, before="a") == {"*": 500}
    assert place(col, after="a") == {"*": 1500}
    assert place([]) == {"*": 1000}


def test_place_rebalances_when_no_room(kit):
    from lib.kanban.state import place
    out = place([("a", 1000), ("b", 1001)], after="a")
    assert out == {"*": 2000, "b": 3000}
    out = place([("a", 1), ("b", 5)], before="a")
    assert out == {"*": 1000, "a": 2000, "b": 3000}


def test_stamp_format(kit):
    from lib.kanban.state import stamp, stamp_time
    c = card()
    now = datetime(2026, 10, 24, 10, 12, tzinfo=timezone.utc)
    stamp(c, "status", "ana@x", now)
    assert c["t"]["status"] == "2026-10-24T10:12:00Z ana@x"
    assert stamp_time(c["t"]["status"]) == now


def test_uid_shape(kit):
    import re
    from lib.kanban.state import new_uid
    assert re.fullmatch(r"[0-9a-hjkmnp-tv-z]{8}", new_uid())


def test_values_that_yaml_would_misread_survive(kit):
    from lib.kanban.state import dump_board, load_board
    cards = {"WI-1": card("12345678", assignee=["a b", "x:y", "null"], t={"status": "2026-10-24T10:12:00Z a@x"})}
    assert load_board(dump_board(cards)) == cards
