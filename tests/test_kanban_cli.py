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


# ── board story lint | invest | split ────────────────────────────────────────────────────────────────────────────

_P = "src/main/java/demo/shop/"
_ORDER, _PAY, _WEB = (f"api:{_P}{p}" for p in ("orders/OrderService.java", "payments/PaymentClient.java",
                                               "web/OrderResource.java"))
_TEXT = "Como responsable de pedidos,\nquiero cobrar los pedidos con tarjeta,\npara no perder ventas."


def _story_world(kit, touches=(_ORDER, _PAY), description=_TEXT):
    """A board with story WI-1 and a code graph of `api` (orders, payments, web) with real files behind it."""
    from test_codemap import node, write_graph
    from lib.kanban import ops
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)
    assert cli(kit, "board", "init").returncode == 0
    write_graph(kit, graph={"built_at_commit": "abc1234", "links": [
        {"source": "web", "target": "order", "relation": "calls"}, {"source": "order", "target": "pay", "relation": "calls"}],
        "nodes": [node("order", "OrderService", _P + "orders/OrderService.java", True),
                  node("pay", "PaymentClient", _P + "payments/PaymentClient.java", True),
                  node("web", "OrderResource", _P + "web/OrderResource.java", True)]})
    for rel in ("orders/OrderService.java", "payments/PaymentClient.java", "web/OrderResource.java"):
        f = kit.ws / "api" / _P / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("class X {}\n", encoding="utf-8")
    ops.add("story", "Cobrar", touches=list(touches), description=description,
            criteria=["Dado un pedido, cuando pago, entonces veo el recibo"])
    return kit


def _json(kit, *args):
    r = cli(kit, "board", "story", *args, "--json")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_story_lint_json_is_the_hint_list_and_touch_changes_it(wired):
    _story_world(wired, touches=())
    from lib import stories
    hints = _json(wired, "lint", "WI-1")
    assert [h["code"] for h in hints] == [h["code"] for h in stories.lint(
        "responsable de pedidos", "cobrar los pedidos con tarjeta", "no perder ventas", "es", touches=())]
    assert "no-footprint" in [h["code"] for h in hints]
    assert "no-footprint" not in [h["code"] for h in _json(wired, "lint", "WI-1", "--touch", _ORDER)]
    human = cli(wired, "board", "story", "lint", "WI-1")
    assert human.returncode == 0 and "🦐" not in human.stdout and len(human.stdout.strip().splitlines()) >= 1


def test_story_invest_json_has_the_verdict_and_agrees_with_analyze(wired):
    _story_world(wired)
    got = _json(wired, "invest", "WI-1")
    assert got["verdict"] in ("good", "improve", "poor") and set(got["letters"]) == set("INVEST")
    from lib import stories, stories_save
    s = stories_save.item("WI-1")
    story = {k: s[k] for k in ("id", "as_", "want", "so", "criteria", "touches", "epic", "priority")}
    from lib.kanban import ops
    assert got == stories.analyze(story, lang=ops.docs_lang())["invest"]
    human = cli(wired, "board", "story", "invest", "WI-1").stdout
    assert all(letter in human for letter in "INVEST")
    bare = _json(wired, "invest", "WI-1", "--touch", _WEB)
    assert bare["verdict"] in ("good", "improve", "poor")


def test_story_split_json_lists_proposals_with_waves_and_human_lines(wired):
    _story_world(wired)
    tasks = _json(wired, "split", "WI-1")
    assert [t["key"] for t in tasks] == ["change:api:payments", "change:api:orders"]
    assert [t["wave"] for t in tasks] == [0, 1] and tasks[1]["deps"] == ["change:api:payments"]
    human = cli(wired, "board", "story", "split", "WI-1")
    assert human.returncode == 0 and human.stderr == ""
    lines = human.stdout.splitlines()
    assert lines[0].startswith("wave 1  ") and _PAY in lines[0] and "deps:" not in lines[0]
    assert lines[1].startswith("wave 2  ") and "deps: change:api:payments" in lines[1]
    assert cli(wired, "board", "list").stdout.count("\n") == 1          # nothing was saved


def test_story_split_accept_saves_every_proposal(wired):
    _story_world(wired)
    got = _json(wired, "split", "WI-1", "--accept")
    assert got["story"]["id"] == "WI-1" and [t["id"] for t in got["tasks"]] == ["WI-2", "WI-3"]
    assert got["tasks"][1]["dependencies"] == ["WI-2"]
    rows = json.loads(cli(wired, "board", "list", "--json").stdout)["cards"]
    assert sorted(r["id"] for r in rows) == ["WI-1", "WI-2", "WI-3"]
    again = cli(wired, "board", "story", "split", "WI-1", "--accept")       # it has subtasks now: no duplicates
    assert again.returncode == 2 and again.stderr.startswith("✖") and again.stdout == ""


def test_story_split_accept_human_prints_the_new_ids(wired):
    _story_world(wired)
    r = cli(wired, "board", "story", "split", "WI-1", "--accept")
    assert r.returncode == 0, r.stderr
    assert "WI-2" in r.stdout and "WI-3" in r.stdout and r.stdout.count("🦐") <= 1


def test_story_split_accept_refuses_a_cycle_or_duplicates(wired, monkeypatch, capsys):
    import argparse
    _story_world(wired)
    from lib import stories
    from lib.kanban import cli as board_cli
    p = argparse.ArgumentParser()
    board_cli.add_parser(p.add_subparsers(dest="cmd"))
    args = p.parse_args(["board", "story", "split", "WI-1", "--accept"])
    real = stories.analyze
    for bad in ({"cycle": ["a", "b"]}, {"duplicates": ["a"]}):
        monkeypatch.setattr(stories, "analyze", lambda *a, _b=bad, **k: {**real(*a, **k), **_b})
        assert board_cli.run(args) == 2
        out = capsys.readouterr()
        assert out.err.startswith("✖") and len(out.err.strip().splitlines()) == 1 and out.out == ""
    assert cli(wired, "board", "list").stdout.count("\n") == 1


def test_story_errors_are_plain_and_exit_2(wired):
    _story_world(wired)
    for args in (("bogus", "WI-1"), ("lint",), ("lint", "WI-1", "x")):
        r = cli(wired, "board", "story", *args)
        assert r.returncode == 2 and r.stdout == "", args
        assert r.stderr.startswith("✖ usage: camaron board story lint|invest|split ID"), (args, r.stderr)
    r = cli(wired, "board", "story")
    assert r.returncode == 2 and "story lint|invest|split ID" in r.stderr
    for args in (("lint", "WI-99"), ("lint", "WI-1", "--touch", "api:nope/missing/x.java"),
                 ("lint", "WI-1", "--touch", "nowhere:x")):
        r = cli(wired, "board", "story", *args, "--json")
        assert r.returncode == 2 and r.stdout == "" and r.stderr.startswith("✖") and "🦐" not in r.stderr, args
    cli(wired, "board", "add", "task", "Plain")
    r = cli(wired, "board", "story", "lint", "WI-2")
    assert r.returncode == 2 and "not a story" in r.stderr
