"""The board's repair pass (spec §4) and its hooks: checkpoint and share. Runs on the `wired` project, which has a board."""
from __future__ import annotations

import subprocess
from datetime import date


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def mk(wired, item_id, title="Thing", **fm):
    """Write an item file the way a person or another branch would (not through ops)."""
    from lib.kanban import TASKS
    from lib.kanban.items import Item, file_name, serialize_item
    base = {"id": item_id, "title": title, "status": "Backlog", "assignee": [], "created_date": "2026-10-01 10:00",
            "type": "task", "ordinal": 1000}
    base.update(fm)
    item = Item({k: v for k, v in base.items() if v is not None}, "## Description\nx\n", TASKS / file_name(item_id, title))
    item.path.write_text(serialize_item(item), encoding="utf-8", newline="\n")
    return item.path


def card(uid, status="Backlog", ordinal=1000, t=None):
    return {"uid": uid, "status": status, "ordinal": ordinal, "assignee": [], "t": t or {}}


def put_board(cards):
    from lib.kanban import ops
    ops.save_board(cards)


def get_board():
    from lib.kanban import BOARD
    from lib.kanban.state import load_board
    return load_board(BOARD.read_text(encoding="utf-8"))


def read(path):
    from lib.kanban.items import parse_item
    return parse_item(path.read_text(encoding="utf-8"), path)


def run_repair(**kw):
    from lib.kanban import repair
    return repair.repair(log=lambda _: None, **kw)


def snapshot(root):
    return {p: p.read_bytes() for p in (root / "backlog").rglob("*") if p.is_file()}


def test_adopts_file_without_card(wired):
    f = mk(wired, "WI-9", "Hand made", status="Ready")
    g = mk(wired, "WI-10", "Odd status", status="Doing")
    r = run_repair()
    cards = get_board()
    assert cards["WI-9"]["status"] == "Ready" and cards["WI-9"]["uid"]
    assert read(f).uid == cards["WI-9"]["uid"]
    assert cards["WI-10"]["status"] == "Backlog" and read(g).fm["status"] == "Backlog"
    assert any("WI-10" in w and "Doing" in w for w in r["warnings"])
    assert r["changed"]


def test_renumbers_duplicate_ids_and_rewrites_references(wired):
    from lib.kanban import TASKS
    a = mk(wired, "WI-5", "Older", **{"x-uid": "aaaa1111", "created_date": "2026-10-01 10:00"})
    b = mk(wired, "WI-5", "Newer", **{"x-uid": "bbbb2222", "created_date": "2026-10-01 11:00"}, subtasks=["WI-4"])
    c = mk(wired, "WI-6", "Depends", **{"x-uid": "cccc3333"}, dependencies=["WI-5~bbbb2222"])
    d = mk(wired, "WI-4", "Child", **{"x-uid": "dddd4444"}, parent_task_id="WI-5")
    put_board({"WI-5": card("aaaa1111"), "WI-5~bbbb2222": card("bbbb2222", ordinal=2000),
               "WI-6": card("cccc3333", ordinal=3000), "WI-4": card("dddd4444", ordinal=4000)})
    logs = []
    from lib.kanban import repair
    r = repair.repair(log=logs.append)
    cards = get_board()
    assert cards["WI-5"]["uid"] == "aaaa1111" and cards["WI-7"]["uid"] == "bbbb2222"
    assert not [k for k in cards if "~" in k]
    assert not b.exists() and (TASKS / "wi-7 - Newer.md").exists() and a.exists()
    assert read(TASKS / "wi-7 - Newer.md").id == "WI-7"
    assert read(c).fm["dependencies"] == ["WI-7"]
    assert read(d).fm["parent_task_id"] == "WI-7"
    assert any("WI-7" in line for line in logs) and r["changed"]


def test_rewrites_mirrors_and_warns(wired):
    from lib.kanban import ops
    from lib.kanban.items import serialize_item
    ops.add("task", "Mirror me")
    path = next(wired.root.glob("backlog/tasks/wi-1 - *.md"))
    item = read(path)
    item.fm["status"] = "Done"
    path.write_text(serialize_item(item), encoding="utf-8", newline="\n")
    r = run_repair()
    assert read(path).fm["status"] == "Backlog"
    assert any("WI-1" in w for w in r["warnings"])


def test_archives_done_after_days(wired):
    from lib.kanban import ARCHIVE
    old = mk(wired, "WI-1", "Old", status="Done", **{"x-uid": "old00001"})
    new = mk(wired, "WI-2", "Fresh", status="Done", **{"x-uid": "new00002"})
    put_board({"WI-1": card("old00001", "Done", t={"status": "2026-10-10T08:00:00Z a@b"}),
               "WI-2": card("new00002", "Done", ordinal=2000, t={"status": "2026-10-12T08:00:00Z a@b"})})
    run_repair(today=date(2026, 10, 25))
    assert (ARCHIVE / old.name).exists() and not old.exists() and new.exists()
    assert set(get_board()) == {"WI-2"}


def test_archive_after_days_from_workspace(wired):
    from lib.kanban import ARCHIVE
    ws = wired.docs.workspace()
    ws["board"] = {"archive_after_days": 3}
    wired.docs.save_workspace(ws)
    f = mk(wired, "WI-1", "Soon", status="Done", **{"x-uid": "old00001"})
    put_board({"WI-1": card("old00001", "Done", t={"status": "2026-10-20T08:00:00Z a@b"})})
    run_repair(today=date(2026, 10, 25))
    assert (ARCHIVE / f.name).exists()


def test_warns_on_unused_backlogmd_folders_and_unknown_links(wired):
    from lib.kanban import BACKLOG
    (BACKLOG / "docs").mkdir()
    (BACKLOG / "docs" / "notes.md").write_text("# n\n", encoding="utf-8")
    mk(wired, "WI-1", "Linky", documentation=["FLOW-zzzz#a@1234abcd"], **{"x-uid": "link0001"})
    put_board({"WI-1": card("link0001")})
    r = run_repair()
    assert len(r["warnings"]) == 2
    assert any("docs" in w for w in r["warnings"]) and any("FLOW-zzzz" in w for w in r["warnings"])


def test_known_link_does_not_warn(wired):
    (wired.root / "docs" / "flow.md").write_text("---\ntitle: Flow\nx-id: FLOW-k3f9\n---\n# Flow\n", encoding="utf-8")
    mk(wired, "WI-1", "Linky", documentation=["FLOW-k3f9#a"], **{"x-uid": "link0001"})
    put_board({"WI-1": card("link0001")})
    assert run_repair()["warnings"] == []


def test_idempotent(wired):
    mk(wired, "WI-9", "Hand made", status="Ready")
    mk(wired, "WI-5", "Older", **{"x-uid": "aaaa1111"})
    mk(wired, "WI-5", "Newer", **{"x-uid": "bbbb2222", "created_date": "2026-10-01 11:00"})
    first = run_repair()
    assert {k: c["uid"] for k, c in get_board().items() if k != "WI-9"} == {"WI-5": "aaaa1111", "WI-10": "bbbb2222"}
    assert first["changed"]
    status = git(wired.root, "status", "--porcelain", "backlog")
    snap = snapshot(wired.root)
    second = run_repair()
    assert second["changed"] == []
    assert git(wired.root, "status", "--porcelain", "backlog") == status
    assert snap == snapshot(wired.root)


def test_checkpoint_commits_backlog(wired):
    from lib.kanban import ops
    ops.add("task", "Committed")
    assert wired.env.checkpoint_commit("x") is True
    files = git(wired.root, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert "backlog/board.yaml" in files and any(f.startswith("backlog/tasks/wi-1") for f in files)


def test_checkpoint_repairs_first(wired):
    mk(wired, "WI-9", "Hand made", status="Ready")
    assert wired.env.checkpoint_commit("x") is True
    assert "WI-9" in (wired.root / "backlog" / "board.yaml").read_text(encoding="utf-8")
    assert git(wired.root, "status", "--porcelain", "backlog") == ""


def test_checkpoint_survives_a_failing_repair(wired, monkeypatch, capsys):
    from lib.kanban import repair

    def boom(**_):
        raise RuntimeError("boom")

    monkeypatch.setattr(repair, "repair", boom)
    (wired.root / "docs" / "new.md").write_text("# New\n", encoding="utf-8")
    assert wired.env.checkpoint_commit("x") is True
    assert "boom" in capsys.readouterr().err


def test_install_state_repair_restores_the_driver(wired):
    from lib import install_state
    subprocess.run(["git", "config", "--local", "--unset", "merge.camaron-board.driver"], cwd=wired.root, check=True)
    install_state.repair(log=lambda _: None)
    assert "board merge-driver" in git(wired.root, "config", "merge.camaron-board.driver")


def test_project_without_backlog_unchanged(wired):
    import shutil
    shutil.rmtree(wired.root / "backlog")                 # the wired fixture gets a board; this project has none
    attrs = wired.root / ".gitattributes"
    attrs.unlink(missing_ok=True)
    for key in ("name", "driver"):
        subprocess.run(["git", "config", "--local", "--unset", f"merge.camaron-board.{key}"], cwd=wired.root)
    git(wired.root, "add", "-A")
    git(wired.root, "commit", "-q", "-m", "no board")
    attrs.write_text("*.png binary\n", encoding="utf-8")            # a user's own file, untracked
    (wired.root / "docs" / "new.md").write_text("# New\n", encoding="utf-8")
    assert wired.env.checkpoint_commit("x") is True
    from lib import install_state
    install_state.repair(log=lambda _: None)
    assert not (wired.root / "backlog").exists()
    assert attrs.read_text(encoding="utf-8") == "*.png binary\n"
    assert ".gitattributes" not in git(wired.root, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert git(wired.root, "config", "--local", "--get", "merge.camaron-board.driver") == ""


def test_share_repairs_after_the_pull_and_commits(kit, tmp_path):
    from test_team_repo import bare, publish
    remote = bare(tmp_path)
    publish(kit, remote)
    mate, _ = kit.projects.join(str(remote), tmp_path / "mate")
    hand = mate / "backlog" / "tasks" / "wi-9 - Hand made.md"
    hand.parent.mkdir(parents=True, exist_ok=True)
    hand.write_text("---\nid: WI-9\ntitle: Hand made\nstatus: Ready\n---\n\n## Description\nx\n", encoding="utf-8")
    git(mate, "add", "-A")
    git(mate, "commit", "-q", "-m", "hand made item")
    git(mate, "push", "-q", "origin", "main")
    s = kit.env.share(log=lambda _: None)
    assert s["status"] == "pushed", s
    assert git(kit.root, "log", "-1", "--format=%s") == "docs(camarones): board repaired after sync"
    assert "WI-9" in (kit.root / "backlog" / "board.yaml").read_text(encoding="utf-8")
    assert git(kit.root, "status", "--porcelain", "backlog") == ""
    assert git(kit.root, "rev-parse", "HEAD") == git(kit.root, "rev-parse", "origin/main")
