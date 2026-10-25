"""Doc links by x-id (spec §5): ids, the textual frontmatter insert, section hashes and link states."""
from __future__ import annotations

import re

import pytest

PAYMENTS = ("---\ntitle: Payments\n# kept as written\ndescription: How payments flow\n---\n"
            "# Payments\n\nIntro.\n\n## Retries\nThree tries.\n\n## Refunds\nWithin 30 days.\n")


def page(wired, logical, text):
    f = wired.root / "docs" / logical
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(text.encode("utf-8"))
    return f


def raw(f):
    return f.read_bytes().decode("utf-8")


def test_xid_prefix_by_folder(wired):
    from lib.kanban import xid
    page(wired, "flows/payments.md", PAYMENTS)
    page(wired, "decisions/0004-retries.md", "---\ntitle: Retries\n---\n# Retries\n")
    a = xid.ensure_xid("flows/payments.md")
    assert re.fullmatch(r"FLOW-[0-9a-hjkmnp-tv-z]{4}", a)
    assert xid.ensure_xid("decisions/0004-retries.md") == "DEC-0004"
    assert xid.ensure_xid("overview.md").startswith("DOC-")
    assert xid.ensure_xid("flows/payments.md") == a
    assert xid.index()[a] == "flows/payments.md"
    assert xid.index()["DEC-0004"] == "decisions/0004-retries.md"


def test_confirmed_page_stays_confirmed(wired):
    from lib import docs
    from lib.kanban import xid
    f = page(wired, "flows/payments.md", PAYMENTS)
    docs.confirm(["docs/flows/payments.md"], "ana")
    # confirm re-dumps the frontmatter (and, on Windows, writes CRLF); a person then adds a comment line
    lines = raw(f).splitlines()
    lines.insert(lines.index("title: Payments") + 1, "# human note")
    f.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    before = raw(f)
    assert "# human note" in before
    new = xid.ensure_xid("flows/payments.md")
    fm, body, _ = docs.parse_fm(raw(f))
    assert docs.trust_of(fm, docs.body_sha(body)) == "confirmed"
    assert fm["x-id"] == new
    kept = [l for l in before.split("---\n")[1].splitlines()]
    assert [l for l in raw(f).split("---\n")[1].splitlines() if l != f"x-id: {new}"] == kept
    assert docs.parse_fm(before)[1] == body


def test_page_without_frontmatter_gets_one(wired):
    from lib.kanban import xid
    body = "# Plain\n\n## A\nx\r\n"
    f = page(wired, "flows/plain.md", body)
    new = xid.ensure_xid("flows/plain.md")
    assert raw(f) == f"---\nx-id: {new}\n---\n{body}"


def test_crlf_frontmatter_keeps_its_line_endings(wired):
    from lib.kanban import xid
    f = page(wired, "flows/win.md", "---\r\ntitle: Win\r\n---\r\n# Win\r\n")
    new = xid.ensure_xid("flows/win.md")
    assert raw(f) == f"---\r\ntitle: Win\r\nx-id: {new}\r\n---\r\n# Win\r\n"


def test_link_format_roundtrip():
    from lib.kanban import xid
    s = xid.format_link("FLOW-k3f9", "retries", "1a2b3c4d")
    assert s == "FLOW-k3f9#retries@1a2b3c4d"
    assert xid.parse_link(s) == {"xid": "FLOW-k3f9", "section": "retries", "hash": "1a2b3c4d"}
    assert xid.parse_link("DEC-0004") == {"xid": "DEC-0004", "section": None, "hash": None}
    assert xid.format_link("DEC-0004", None, None) == "DEC-0004"


def test_resolve_ref_and_changed_since_linked(wired):
    from lib.kanban import xid
    f = page(wired, "flows/payments.md", PAYMENTS)
    link = xid.resolve_ref("flows/payments.md#Retries")
    assert re.fullmatch(r"FLOW-[0-9a-hjkmnp-tv-z]{4}#retries@[0-9a-f]{8}", link)
    assert xid.resolve_ref(link.split("#")[0] + "#retries") == link        # by x-id, same hash
    rows = {"flows/payments.md": {"title": "Payments", "trust": "draft", "fresh": "unverified"}}
    st = xid.link_state(link, rows)
    assert st["changed"] is False and st["missing"] is False
    assert st["path"] == "flows/payments.md" and st["title"] == "Payments" and st["trust"] == "draft"
    f.write_bytes(raw(f).replace("Within 30 days.", "Within 14 days.").encode("utf-8"))
    assert xid.link_state(link, rows)["changed"] is False                  # another section
    f.write_bytes(raw(f).replace("Three tries.", "Five tries.").encode("utf-8"))
    assert xid.link_state(link, rows)["changed"] is True


def test_whole_page_link_and_vanished_section(wired):
    from lib.kanban import xid
    f = page(wired, "flows/payments.md", PAYMENTS)
    whole = xid.resolve_ref("flows/payments.md")
    assert re.fullmatch(r"FLOW-[0-9a-hjkmnp-tv-z]{4}@[0-9a-f]{8}", whole)
    sec = xid.resolve_ref("flows/payments.md#refunds")
    f.write_bytes(raw(f).replace("## Refunds", "## Returns").encode("utf-8"))
    assert xid.link_state(sec, {})["changed"] is True
    assert xid.link_state(whole, {})["changed"] is True


def test_unknown_ref_raises(wired):
    from lib.kanban import xid
    from lib.kanban.ops import BoardError
    page(wired, "flows/payments.md", PAYMENTS)
    for ref in ("flows/nope.md", "FLOW-zzzz", "flows/payments.md#nothing"):
        with pytest.raises(BoardError):
            xid.resolve_ref(ref)


def test_missing_page_state(wired):
    from lib.kanban import TASKS, ops, repair, xid
    from lib.kanban.items import Item, file_name, serialize_item
    st = xid.link_state("FLOW-zzzz#a@1234abcd", {})
    assert st["missing"] is True and st["path"] is None
    fm = {"id": "WI-1", "title": "Linky", "status": "Backlog", "assignee": [], "created_date": "2026-10-01 10:00",
          "type": "task", "ordinal": 1000, "x-uid": "link0001", "documentation": "FLOW-zzzz#a@1234abcd"}   # a lone scalar
    item = Item(fm, "## Description\nx\n", TASKS / file_name("WI-1", "Linky"))
    item.path.write_text(serialize_item(item), encoding="utf-8", newline="\n")
    ops.save_board({"WI-1": {"uid": "link0001", "status": "Backlog", "ordinal": 1000, "assignee": [], "t": {}}})
    out = repair.repair(log=lambda _: None)
    assert any("FLOW-zzzz" in w for w in out["warnings"])


@pytest.fixture
def board(wired):
    from lib.kanban import ops
    ops.init(log=lambda _: None)
    return ops


def test_add_and_link_resolve_refs(board, wired):
    page(wired, "flows/payments.md", PAYMENTS)
    row = board.add("story", "Pay twice", docs=["flows/payments.md#retries"])
    assert re.fullmatch(r"FLOW-[0-9a-hjkmnp-tv-z]{4}#retries@[0-9a-f]{8}", row["docs"][0])
    base = row["docs"][0].split("#")[0]
    board.add("task", "Other")
    out = board.link("WI-2", f"{base}#refunds")
    assert out["docs"][0].startswith(f"{base}#refunds@")
    again = board.link("WI-2", f"{base}#refunds")                          # no duplicate, hash refreshed
    assert len(again["docs"]) == 1
    both = board.link("wi-2", "flows/payments.md#retries")
    assert len(both["docs"]) == 2
    with pytest.raises(board.BoardError):
        board.link("WI-2", "flows/nope.md")
    with pytest.raises(board.BoardError):
        board.link("WI-99", "flows/payments.md")
    with pytest.raises(board.BoardError):
        board.add("task", "Bad link", docs=["flows/nope.md"])
    assert [c["id"] for c in board.list_items()["cards"]] == ["WI-1", "WI-2"]    # the failed add left nothing


def test_list_filter_docs_state(board, wired, monkeypatch):
    from lib import docs
    from lib.harness import freshness
    page(wired, "flows/payments.md", PAYMENTS)
    page(wired, "flows/refunds.md", "---\ntitle: Refunds\n---\n# Refunds\n")
    docs.confirm(["docs/flows/refunds.md"], "ana")
    board.add("story", "Draft link", docs=["flows/payments.md#retries"])
    board.add("story", "Confirmed link", docs=["flows/refunds.md"])
    board.add("story", "No link")
    assert [c["id"] for c in board.list_items(docs="unconfirmed")["cards"]] == ["WI-1"]
    freshness.stamp_all()                       # a project whose fingerprints exist: reading them writes nothing
    real = freshness.states
    monkeypatch.setattr(freshness, "states",
                        lambda: {**real(), "flows/refunds.md": {"state": "suspect", "changed": [], "missing": []}})
    assert [c["id"] for c in board.list_items(docs="suspect")["cards"]] == ["WI-2"]
    xid_ = board.list_items(docs="unconfirmed")["cards"][0]["docs"][0].split("#")[0]
    assert [c["id"] for c in board.list_items(docs=xid_)["cards"]] == ["WI-1"]
    shown = board.show("WI-2")["links"][0]
    assert shown["trust"] == "confirmed" and shown["fresh"] == "suspect" and shown["title"] == "Refunds"


# --- fix round 1 ---

def test_wiki_pages_take_the_prefix_of_their_folder(wired):
    from lib.kanban import xid
    wiki = wired.root / "wikis" / "api"
    (wiki / "flows").mkdir(parents=True)
    (wiki / "flows" / "x.md").write_text("---\ntitle: X\n---\n# X\n", encoding="utf-8")
    (wiki / "domain").mkdir()
    (wiki / "domain" / "y.md").write_text("---\ntitle: Y\n---\n# Y\n", encoding="utf-8")
    (wiki / "intro.md").write_text("---\ntitle: I\n---\n# I\n", encoding="utf-8")
    assert xid.ensure_xid("repos/api/flows/x.md").startswith("FLOW-")
    assert xid.ensure_xid("repos/api/domain/y.md").startswith("DOM-")
    assert xid.ensure_xid("repos/api/intro.md").startswith("DOC-")


def test_same_decision_number_in_two_places_gets_two_ids(wired):
    from lib.kanban import xid
    page(wired, "decisions/0004-y.md", "---\ntitle: Y\n---\n# Y\n")
    wiki = wired.root / "wikis" / "api" / "decisions"
    wiki.mkdir(parents=True)
    (wiki / "0004-x.md").write_text("---\ntitle: X\n---\n# X\n", encoding="utf-8")
    a = xid.ensure_xid("decisions/0004-y.md")
    b = xid.ensure_xid("repos/api/decisions/0004-x.md")
    assert a == "DEC-0004" and b != a
    assert re.fullmatch(r"DEC-[0-9a-hjkmnp-tv-z]{4}", b)
    assert xid.index()[a] == "decisions/0004-y.md" and xid.index()[b] == "repos/api/decisions/0004-x.md"
    assert xid.ensure_xid("repos/api/decisions/0004-x.md") == b


def test_bom_page_keeps_its_bom_and_frontmatter(wired):
    from lib.kanban import xid
    original = "﻿---\ntitle: Bom\n---\n# Bom\n\n## A\nx\n"
    f = page(wired, "flows/bom.md", original)
    new = xid.ensure_xid("flows/bom.md")
    assert raw(f) == original.replace("title: Bom\n", f"title: Bom\nx-id: {new}\n")
    assert xid.index()[new] == "flows/bom.md" and xid.ensure_xid("flows/bom.md") == new


def write_item(links):
    from lib.kanban import TASKS, ops
    from lib.kanban.items import Item, file_name, serialize_item
    fm = {"id": "WI-1", "title": "Linky", "status": "Backlog", "assignee": [], "created_date": "2026-10-01 10:00",
          "type": "task", "ordinal": 1000, "x-uid": "link0001", "documentation": links}
    item = Item(fm, "## Description\nx\n", TASKS / file_name("WI-1", "Linky"))
    item.path.write_text(serialize_item(item), encoding="utf-8", newline="\n")
    ops.save_board({"WI-1": {"uid": "link0001", "status": "Backlog", "ordinal": 1000, "assignee": [], "t": {}}})


def test_malformed_link_is_missing_not_a_crash(board, wired):
    from lib.kanban import repair, xid
    st = xid.link_state("", {})
    assert st["missing"] is True and st["link"] == ""
    write_item(["", "###", "FLOW-zzzz"])
    shown = board.show("WI-1")
    assert [l["link"] for l in shown["links"]] == ["", "###", "FLOW-zzzz"]
    assert all(l["missing"] for l in shown["links"])
    assert board.list_items(docs="missing")["cards"][0]["id"] == "WI-1"
    out = repair.repair(log=lambda _: None)
    assert any("WI-1" in w and "link" in w for w in out["warnings"])


def test_scalar_reference_fields_are_one_entry(board, wired):
    page(wired, "flows/payments.md", "---\ntitle: P\nx-id: FLOW-k3f9\n---\n# P\n")
    write_item("FLOW-k3f9")
    assert board.list_items()["cards"][0]["docs"] == ["FLOW-k3f9"]
    assert [l["link"] for l in board.show("WI-1")["links"]] == ["FLOW-k3f9"]
    assert [c["id"] for c in board.list_items(docs="FLOW-k3f9")["cards"]] == ["WI-1"]
    # a hand-written scalar `subtasks` keeps its entry when a child is added under it
    from lib.kanban import TASKS
    f = next(TASKS.glob("wi-1 - *.md"))
    f.write_text(f.read_text(encoding="utf-8").replace("type: task", "type: epic\nsubtasks: WI-7"), encoding="utf-8")
    board.add("task", "Child", epic="WI-1")
    from lib.kanban.items import parse_item
    parent = parse_item(next(TASKS.glob("wi-1 - *.md")).read_text(encoding="utf-8"))
    assert parent.fm["subtasks"] == ["WI-7", "WI-2"]


def snapshot_files(wired):
    import subprocess
    from lib import docs
    from lib.harness import freshness
    status = subprocess.run(["git", "status", "--porcelain", "--ignored"], cwd=wired.root, capture_output=True,
                            text=True, encoding="utf-8").stdout
    one = lambda p: p.read_bytes() if p.exists() else None   # noqa: E731
    return status, one(docs.STATUS_FILE), one(freshness.FILE)


def test_reads_do_not_write_tracked_files(board, wired):
    page(wired, "flows/payments.md", PAYMENTS)
    board.add("story", "Linked", docs=["flows/payments.md#retries"])
    board.add("story", "Plain")
    before = snapshot_files(wired)
    assert board.show("WI-2")["links"] == []
    shown = board.show("WI-1")
    assert shown["links"][0]["trust"] == "draft" and shown["links"][0]["title"] == "Payments"
    assert [c["id"] for c in board.list_items(docs="unconfirmed")["cards"]] == ["WI-1"]
    assert snapshot_files(wired) == before
