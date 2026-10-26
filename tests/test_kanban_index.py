"""The board's derived SQLite index: footprints, code-map edges and doc citations, rebuilt when the files change."""
from __future__ import annotations

import multiprocessing
import os
import shutil
import sqlite3
import subprocess

import pytest

from fixtures import index_worker
from test_codemap import JAVA, write_graph

ORDER = "api:api-core/src/main/java/demo/shop/orders/OrderService.java"
PAY = "api:api-core/src/main/java/demo/shop/payments/PaymentClient.java"
PAGE = "cam-docs:docs/orders.md"
DTO = "api:api-core/src/main/java/demo/shop/payments/dto/PaymentDto.java"


@pytest.fixture
def world(kit):
    """A board with two cards on the code map's files and one doc page citing OrderService."""
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)
    from lib.kanban import ops
    ops.init(log=lambda _: None)
    write_graph(kit)
    (kit.root / "docs").mkdir(exist_ok=True)
    (kit.root / "docs" / "orders.md").write_text(
        f"---\ntitle: Orders\nx-sources:\n  - api-core/x\n  - api:{JAVA}orders/OrderService.java#place\n---\n# Orders\n",
        encoding="utf-8")
    one = ops.add("task", "Place order", repos=["api"], touches=[ORDER])
    two = ops.add("task", "Pay", repos=["api"], touches=[PAY], dependencies=[one["id"]], priority="P1")
    from lib.kanban import index
    return kit, ops, index, one["id"], two["id"]


def edit(ops, item_id, **fm):
    item = ops.load_state()[1][item_id]
    item.fm.update(fm)
    ops.save_item(item)


def counting(monkeypatch, index):
    calls = []
    real = index._build

    def build(*a, **k):
        calls.append(1)
        return real(*a, **k)
    monkeypatch.setattr(index, "_build", build)
    return calls


def test_builds_and_answers(world):
    kit, ops, index, one, two = world
    conn = index.connect()
    try:
        nodes = {n["id"]: n for n in index.nodes(conn)}
        assert [n["id"] for n in index.nodes(conn)] == [one, two]
        assert nodes[one] == {"id": one, "status": "Backlog", "priority": None, "parent": None, "touches": [ORDER], "repos": ["api"],
                              "deps": [], "archived": False}
        assert nodes[two]["deps"] == [one] and nodes[two]["priority"] == "P1"
        assert index.cites(conn, [PAGE]) == {PAGE: {ORDER}}
        assert index.cites(conn, [ORDER]) == {PAGE: {ORDER}}
        assert index.pages_citing(conn, [ORDER, PAY]) == [PAGE]
        assert index.pages_citing(conn, [PAY]) == []
        assert index.edges(conn, [ORDER, PAY]) == {(ORDER, PAY)}
        assert index.edges(conn, [ORDER]) == set()
        assert index.groups(conn, [ORDER, PAY, PAGE]) == {ORDER: "core/orders", PAY: "core/payments", PAGE: "docs"}
        assert index.search(conn, "ordersvc") == []
        assert index.search(conn, "OrderServ")[0] == {"touch": ORDER, "group": "core/orders", "kind": "file"}
        assert {"touch": "api:core/payments", "group": "core/payments", "kind": "group"} in index.search(conn, "payments")
        assert {"touch": PAGE, "group": "docs", "kind": "page", "title": "Orders"} in index.search(conn, "orders")
        assert len(index.search(conn, "o", limit=2)) == 2
    finally:
        conn.close()


def test_prefix_matches_come_before_substring_matches(world):
    kit, ops, index, one, two = world
    conn = index.connect()
    try:
        assert {h["touch"] for h in index.search(conn, "pay")[:2]} == {PAY, DTO}   # file names start with it
        assert index.search(conn, "PAYMENTC")[0]["touch"] == PAY                    # case-insensitive
        hits = [h["touch"] for h in index.search(conn, "ment")]        # substring only
        assert PAY in hits
    finally:
        conn.close()


def test_archived_items_are_listed_with_their_flag(world):
    kit, ops, index, one, two = world
    f = ops.load_state()[1][one].path
    (kit.root / "backlog" / "archive" / "tasks").mkdir(parents=True, exist_ok=True)
    shutil.move(str(f), str(kit.root / "backlog" / "archive" / "tasks" / f.name))
    conn = index.connect()
    try:
        nodes = {n["id"]: n for n in index.nodes(conn)}
        assert nodes[one]["archived"] is True and nodes[two]["archived"] is False
        assert nodes[one]["touches"] == [ORDER]
    finally:
        conn.close()


def test_rebuilds_when_a_card_changes(world, monkeypatch):
    kit, ops, index, one, two = world
    calls = counting(monkeypatch, index)
    index.connect().close()
    assert len(calls) == 1
    index.connect().close()
    assert len(calls) == 1                                             # nothing changed: no rebuild
    edit(ops, one, **{"x-touches": [ORDER, "api:new/File.java"]})
    conn = index.connect()
    try:
        assert len(calls) == 2
        assert {n["id"]: n for n in index.nodes(conn)}[one]["touches"] == [ORDER, "api:new/File.java"]
    finally:
        conn.close()


def test_a_changed_doc_or_graph_rebuilds(world, monkeypatch):
    kit, ops, index, one, two = world
    calls = counting(monkeypatch, index)
    index.connect().close()
    page = kit.root / "docs" / "orders.md"
    page.write_text(page.read_text(encoding="utf-8") + "\nmore\n", encoding="utf-8")
    index.connect().close()
    assert len(calls) == 2
    g = kit.root / "graph" / "api" / "graph.json"
    g.write_text(g.read_text(encoding="utf-8") + " ", encoding="utf-8")
    index.connect().close()
    assert len(calls) == 3


def test_snapshot_reads_no_file_contents(world, monkeypatch):
    """Cards, docs and graphs are only stat'ed (workspace.yaml, the list of repos, is the one file it reads)."""
    kit, ops, index, one, two = world
    from pathlib import Path
    real = Path.read_text

    def guarded(self, *a, **k):
        if self.name != "workspace.yaml":
            raise AssertionError(f"snapshot read {self}")
        return real(self, *a, **k)

    def boom(*a, **k):
        raise AssertionError("snapshot read a file")
    monkeypatch.setattr(Path, "read_text", guarded)
    monkeypatch.setattr(Path, "read_bytes", boom)
    a = index.snapshot()
    assert a == index.snapshot() and len(a) == 64


def test_corrupt_db_is_rebuilt(world):
    kit, ops, index, one, two = world
    index.DB.parent.mkdir(parents=True, exist_ok=True)
    index.DB.write_bytes(b"this is not a database" * 500)
    conn = index.connect()
    try:
        assert [n["id"] for n in index.nodes(conn)] == [one, two]
    finally:
        conn.close()


def test_a_db_of_another_format_is_rebuilt(world):
    kit, ops, index, one, two = world
    index.connect().close()
    db = sqlite3.connect(index.DB)
    db.execute("update meta set value='0' where key='format'")
    db.commit()
    db.close()
    conn = index.connect()
    try:
        assert conn.execute("select value from meta where key='format'").fetchone()[0] == str(index.FORMAT)
    finally:
        conn.close()


def test_unwritable_cache_falls_back_to_memory(world, monkeypatch, caplog):
    kit, ops, index, one, two = world

    def denied(*a, **k):
        raise PermissionError("locked")
    monkeypatch.setattr(os, "replace", denied)
    monkeypatch.setattr(index, "REPLACE_WAIT", 0.0)
    with caplog.at_level("WARNING", logger="camaron.board.index"):
        conn = index.connect()
    try:
        assert [n["id"] for n in index.nodes(conn)] == [one, two]
    finally:
        conn.close()
    assert not index.DB.exists()
    assert not list(index.DB.parent.glob("board.db.tmp-*"))
    assert any(r.name == "camaron.board.index" for r in caplog.records)


def test_a_cache_that_cannot_be_created_still_answers(world):
    kit, ops, index, one, two = world
    shutil.rmtree(index.DB.parent, ignore_errors=True)
    index.DB.parent.write_text("a file where the cache folder should be", encoding="utf-8")
    conn = index.connect()
    try:
        assert [n["id"] for n in index.nodes(conn)] == [one, two]
    finally:
        conn.close()


def test_scalar_fields_are_lists(world):
    kit, ops, index, one, two = world
    edit(ops, two, dependencies="WI-1", **{"x-touches": "api:a.py", "x-repos": "api"})
    conn = index.connect()
    try:
        n = {n["id"]: n for n in index.nodes(conn)}[two]
        assert n["deps"] == ["WI-1"] and n["touches"] == ["api:a.py"] and n["repos"] == ["api"]
    finally:
        conn.close()


def test_a_bad_graph_does_not_break_the_index(world):
    kit, ops, index, one, two = world
    (kit.root / "graph" / "api" / "graph.json").write_text("{ not json", encoding="utf-8")
    conn = index.connect()
    try:
        assert index.groups(conn, [ORDER, PAY]) == {ORDER: "orders", PAY: "payments"}   # folder names
        assert index.edges(conn, [ORDER, PAY]) == set()
        assert [n["id"] for n in index.nodes(conn)] == [one, two]
    finally:
        conn.close()


def test_an_uninitialised_board_gives_an_empty_index(kit):
    from lib.kanban import index
    conn = index.connect()
    try:
        assert index.nodes(conn) == [] and index.search(conn, "x") == []
    finally:
        conn.close()


def test_two_processes_rebuild_at_once(world):
    kit, ops, index, one, two = world
    edit(ops, one, **{"x-touches": [ORDER, "api:new/File.java"]})
    card = ops.load_state()[1][two].path
    index.DB.unlink(missing_ok=True)
    ctx = multiprocessing.get_context("spawn")
    start = ctx.Barrier(2)                                             # both begin rebuilding at the same moment
    procs = [ctx.Process(target=index_worker.run,
                         args=(str(kit.root), str(kit.home), 20, str(card), "api:new/File.java", start))
             for _ in range(2)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(240)
    stuck = [p for p in procs if p.is_alive()]
    for p in stuck:
        p.terminate()
        p.join(10)
    assert not stuck, "a worker did not finish"
    assert [p.exitcode for p in procs] == [0, 0]
    conn = index.connect()
    try:
        assert "api:new/File.java" in {t for n in index.nodes(conn) for t in n["touches"]}
    finally:
        conn.close()
    db = sqlite3.connect(index.DB)
    try:
        assert db.execute("select value from meta where key='snapshot'").fetchone()[0] == index.snapshot()
    finally:
        db.close()
    assert not list(index.DB.parent.glob("board.db.tmp-*"))


def test_uninstall_leaves_no_trace(world):
    kit, ops, index, one, two = world
    from lib.common import CACHE
    assert index.DB.is_relative_to(CACHE)
    index.connect().close()
    assert index.DB.exists()
    assert not list(index.DB.parent.glob("board.db-*"))                # no journal side files left behind


@pytest.fixture
def bare(kit):
    """A board with no cards and no pages, only the code map: what a story being drafted looks like."""
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)
    from lib.kanban import ops, index
    ops.init(log=lambda _: None)
    write_graph(kit)
    return kit, ops, index


RES = "api:api-web/src/main/java/demo/shop/web/OrderResource.java"



def test_every_graph_file_is_searchable_and_has_a_group(bare):
    kit, ops, index = bare
    conn = index.connect()
    try:
        assert index.search(conn, "OrderRes")[0] == {"touch": RES, "group": "web/web", "kind": "file"}
        assert {"touch": "api:web/web", "group": "web/web", "kind": "group"} in index.search(conn, "web/w")
        assert index.search(conn, "paymentd")[0]["touch"] == DTO
        # files nobody touches or cites still get their group; one the graph does not know gets its folder's name
        new, other_repo = "api:api-core/src/main/java/demo/shop/orders/Fresh.java", "web:src/App.jsx"
        assert index.groups(conn, [RES, DTO, new, other_repo]) == {
            RES: "web/web", DTO: "core/payments/dto", new: "orders", other_repo: "src"}
    finally:
        conn.close()


def test_every_edge_of_the_graph_is_indexed_not_only_touched_ones(bare):
    kit, ops, index = bare
    conn = index.connect()
    try:
        order = "api:api-core/src/main/java/demo/shop/orders/OrderService.java"
        assert index.edges(conn, [RES, order]) == {(RES, order)}          # no card touches either file
        assert index.edges(conn, [RES]) == set()                          # both ends must be in the given touches
        assert conn.execute("select count(*) from edges").fetchone()[0] == 4
    finally:
        conn.close()


def test_two_archived_files_with_one_id_do_not_break_the_index(world, caplog):
    kit, ops, index, one, two = world
    a = kit.root / "backlog" / "archive" / "tasks"
    a.mkdir(parents=True, exist_ok=True)
    text = ops.load_state()[1][one].path.read_text(encoding="utf-8")
    (a / "wi-9 - first.md").write_text(text.replace(f"id: {one}", "id: WI-9"), encoding="utf-8")
    (a / "wi-9 - second.md").write_text(text.replace(f"id: {one}", "id: WI-9").replace("Place order", "Other"),
                                        encoding="utf-8")
    with caplog.at_level("WARNING", logger="camaron.board.index"):
        conn = index.connect()
    try:
        assert [n["id"] for n in index.nodes(conn)] == [one, two, "WI-9"]
        assert conn.execute("select title from items where id='WI-9'").fetchone()[0] == "Place order"   # first file wins
    finally:
        conn.close()
    assert any("WI-9" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("sources", ["3", "[3, null, {a: b}]", "api:api-core/x/Y.java#z", "[api:a.py, 4]"])
def test_hand_written_x_sources_never_break_the_index(world, sources):
    kit, ops, index, one, two = world
    (kit.root / "docs" / "odd.md").write_text(
        "---\ntitle: Odd\nx-sources: " + sources + "\n---\n# Odd\n", encoding="utf-8")
    conn = index.connect()
    try:
        assert [n["id"] for n in index.nodes(conn)] == [one, two]
        assert index.cites(conn, ["cam-docs:docs/odd.md"]).get("cam-docs:docs/odd.md", set()) <= {
            "api:api-core/x/Y.java", "api:a.py"}
    finally:
        conn.close()


def test_odd_card_fields_never_break_the_index(world):
    kit, ops, index, one, two = world
    edit(ops, one, priority=[1, 2], parent_task_id=["WI-1"], **{"x-touches": ["api:ok.py", 5, None]})
    conn = index.connect()
    try:
        assert [n["id"] for n in index.nodes(conn)] == [one, two]
    finally:
        conn.close()


def test_the_in_memory_fallback_closes_its_connection_when_the_build_fails(world, monkeypatch):
    kit, ops, index, one, two = world
    opened = []

    class Rec(sqlite3.Connection):
        closed = False

        def close(self):
            self.closed = True
            super().close()
    real = sqlite3.connect
    monkeypatch.setattr(index.sqlite3, "connect", lambda *a, **k: opened.append(real(*a, factory=Rec, **k)) or opened[-1])
    monkeypatch.setattr(index, "_build", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bug")))
    with pytest.raises(RuntimeError):
        index._in_memory("x")
    assert opened and all(c.closed for c in opened)
