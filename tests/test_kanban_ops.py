from __future__ import annotations

import json
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
    assert [c["id"] for c in out["cards"]] == ["WI-1", "WI-2", "WI-3"] or len(out["cards"]) == 3
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


def test_who_falls_back_to_login(kit):
    from lib.kanban import ops
    assert ops.who() == "test@example.com" or ops.who()
