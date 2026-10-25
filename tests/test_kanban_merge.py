from __future__ import annotations

import subprocess
import sys


def card(uid="aaaaaaaa", status="Ready", ordinal=1000, assignee=(), t=None):
    return {"uid": uid, "status": status, "ordinal": ordinal, "assignee": list(assignee), "t": dict(t or {})}


def merged(kit, base, ours, theirs):
    from lib.kanban.merge import merge_boards
    from lib.kanban.state import dump_board, load_board
    text, log = merge_boards(dump_board(base), dump_board(ours), dump_board(theirs))
    return load_board(text), log, text


def test_change_on_one_side_wins(kit):
    base = {"WI-1": card()}
    ours = {"WI-1": card(status="In Progress", t={"status": "2026-10-24T10:00:00Z ana"})}
    out, log, _ = merged(kit, base, ours, base)
    assert out["WI-1"]["status"] == "In Progress"
    assert out["WI-1"]["t"]["status"] == "2026-10-24T10:00:00Z ana"


def test_both_sides_latest_stamp_wins_per_field(kit):
    base = {"WI-1": card()}
    ours = {"WI-1": card(status="In Progress", t={"status": "2026-10-24T10:00:00Z ana"})}
    theirs = {"WI-1": card(status="Done", assignee=["luis"],
                           t={"status": "2026-10-24T11:00:00Z luis", "assignee": "2026-10-24T09:00:00Z luis"})}
    out, _, _ = merged(kit, base, ours, theirs)
    assert out["WI-1"]["status"] == "Done"
    assert out["WI-1"]["assignee"] == ["luis"]
    assert out["WI-1"]["t"]["status"] == "2026-10-24T11:00:00Z luis"


def test_tie_is_deterministic(kit):
    base = {"WI-1": card()}
    a = {"WI-1": card(status="In Progress", t={"status": "2026-10-24T10:00:00Z ana"})}
    b = {"WI-1": card(status="Done", t={"status": "2026-10-24T10:00:00Z luis"})}
    one = merged(kit, base, a, b)
    two = merged(kit, base, b, a)
    assert one[2] == two[2]
    assert one[0]["WI-1"]["status"] == "Done"      # same stamp: the larger author wins
    c = {"WI-1": card(status="Blocked", t={"status": "2026-10-24T10:00:00Z ana"})}
    assert merged(kit, base, a, c)[2] == merged(kit, base, c, a)[2]
    assert merged(kit, base, a, c)[0]["WI-1"]["status"] == "In Progress"     # same author: the larger value


def test_same_id_added_on_both_sides_keeps_both(kit):
    base = {}
    old = card("aaaaaaaa", t={"status": "2026-10-24T09:00:00Z ana"})
    new = card("bbbbbbbb", t={"status": "2026-10-24T10:00:00Z luis"})
    out, log, text = merged(kit, base, {"WI-5": new}, {"WI-5": old})
    assert out["WI-5"]["uid"] == "aaaaaaaa"
    assert out["WI-5~bbbbbbbb"]["uid"] == "bbbbbbbb"
    assert log
    assert text == merged(kit, base, {"WI-5": old}, {"WI-5": new})[2]


def test_delete_vs_change_keeps_the_change(kit):
    base = {"WI-1": card("11111111"), "WI-2": card("22222222")}
    ours = {"WI-1": card("11111111")}
    theirs = {"WI-1": card("11111111"), "WI-2": card("22222222", status="Done", t={"status": "2026-10-24T10:00:00Z luis"})}
    out, log, _ = merged(kit, base, ours, theirs)
    assert out["WI-2"]["status"] == "Done"
    assert any("WI-2" in line for line in log)


def test_delete_of_an_unchanged_card_is_honoured(kit):
    base = {"WI-1": card("11111111"), "WI-2": card("22222222")}
    out, _, _ = merged(kit, base, {"WI-1": card("11111111")}, base)
    assert list(out) == ["WI-1"]


def test_unparsable_side_raises_and_driver_leaves_ours(kit, tmp_path):
    from lib.kanban.merge import driver, merge_boards
    from lib.kanban.state import dump_board
    good = dump_board({"WI-1": card()})
    for bad in ("<<<<<<< ours\nversion: 1\n", "version: 1\ncards:\n  WI-1: {uid: a, status: S, ordinal: 1, t: 5}\n"):
        try:
            merge_boards(good, bad, good)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
        b, o, t = tmp_path / "b", tmp_path / "o", tmp_path / "t"
        b.write_text(good, encoding="utf-8")
        o.write_text(bad, encoding="utf-8")
        t.write_text(good, encoding="utf-8")
        assert driver(b, o, t) == 1
        assert o.read_text(encoding="utf-8") == bad


def test_driver_writes_ours_and_accepts_empty_base(kit, tmp_path):
    from lib.kanban.merge import driver
    from lib.kanban.state import dump_board, load_board
    b, o, t = tmp_path / "b", tmp_path / "o", tmp_path / "t"
    b.write_text("", encoding="utf-8")
    o.write_text(dump_board({"WI-1": card()}), encoding="utf-8")
    t.write_text(dump_board({"WI-2": card("22222222")}), encoding="utf-8")
    assert driver(b, o, t) == 0
    assert list(load_board(o.read_text(encoding="utf-8"))) == ["WI-1", "WI-2"]


def test_driver_command_quotes_spaces(kit):
    from lib.kanban.merge import driver_command
    cmd = driver_command(["C:/Users/Ana María/uv.exe", "run", "--quiet", "--script", "C:/kit dir/camarones.py"])
    assert cmd == ('"C:/Users/Ana María/uv.exe" "run" "--quiet" "--script" "C:/kit dir/camarones.py" '
                   'board merge-driver %O %A %B')
    assert driver_command(["C:\\kit dir\\x.exe"]).startswith('"C:/kit dir/x.exe"')


def test_real_git_merge_uses_the_driver(kit, tmp_path):
    from lib.kanban.merge import driver_command
    from lib.kanban.state import dump_board, load_board
    wrapper = tmp_path / "kit dir" / "driver.py"
    wrapper.parent.mkdir()
    wrapper.write_text(
        "import sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(kit.kit_dir)!r})\n"
        "from lib.kanban.merge import driver\n"
        "sys.exit(driver(*[Path(a) for a in sys.argv[-3:]]))\n", encoding="utf-8")
    repo = tmp_path / "repo"
    (repo / "backlog").mkdir(parents=True)

    def git(*args):
        r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, (args, r.stdout, r.stderr)
        return r.stdout

    git("init", "-q", "-b", "main")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    git("config", "merge.camaron-board.name", "Camarón board (per card)")
    git("config", "merge.camaron-board.driver", driver_command([sys.executable, str(wrapper)]))
    (repo / ".gitattributes").write_text("backlog/board.yaml merge=camaron-board\n", encoding="utf-8", newline="\n")
    board = repo / "backlog" / "board.yaml"
    base = {"WI-1": card("11111111"), "WI-2": card("22222222", ordinal=2000), "WI-3": card("33333333", ordinal=3000)}
    board.write_text(dump_board(base), encoding="utf-8", newline="\n")
    git("add", ".")
    git("commit", "-qm", "base")
    git("checkout", "-qb", "other")
    other = dict(base, **{"WI-2": card("22222222", "Done", 2000, t={"status": "2026-10-24T10:00:00Z luis"})})
    board.write_text(dump_board(other), encoding="utf-8", newline="\n")
    git("commit", "-qam", "luis")
    git("checkout", "-q", "main")
    mine = dict(base, **{"WI-1": card("11111111", "In Progress", 1000, t={"status": "2026-10-24T09:00:00Z ana"})})
    board.write_text(dump_board(mine), encoding="utf-8", newline="\n")
    git("commit", "-qam", "ana")
    git("merge", "-q", "other", "-m", "merge")
    out = load_board(board.read_text(encoding="utf-8"))
    assert out["WI-1"]["status"] == "In Progress"
    assert out["WI-2"]["status"] == "Done"
