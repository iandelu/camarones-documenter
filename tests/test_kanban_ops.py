from __future__ import annotations

import json
import re
import subprocess
import threading

import pytest


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8").stdout.strip()


@pytest.fixture
def board(kit):
    """A kit whose cam-docs is a git repo with an initialised board."""
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)
    from lib.kanban import ops
    ops.init(log=lambda _: None)
    return ops


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / "backlog").rglob("*") if p.is_file()}


def test_init_creates_layout_and_is_idempotent(kit):
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)
    from lib.kanban import ops
    from lib.kanban.state import load_board
    made = ops.init(log=lambda _: None)
    assert made
    b = kit.root / "backlog"
    for d in ("tasks", "drafts", "archive/tasks"):
        assert (b / d).is_dir()
    assert load_board((b / "board.yaml").read_text(encoding="utf-8")) == {}
    cfg = (b / "config.yml").read_text(encoding="utf-8")
    assert 'task_prefix: "WI"' in cfg.splitlines()
    assert "statuses:\n  - Backlog\n  - Ready\n" in cfg
    assert "check_active_branches: false" in cfg and "auto_commit: false" in cfg
    attrs = (kit.root / ".gitattributes").read_text(encoding="utf-8")
    assert attrs.count("backlog/board.yaml merge=camaron-board") == 1
    assert "board merge-driver %O %A %B" in git(kit.root, "config", "merge.camaron-board.driver")
    before = tree(kit.root)
    attrs_before = (kit.root / ".gitattributes").read_bytes()
    assert ops.init(log=lambda _: None) == []
    assert tree(kit.root) == before
    assert (kit.root / ".gitattributes").read_bytes() == attrs_before


def test_config_keeps_keys_people_added(board, kit):
    cfg = kit.root / "backlog" / "config.yml"
    text = cfg.read_text(encoding="utf-8").replace("  - Ready\n", "  - Listo\n") + "default_editor: vim\n"
    cfg.write_text(text, encoding="utf-8")
    assert board.write_config() is True
    new = cfg.read_text(encoding="utf-8")
    assert "default_editor: vim" in new.splitlines()
    assert "  - Ready\n" in new and "Listo" not in new
    assert board.write_config() is False


def test_config_adds_project_definition_of_done(kit):
    ws = kit.docs.workspace()
    ws["board"] = {"definition_of_done": ["security reviewed"]}
    kit.docs.save_workspace(ws)
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)
    from lib.kanban import ops
    ops.init(log=lambda _: None)
    cfg = (kit.root / "backlog" / "config.yml").read_text(encoding="utf-8")
    assert "  - acceptance criteria met\n" in cfg and "  - security reviewed\n" in cfg


def test_add_story_writes_file_and_card(board, kit):
    from lib.kanban.items import parse_item
    from lib.kanban.state import load_board
    epic = board.add("epic", "Payments")
    assert epic["id"] == "WI-1"
    row = board.add("story", "Pay twice", epic="WI-1", repos=["api"], labels=["pay"], priority="P1")
    assert row["id"] == "WI-2"
    f = kit.root / "backlog" / "tasks" / "wi-2 - Pay twice.md"
    item = parse_item(f.read_text(encoding="utf-8"), f)
    assert item.fm["parent_task_id"] == "WI-1" and item.fm["x-repos"] == ["api"] and item.fm["x-uid"]
    assert item.fm["status"] == "Backlog" and item.fm["ordinal"] == 2000 and item.fm["priority"] == "P1"
    assert item.fm["labels"] == ["pay"] and item.fm["type"] == "story"
    assert "<!-- DOD:BEGIN -->" in item.body
    epic_file = next((kit.root / "backlog" / "tasks").glob("wi-1 - *.md"))
    assert parse_item(epic_file.read_text(encoding="utf-8")).fm["subtasks"] == ["WI-2"]
    cards = load_board((kit.root / "backlog" / "board.yaml").read_text(encoding="utf-8"))
    assert cards["WI-2"]["uid"] == item.fm["x-uid"]
    assert cards["WI-2"]["t"]["status"].endswith("Z test@example.com")
    assert cards["WI-2"]["ordinal"] == 2000 and cards["WI-1"]["ordinal"] == 1000
    assert (kit.root / "backlog" / "board.yaml").read_bytes().count(b"\r") == 0


def test_add_validates(board):
    with pytest.raises(board.BoardError):
        board.add("saga", "x")
    with pytest.raises(board.BoardError):
        board.add("story", "x", priority="P9")
    with pytest.raises(board.BoardError):
        board.add("story", "x", epic="WI-99")
    assert board.list_items()["cards"] == []


def test_ops_need_an_initialised_board(kit):
    from lib.kanban import ops
    with pytest.raises(ops.BoardError):
        ops.add("task", "x")


def test_ids_are_never_reused_after_archive(board):
    board.add("task", "one")
    board.add("task", "two")
    board.archive("WI-2")
    assert board.add("task", "three")["id"] == "WI-3"


def test_move_updates_board_and_mirror(board, kit):
    from lib.kanban.items import parse_item
    from lib.kanban.state import load_board
    for t in ("a", "b", "c"):
        board.add("task", t)
    r = board.move("WI-1", "Ready")
    assert r["status"] == "Ready"
    cards = load_board((kit.root / "backlog" / "board.yaml").read_text(encoding="utf-8"))
    f = next((kit.root / "backlog" / "tasks").glob("wi-1 - *.md"))
    assert cards["WI-1"]["status"] == "Ready" == parse_item(f.read_text(encoding="utf-8")).fm["status"]
    board.move("WI-2", "Ready")
    board.move("WI-3", "Ready", before="WI-1")
    cards = load_board((kit.root / "backlog" / "board.yaml").read_text(encoding="utf-8"))
    assert cards["WI-3"]["ordinal"] < cards["WI-1"]["ordinal"] < cards["WI-2"]["ordinal"]
    f3 = next((kit.root / "backlog" / "tasks").glob("wi-3 - *.md"))
    assert parse_item(f3.read_text(encoding="utf-8")).fm["ordinal"] == cards["WI-3"]["ordinal"]
    board.move("WI-3", "Ready", after="WI-2")
    cards = load_board((kit.root / "backlog" / "board.yaml").read_text(encoding="utf-8"))
    assert cards["WI-3"]["ordinal"] > cards["WI-2"]["ordinal"]


def test_move_errors(board):
    board.add("task", "a")
    board.add("task", "b")
    with pytest.raises(board.BoardError):
        board.move("WI-1", "Nope")
    with pytest.raises(board.BoardError):
        board.move("WI-9", "Ready")
    with pytest.raises(board.BoardError):
        board.move("WI-1", "Ready", before="WI-2", after="WI-2")
    with pytest.raises(board.BoardError):
        board.move("WI-1", "Ready", before="WI-2")       # the anchor is not in that column


def test_move_rebalances_mirrors_of_neighbours(board, kit):
    from lib.kanban.items import parse_item
    from lib.kanban.state import load_board
    for t in "abc":
        board.add("task", t)
    for _ in range(14):                                   # squeeze WI-3 between WI-1 and WI-2 until there is no room
        board.move("WI-3", "Backlog", before="WI-2")
        board.move("WI-2", "Backlog", before="WI-3")
    cards = load_board((kit.root / "backlog" / "board.yaml").read_text(encoding="utf-8"))
    for i, c in cards.items():
        f = next((kit.root / "backlog" / "tasks").glob(f"{i.lower()} - *.md"))
        assert parse_item(f.read_text(encoding="utf-8")).fm["ordinal"] == c["ordinal"]
    assert len({c["ordinal"] for c in cards.values()}) == 3


def test_assign_and_clear(board, kit):
    from lib.kanban.items import parse_item
    board.add("task", "a")
    assert board.assign("WI-1", "ana")["assignee"] == ["ana"]
    f = next((kit.root / "backlog" / "tasks").glob("wi-1 - *.md"))
    assert parse_item(f.read_text(encoding="utf-8")).fm["assignee"] == ["ana"]
    assert board.assign("WI-1", "-")["assignee"] == []
    assert parse_item(f.read_text(encoding="utf-8")).fm["assignee"] == []


def test_archive_moves_file_and_drops_card(board, kit):
    from lib.kanban.state import load_board
    board.add("task", "a")
    board.archive("WI-1")
    b = kit.root / "backlog"
    assert not list((b / "tasks").glob("*.md"))
    assert [p.name for p in (b / "archive" / "tasks").glob("*.md")] == ["wi-1 - a.md"]
    assert load_board((b / "board.yaml").read_text(encoding="utf-8")) == {}
    with pytest.raises(board.BoardError):
        board.archive("WI-1")


def test_list_filters(board, kit):
    (kit.root / "docs" / "flows").mkdir(parents=True)
    (kit.root / "docs" / "flows" / "pay.md").write_text("---\nx-id: FLOW-k3f9\n---\n# Pay\n\n## Retries\nx\n", encoding="utf-8")
    board.add("epic", "Payments")
    board.add("story", "Pay twice", epic="WI-1", repos=["api"], labels=["pay"], docs=["FLOW-k3f9#retries"])
    board.add("bug", "Crash", repos=["web"])
    board.move("WI-3", "Ready")
    (kit.root / "backlog" / "tasks" / "broken.md").write_text("no frontmatter", encoding="utf-8")
    out = board.list_items()
    assert [c["id"] for c in out["cards"]] == ["WI-1", "WI-2", "WI-3"]
    assert [p["path"] for p in out["problems"]] and "broken.md" in str(out["problems"][0]["path"])
    assert [c["id"] for c in board.list_items(status="Ready")["cards"]] == ["WI-3"]
    assert [c["id"] for c in board.list_items(epic="WI-1")["cards"]] == ["WI-2"]
    assert [c["id"] for c in board.list_items(repo="web")["cards"]] == ["WI-3"]
    assert [c["id"] for c in board.list_items(label="pay")["cards"]] == ["WI-2"]
    assert [c["id"] for c in board.list_items(docs="FLOW-k3f9")["cards"]] == ["WI-2"]
    row = board.list_items(label="pay")["cards"][0]
    assert set(row) >= {"id", "uid", "title", "type", "status", "ordinal", "assignee", "labels", "priority", "epic",
                        "repos", "docs"}
    assert len(row["docs"]) == 1 and row["docs"][0].startswith("FLOW-k3f9#retries@") and row["epic"] == "WI-1" and row["repos"] == ["api"]
    # sorted by column, then ordinal: Backlog cards first, Ready after
    assert [c["status"] for c in out["cards"]] == ["Backlog", "Backlog", "Ready"]


def test_show_has_criteria_dod_history(board, kit):
    board.add("story", "Pay twice")
    f = next((kit.root / "backlog" / "tasks").glob("wi-1 - *.md"))
    text = f.read_text(encoding="utf-8").replace("<!-- AC:BEGIN -->\n", "<!-- AC:BEGIN -->\n- [x] #1 No double charge\n")
    f.write_text(text, encoding="utf-8")
    git(kit.root, "add", "-A")
    git(kit.root, "commit", "-qm", "seed board")
    board.move("WI-1", "Ready")
    s = board.show("WI-1")
    assert s["id"] == "WI-1" and s["status"] == "Ready"
    assert s["criteria"] == [{"n": 1, "done": True, "text": "No double charge"}]
    assert s["dod"][0]["text"] == "acceptance criteria met" and s["description"]
    assert s["file"].endswith("wi-1 - Pay twice.md")
    sources = {h["source"] for h in s["history"]}
    assert sources == {"board", "git"}
    assert any(h["by"] == "test@example.com" and h["what"] == "status" for h in s["history"])
    assert any(h["what"] == "seed board" for h in s["history"])
    with pytest.raises(board.BoardError):
        board.show("WI-77")


def test_two_writers_do_not_lose_cards(board, kit):
    errors = []

    def work(k):
        try:
            for n in range(10):
                board.add("task", f"t{k}-{n}")
        except Exception as e:      # pragma: no cover
            errors.append(e)

    ts = [threading.Thread(target=work, args=(k,)) for k in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors
    from lib.kanban.state import load_board
    cards = load_board((kit.root / "backlog" / "board.yaml").read_text(encoding="utf-8"))
    files = list((kit.root / "backlog" / "tasks").glob("*.md"))
    assert len(cards) == 20 and len(files) == 20 and len({f.name.split(" - ")[0] for f in files}) == 20


def test_new_project_gets_a_board(kit):
    assert not (kit.root / ".git").exists()
    kit.env.init_templates(log=lambda _: None)
    assert (kit.root / "backlog" / "board.yaml").exists()
    assert (kit.root / "backlog" / "tasks").is_dir()


def test_existing_project_unchanged(kit):
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)         # already a docs repo: the board is opt-in
    kit.env.init_templates(log=lambda _: None)
    assert not (kit.root / "backlog").exists()
    assert not (kit.root / ".gitattributes").exists()
    assert git(kit.root, "config", "--get", "merge.camaron-board.driver") == ""


def test_usage_counts_surface(board, kit):
    kit.usage.set_enabled(True)
    board.add("task", "a", surface="portal")
    board.move("WI-1", "Ready", surface="cli")
    data = json.loads((kit.usage.DIR / f"{kit.usage.me()}.json").read_text(encoding="utf-8"))
    events = next(iter(data["months"].values()))["events"]
    assert events["board:add:portal"] == 1 and events["board:move:cli"] == 1


def test_who_is_the_git_email(kit):
    from lib.kanban import ops
    assert ops.who() == "test@example.com"


def test_who_falls_back_to_login(kit, monkeypatch):
    from lib.kanban import ops
    monkeypatch.setattr(ops, "out", lambda *a, **k: "")
    monkeypatch.setattr(ops.getpass, "getuser", lambda: "shrimp")
    assert ops.who() == "shrimp"


# --- final review ---

def test_scalar_lists_in_a_hand_written_item(board, kit):
    (kit.root / "backlog" / "tasks" / "wi-7 - Hand.md").write_text(
        "---\nid: WI-7\ntitle: Hand\nstatus: Ready\nassignee: ana\nlabels: payments\nx-repos: api\n---\n\nBody\n",
        encoding="utf-8")
    row = next(c for c in board.list_items()["cards"] if c["id"] == "WI-7")
    assert row["labels"] == ["payments"] and row["repos"] == ["api"] and row["assignee"] == ["ana"]
    assert [c["id"] for c in board.list_items(label="payments")["cards"]] == ["WI-7"]


def test_bom_item_is_read(board, kit):
    f = kit.root / "backlog" / "tasks" / "wi-8 - Bom.md"
    f.write_bytes("\ufeff---\nid: WI-8\ntitle: Bom\nstatus: Backlog\n---\n\nBody\n".encode("utf-8"))
    out = board.list_items()
    assert out["problems"] == [] and [c["id"] for c in out["cards"]] == ["WI-8"]
    from lib.kanban.items import parse_item, serialize_item
    item = parse_item(f.read_text(encoding="utf-8"), f)
    assert item.title == "Bom" and item.body == "Body\n"
    assert serialize_item(item) == "---\nid: WI-8\ntitle: Bom\nstatus: Backlog\n---\n\nBody\n"


def test_a_card_less_item_is_adopted_when_written(board, kit):
    """A file made by Backlog.md or by hand shows on the board before any repair; moving it must work too."""
    f = kit.root / "backlog" / "tasks" / "wi-3 - Hand made.md"
    f.write_text("---\nid: WI-3\ntitle: Hand made\nstatus: in progress\nassignee: ana\n---\n\nBody\n", encoding="utf-8")
    assert [c["id"] for c in board.list_items()["cards"]] == ["WI-3"]
    board.move("WI-3", "Done")
    from lib.kanban.items import parse_item
    from lib.kanban.state import load_board
    cards = load_board((kit.root / "backlog" / "board.yaml").read_text(encoding="utf-8"))
    item = parse_item(f.read_text(encoding="utf-8"))
    assert cards["WI-3"]["status"] == "Done" and cards["WI-3"]["uid"] == item.uid and item.uid
    assert item.fm["status"] == "Done" and cards["WI-3"]["assignee"] == ["ana"]
    g = kit.root / "backlog" / "tasks" / "wi-4 - Other.md"
    g.write_text("---\nid: WI-4\ntitle: Other\nstatus: Ready\n---\n\nBody\n", encoding="utf-8")
    board.assign("WI-4", "bo")
    cards = load_board((kit.root / "backlog" / "board.yaml").read_text(encoding="utf-8"))
    assert cards["WI-4"]["assignee"] == ["bo"] and cards["WI-4"]["status"] == "Ready"


def test_a_uid_mismatch_never_writes_the_wrong_file(board, kit):
    """Duplicate ids (WI-1 and WI-1~uid after a merge) or a hand-edited x-uid: the card and the file must be the same item."""
    board.add("task", "Mine")
    f = next((kit.root / "backlog" / "tasks").glob("wi-1 - *.md"))
    f.write_text(f.read_text(encoding="utf-8").replace("x-uid: ", "x-uid: zz"), encoding="utf-8")
    before = tree(kit.root)
    for write in (lambda: board.move("WI-1", "Done"), lambda: board.assign("WI-1", "ana"),
                  lambda: board.archive("WI-1")):
        with pytest.raises(board.BoardError, match="camaron board repair"):
            write()
    assert tree(kit.root) == before


def test_add_writes_the_new_item_before_its_epic(board, kit, monkeypatch):
    board.add("epic", "Payments")
    before = tree(kit.root)
    real = board.save_item

    def failing(item):
        if item.id == "WI-2":
            raise OSError("disk full")
        real(item)
    monkeypatch.setattr(board, "save_item", failing)
    with pytest.raises(OSError):
        board.add("story", "Pay", epic="WI-1")
    assert tree(kit.root) == before                     # the epic does not list a story that was never written


def test_a_failed_replace_leaves_no_temp_file(board, kit, monkeypatch):
    def boom(*_):
        raise OSError("locked")
    monkeypatch.setattr(board.os, "replace", boom)
    with pytest.raises(OSError):
        board.add("task", "x")
    monkeypatch.undo()
    assert list((kit.root / "backlog").rglob("*.tmp")) == []


# --- story parents, footprints, dependencies ---

def _fm(kit, item_id):
    from lib.kanban.items import parse_item
    f = next((kit.root / "backlog" / "tasks").glob(f"{item_id.lower()} - *.md"))
    return parse_item(f.read_text(encoding="utf-8"), f)


def test_add_task_under_story(board, kit):
    board.add("story", "Pay twice")
    row = board.add("task", "x", parent="WI-1", touches=["api:b.py", "api:a.py"])
    assert row["parent"] == "WI-1" and row["epic"] == "WI-1" and row["touches"] == ["api:a.py", "api:b.py"]
    fm = _fm(kit, "WI-2").fm
    assert fm["parent_task_id"] == "WI-1" and fm["x-touches"] == ["api:a.py", "api:b.py"]
    assert fm["x-repos"] == ["api"]                                   # defaults to the repos of the touches
    assert _fm(kit, "WI-1").fm["subtasks"] == ["WI-2"]
    text = next((kit.root / "backlog" / "tasks").glob("wi-2 - *.md")).read_text(encoding="utf-8")
    assert "x-touches:\n  - api:a.py\n  - api:b.py\n" in text
    assert "dependencies" not in text and "x-touches" not in _fm(kit, "WI-1").fm


def test_add_keeps_explicit_repos_over_touches(board, kit):
    board.add("task", "x", repos=["web"], touches=["api:a.py"])
    assert _fm(kit, "WI-1").fm["x-repos"] == ["web"]


def test_add_epic_alias_and_parent_must_agree(board):
    board.add("epic", "Payments")
    board.add("epic", "Other")
    assert board.add("story", "a", epic="WI-1")["parent"] == "WI-1"
    assert board.add("story", "b", epic="WI-1", parent="wi-1")["parent"] == "WI-1"
    with pytest.raises(board.BoardError):
        board.add("story", "c", epic="WI-1", parent="WI-2")


def test_add_refuses_bad_parents(board, kit):
    board.add("epic", "Payments")
    board.add("story", "Pay twice")
    board.add("bug", "Crash")
    before = tree(kit.root)
    for type_, parent in (("story", "WI-2"), ("task", "WI-3"), ("task", "WI-99"), ("epic", "WI-1"), ("epic", "WI-2")):
        with pytest.raises(board.BoardError):
            board.add(type_, "x", parent=parent)
    assert tree(kit.root) == before
    for type_ in ("story", "bug", "spike", "task"):                    # an epic takes anything but an epic
        assert board.add(type_, "ok", parent="WI-1")["parent"] == "WI-1"
    assert board.add("task", "under a story", parent="WI-2")["parent"] == "WI-2"


def test_add_refuses_a_bad_touch(board, kit):
    before = tree(kit.root)
    for bad in ("no-colon.py", "api:../x.py", "api:", ":a.py"):
        with pytest.raises(board.BoardError, match=re.escape(bad)):
            board.add("task", "x", touches=[bad])
    assert tree(kit.root) == before


def test_add_description_and_criteria_fill_the_template(board, kit):
    board.add("task", "x", description="Retry the charge once.", criteria=["A retry happens", "  No double  charge "])
    body = _fm(kit, "WI-1").body
    desc = body.split("<!-- SECTION:DESCRIPTION:BEGIN -->\n")[1].split("\n<!-- SECTION:DESCRIPTION:END -->")[0]
    assert desc == "Retry the charge once."
    ac = body.split("<!-- AC:BEGIN -->\n")[1].split("<!-- AC:END -->")[0]
    assert ac == "- [ ] #1 A retry happens\n- [ ] #2 No double charge\n"
    assert "- [ ] #1 acceptance criteria met\n" in body.split("<!-- DOD:BEGIN -->\n")[1]    # DoD unchanged
    board.add("task", "y")
    plain = _fm(kit, "WI-2").body
    assert "What needs doing" in plain and "<!-- AC:BEGIN -->\n<!-- AC:END -->" in plain


def test_add_dependencies_must_exist(board, kit):
    board.add("task", "one")
    board.add("task", "two")
    before = tree(kit.root)
    with pytest.raises(board.BoardError, match="WI-9"):
        board.add("task", "x", dependencies=["WI-1", "WI-9"])
    assert tree(kit.root) == before
    row = board.add("task", "three", dependencies=["wi-2", "WI-1", "WI-2"])
    assert row["dependencies"] == ["WI-1", "WI-2"]
    assert _fm(kit, "WI-3").fm["dependencies"] == ["WI-1", "WI-2"]


def test_add_dependency_on_archived_item_is_allowed(board, kit):
    board.add("task", "old")
    board.archive("WI-1")
    row = board.add("task", "new", dependencies=["WI-1"])
    assert row["id"] == "WI-2" and _fm(kit, "WI-2").fm["dependencies"] == ["WI-1"]


@pytest.mark.parametrize("folds", [True, False])
def test_touches_normalised_and_case_folded(board, kit, monkeypatch, folds):
    monkeypatch.setattr(board, "IS_WIN", folds)
    monkeypatch.setattr(board, "IS_MAC", False)
    row = board.add("task", "x", touches=["api:src\\A.java", "api:./src/a.java ", " api:src/A.java"])
    assert row["touches"] == (["api:src/A.java"] if folds else ["api:src/A.java", "api:src/a.java"])
    assert _fm(kit, "WI-1").fm["x-touches"] == row["touches"]
    monkeypatch.setattr(board, "IS_WIN", False)
    monkeypatch.setattr(board, "IS_MAC", True)
    assert len(board.add("task", "y", touches=["api:B.java", "api:b.java"])["touches"]) == 1


def _write_4x(kit):
    """A board as a 4.x kit left it: epics and stories, none of the new fields."""
    from lib.kanban import TASKS
    from lib.kanban.items import Item, file_name, serialize_item
    from lib.kanban.state import dump_board
    rows = [("WI-1", "Payments", "epic", None, ["WI-2", "WI-3"]), ("WI-2", "Pay", "story", "WI-1", None),
            ("WI-3", "Refund", "story", "WI-1", None), ("WI-4", "Loose", "bug", None, None)]
    cards = {}
    for n, (i, title, type_, parent, subs) in enumerate(rows, 1):
        fm = {"id": i, "title": title, "status": "Backlog", "assignee": [], "created_date": "2026-10-01 10:00",
              "labels": ["pay"], "parent_task_id": parent, "subtasks": subs, "type": type_, "ordinal": n * 1000,
              "x-uid": f"uid{n:05d}", "x-repos": ["api"]}
        item = Item({k: v for k, v in fm.items() if v is not None}, "## Description\nx\n", TASKS / file_name(i, title))
        item.path.write_text(serialize_item(item), encoding="utf-8", newline="\n")
        cards[i] = {"uid": fm["x-uid"], "status": "Backlog", "ordinal": n * 1000, "assignee": [], "t": {}}
    (kit.root / "backlog" / "board.yaml").write_text(dump_board(cards), encoding="utf-8", newline="\n")


def test_old_board_lists_the_same(board, kit):
    _write_4x(kit)
    cards = board.list_items()["cards"]
    assert [c["id"] for c in cards] == ["WI-1", "WI-2", "WI-3", "WI-4"]
    for c in cards:
        assert c["parent"] == c["epic"] and c["touches"] == [] and c["dependencies"] == []
    old = {k for k in cards[0] if k not in ("parent", "touches", "dependencies")}
    assert old == {"id", "uid", "title", "type", "status", "ordinal", "assignee", "labels", "priority", "epic", "repos",
                   "docs"}
    assert [c["epic"] for c in cards] == [None, "WI-1", "WI-1", None]
    assert [c["id"] for c in board.list_items(epic="WI-1")["cards"]] == ["WI-2", "WI-3"]
    assert [c["id"] for c in board.list_items(parent="WI-1")["cards"]] == ["WI-2", "WI-3"]
    assert board.list_items(parent="WI-4")["cards"] == []


def test_list_filters_on_a_story_parent(board):
    board.add("story", "Pay")
    board.add("task", "a", parent="WI-1")
    board.add("task", "b", parent="WI-1")
    board.add("task", "c")
    assert [c["id"] for c in board.list_items(parent="wi-1")["cards"]] == ["WI-2", "WI-3"]


def test_hand_written_scalars_are_lists_in_rows(board, kit):
    board.add("task", "x")
    f = next((kit.root / "backlog" / "tasks").glob("wi-1 - *.md"))
    f.write_text(f.read_text(encoding="utf-8").replace("type: task\n", "type: task\nx-touches: api:a.py\ndependencies: WI-7\n"),
                 encoding="utf-8")
    row = board.list_items()["cards"][0]
    assert row["touches"] == ["api:a.py"] and row["dependencies"] == ["WI-7"]


def test_update_item_appends_criteria_and_keeps_numbering(board, kit):
    board.add("story", "Pay", description="Old.", criteria=["one", "two"])
    f = next((kit.root / "backlog" / "tasks").glob("wi-1 - *.md"))
    f.write_text(f.read_text(encoding="utf-8").replace("- [ ] #2 two", "- [x] #2 two"), encoding="utf-8")
    board.add("task", "t")
    row = board.update_item("wi-1", add_criteria=["three", "four"], description="New text.", touches=["api:b.py", "api:a.py"],
                            subtasks=["WI-2"], by="me@x")
    assert row["touches"] == ["api:a.py", "api:b.py"] and row["id"] == "WI-1"
    item = _fm(kit, "WI-1")
    assert [(c["n"], c["done"], c["text"]) for c in board.show("WI-1")["criteria"]] == [
        (1, False, "one"), (2, True, "two"), (3, False, "three"), (4, False, "four")]
    assert board.show("WI-1")["description"] == "New text."
    assert item.fm["x-touches"] == ["api:a.py", "api:b.py"] and item.fm["subtasks"] == ["WI-2"]
    assert "<!-- DOD:BEGIN -->" in item.body and item.fm["title"] == "Pay"
    assert board.update_item("WI-1", touches=[])["touches"] == []
    assert "x-touches" not in _fm(kit, "WI-1").fm


def test_update_item_changes_only_what_it_is_given(board, kit):
    board.add("task", "x", touches=["api:a.py"], description="Keep me.")
    before = _fm(kit, "WI-1")
    board.update_item("WI-1")
    after = _fm(kit, "WI-1")
    assert after.body == before.body
    assert {k: v for k, v in after.fm.items() if k != "updated_date"} == {k: v for k, v in before.fm.items() if k != "updated_date"}


def test_update_item_without_criteria_block_or_description_block(board, kit):
    board.add("task", "x")
    f = next((kit.root / "backlog" / "tasks").glob("wi-1 - *.md"))
    text = f.read_text(encoding="utf-8")
    head = text.split("## Description")[0]
    f.write_text(head + "just notes\n", encoding="utf-8")                 # a Backlog.md file with no managed blocks
    board.update_item("WI-1", description="D", add_criteria=["c1"])
    s = board.show("WI-1")
    assert s["description"] == "D" and s["criteria"] == [{"n": 1, "done": False, "text": "c1"}]
    assert "just notes" in _fm(kit, "WI-1").body


def test_update_item_title_docs_and_errors(board, kit):
    (kit.root / "docs" / "flows").mkdir(parents=True)
    (kit.root / "docs" / "flows" / "pay.md").write_text("---\nx-id: FLOW-k3f9\n---\n# Pay\n\n## Retries\nx\n", encoding="utf-8")
    board.add("task", "Old name")
    row = board.update_item("WI-1", title="New name", docs=["FLOW-k3f9#retries"])
    assert row["title"] == "New name" and row["docs"][0].startswith("FLOW-k3f9#retries@")
    files = [p.name for p in (kit.root / "backlog" / "tasks").glob("*.md")]
    assert files == ["wi-1 - New name.md"]
    before = tree(kit.root)
    with pytest.raises(board.BoardError):
        board.update_item("WI-77", title="x")
    with pytest.raises(board.BoardError):
        board.update_item("WI-1", title="  ")
    with pytest.raises(board.BoardError):
        board.update_item("WI-1", touches=["nope"])
    with pytest.raises(board.BoardError, match="WI-9"):
        board.update_item("WI-1", subtasks=["WI-9"])
    assert tree(kit.root) == before


def test_update_item_counts_the_surface(board, kit):
    kit.usage.set_enabled(True)
    board.add("task", "x")
    board.update_item("WI-1", title="y", surface="mcp")
    data = json.loads((kit.usage.DIR / f"{kit.usage.me()}.json").read_text(encoding="utf-8"))
    events = next(iter(data["months"].values()))["events"]
    assert events["board:update:mcp"] == 1
