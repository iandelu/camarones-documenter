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
