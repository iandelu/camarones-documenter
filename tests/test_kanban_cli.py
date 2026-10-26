"""`camaron board`: the CLI over lib/kanban. Run as subprocesses, like the other command tests."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys


def cli(kit, *args, cwd=None, root=True):
    e = {**os.environ}
    if root:
        e["CAMARONES_ROOT"] = str(kit.root)
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), *args], env=e, capture_output=True,
                          text=True, encoding="utf-8", cwd=cwd)


def test_board_flow_json(wired):
    subprocess.run(["git", "init", "-q", str(wired.root)], check=True)
    assert cli(wired, "board", "init").returncode == 0
    r = cli(wired, "board", "add", "story", "Pay twice", "--repo", "api", "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["id"] == "WI-1"
    assert cli(wired, "board", "move", "WI-1", "Ready", "--json").returncode == 0
    cards = json.loads(cli(wired, "board", "list", "--status", "Ready", "--json").stdout)["cards"]
    assert [c["id"] for c in cards] == ["WI-1"]
    shown = json.loads(cli(wired, "board", "show", "WI-1", "--json").stdout)
    assert "criteria" in shown
    assert cli(wired, "board", "list").stdout.strip() == "WI-1  Ready  -  Pay twice  [api]"


def test_errors_are_plain_and_exit_2(wired):
    subprocess.run(["git", "init", "-q", str(wired.root)], check=True)
    cli(wired, "board", "init")
    r = cli(wired, "board", "move", "WI-99", "Ready")
    assert r.returncode == 2
    assert r.stderr.startswith("✖") and "🦐" not in r.stderr + r.stdout


def test_board_before_init_says_how(wired):
    shutil.rmtree(wired.root / "backlog", ignore_errors=True)       # a project from before the board (new ones start with it)
    r = cli(wired, "board", "list")
    assert r.returncode == 2 and "board init" in r.stderr


def test_empty_board_has_the_one_shrimp_line(wired):
    subprocess.run(["git", "init", "-q", str(wired.root)], check=True)
    cli(wired, "board", "init")
    out = cli(wired, "board", "list").stdout
    assert "🦐" in out and "The board is empty" in out          # English whatever the docs language is
    assert "🦐" not in cli(wired, "board", "list", "--json").stdout


def test_merge_driver_needs_no_workspace(wired, tmp_path):
    from lib.kanban.state import dump_board, load_board
    card = lambda uid: {"uid": uid, "status": "Backlog", "ordinal": 1, "assignee": [], "t": {}}
    d = tmp_path / "nowhere"
    d.mkdir()
    for name, cards in (("O", {}), ("A", {"WI-1": card("u1")}), ("B", {"WI-2": card("u2")})):
        (d / name).write_text(dump_board(cards), encoding="utf-8", newline="\n")
    env = {k: v for k, v in os.environ.items() if k != "CAMARONES_ROOT"}

    def drive():
        return subprocess.run([sys.executable, str(wired.kit_dir / "camarones.py"), "board", "merge-driver", "O", "A", "B"],
                              env=env, cwd=d, capture_output=True, text=True, encoding="utf-8")
    r = drive()
    assert r.returncode == 0, r.stderr
    assert set(load_board((d / "A").read_text(encoding="utf-8"))) == {"WI-1", "WI-2"}
    (d / "B").write_text("{{ not: [yaml", encoding="utf-8")
    before = (d / "A").read_bytes()
    assert drive().returncode == 1
    assert (d / "A").read_bytes() == before


def test_list_takes_one_repo_and_one_label(wired):
    subprocess.run(["git", "init", "-q", str(wired.root)], check=True)
    cli(wired, "board", "init")
    for flags in (("--repo", "a", "--repo", "b"), ("--label", "x", "--label", "y")):
        r = cli(wired, "board", "list", *flags)
        assert r.returncode == 2 and r.stderr.startswith("✖") and "one" in r.stderr


def test_wrong_positional_counts_are_usage_errors(wired):
    subprocess.run(["git", "init", "-q", str(wired.root)], check=True)
    cli(wired, "board", "init")
    cli(wired, "board", "add", "story", "Pay twice")
    for args in (("show", "WI-1", "junk"), ("move", "WI-1", "Ready", "x"), ("assign", "WI-1"), ("archive", "WI-1", "x"),
                 ("list", "junk"), ("repair", "junk"), ("init", "junk"), ("add", "story")):
        r = cli(wired, "board", *args)
        assert r.returncode == 2 and r.stderr.startswith("✖ usage"), args
    assert cli(wired, "board", "list").stdout.count("WI-1") == 1


def test_docs_check_ignores_the_board(wired):
    subprocess.run(["git", "init", "-q", str(wired.root)], check=True)
    cli(wired, "board", "init")
    cli(wired, "board", "add", "story", "Pay twice", "--repo", "api")
    r = cli(wired, "check")
    assert "backlog" not in r.stdout + r.stderr


def test_a_busy_lock_or_a_file_error_is_one_plain_line(wired, monkeypatch, capsys):
    import argparse
    from pathlib import Path
    from lib.harness.locks import LockBusy
    from lib.kanban import cli as board_cli, ops
    p = argparse.ArgumentParser()
    board_cli.add_parser(p.add_subparsers(dest="cmd"))
    args = p.parse_args(["board", "move", "WI-1", "Ready"])

    def busy(*_a, **_k):
        raise LockBusy(Path("board.lock"), {"pid": 42})
    monkeypatch.setattr(ops, "move", busy)
    assert board_cli.run(args) == 2
    assert capsys.readouterr().err == "✖ board.lock is held by pid 42 on this machine\n"

    def denied(*_a, **_k):
        raise PermissionError(13, "Access is denied", "wi-1 - x.md")
    monkeypatch.setattr(ops, "move", denied)
    assert board_cli.run(args) == 2
    assert capsys.readouterr().err == "✖ [Errno 13] Access is denied: 'wi-1 - x.md'\n"


def _two_on_one_file(kit):
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)
    assert cli(kit, "board", "init").returncode == 0
    from lib.kanban import ops
    ops.add("task", "First", touches=["api:a.py"])
    ops.add("task", "Second", touches=["api:a.py"])
    ops.add("task", "Third", touches=["api:b.py"])
    assert cli(kit, "board", "move", "WI-1", "In Progress").returncode == 0


def test_move_refused_exits_2_and_force_moves_it(wired):
    _two_on_one_file(wired)
    r = cli(wired, "board", "move", "WI-2", "In Progress")
    assert r.returncode == 2 and r.stdout == ""
    assert r.stderr.startswith("✖") and "WI-1" in r.stderr and "api:a.py" in r.stderr and "--force" in r.stderr
    assert len(r.stderr.strip().splitlines()) == 1 and "🦐" not in r.stderr
    forced = cli(wired, "board", "move", "WI-2", "In Progress", "--force", "--json")
    assert forced.returncode == 0, forced.stderr
    assert json.loads(forced.stdout)["status"] == "In Progress"


def test_board_next_json_and_human(wired):
    _two_on_one_file(wired)
    got = json.loads(cli(wired, "board", "next", "--json").stdout)
    assert [r["id"] for r in got["ready"]] == ["WI-3"] and got["ready"][0]["wave"] == 0
    assert got["waiting"] == [{"id": "WI-2", "blocked_by": [{"id": "WI-1", "kind": "conflict", "files": ["api:a.py"]}]}]
    assert [r["id"] for r in json.loads(cli(wired, "board", "next", "--n", "0", "--json").stdout)["ready"]] == []
    human = cli(wired, "board", "next")
    assert human.returncode == 0
    lines = human.stdout.splitlines()
    assert lines[0].startswith("WI-3  Backlog") and any("WI-2" in l and "api:a.py" in l for l in lines[1:])
    assert any(l.startswith("  · WI-2: ") and ("choca con WI-1 en api:a.py" in l or "collides with WI-1 on api:a.py" in l)
               for l in lines)


def test_board_waves_json_and_cycle(wired):
    _two_on_one_file(wired)
    got = json.loads(cli(wired, "board", "waves", "--json").stdout)
    assert [[r["id"] for r in w] for w in got["waves"]] == [["WI-1", "WI-3"], ["WI-2"]]
    from lib.kanban import ops
    for a, b in (("WI-1", "WI-3"), ("WI-3", "WI-1")):
        item = ops.load_state()[1][a]
        item.fm["dependencies"] = [b]
        ops.save_item(item)
    assert json.loads(cli(wired, "board", "waves", "--json").stdout) == {"cycle": ["WI-1", "WI-3"]}
    r = cli(wired, "board", "waves")
    assert r.returncode == 2 and "WI-1" in r.stderr and "WI-3" in r.stderr


def test_board_next_story_flag(wired):
    subprocess.run(["git", "init", "-q", str(wired.root)], check=True)
    cli(wired, "board", "init")
    from lib.kanban import ops
    ops.add("story", "Story")
    ops.add("task", "Inside", parent="WI-1")
    ops.add("task", "Outside")
    got = json.loads(cli(wired, "board", "next", "--story", "WI-1", "--json").stdout)
    assert "WI-3" not in [r["id"] for r in got["ready"]] and "WI-2" in [r["id"] for r in got["ready"]]
