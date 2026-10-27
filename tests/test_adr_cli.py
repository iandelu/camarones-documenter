"""`camaron adr`: the CLI over lib/adr.py and lib/adr_pack.py. The subprocess tests prove the command is wired into
camarones.py and prints what a script reads; the `call` ones run the same command in this process, which is what the many
small argument checks need (a subprocess is a second each)."""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys

import pytest


def cli(kit, *args):
    e = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "adr", *args], env=e, capture_output=True,
                          text=True, encoding="utf-8")


def call(capsys, *argv):
    """`camaron adr …` in this process: the kit fixture has pointed `lib` at the test project."""
    import argparse
    from lib import adr_cli
    parser = argparse.ArgumentParser()
    adr_cli.add_parser(parser.add_subparsers(dest="cmd"))
    code = adr_cli.run(parser.parse_args(["adr", *argv]))
    seen = capsys.readouterr()
    return code, seen.out, seen.err


@pytest.fixture
def adr(kit):
    return importlib.import_module("lib.adr")


def decided(adr):
    """An ADR written to a file, with the Decision a person typed: ready to accept."""
    a = adr.write_without_ai(adr.new({"title": "Sessions in Redis", "kind": "new"})["id"])
    return adr.part(a["id"], "decision", "edit", "Keep sessions in Redis.", base_sha=a["sha"])


def test_new_list_and_show(kit):
    r = cli(kit, "new", "Sessions in Redis", "--kind", "new", "--touch", "api:pom.xml", "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["id"] == "0001"
    assert "0001  running  Sessions in Redis" in cli(kit, "list").stdout
    assert json.loads(cli(kit, "show", "0001", "--json").stdout)["state"]["touches"] == ["api:pom.xml"]


def test_accept_needs_a_file_and_a_decision(kit):
    cli(kit, "new", "A", "--kind", "retro")
    r = cli(kit, "accept", "0001")
    assert r.returncode == 2 and "camaron adr write 0001" in r.stderr
    assert cli(kit, "write", "0001").returncode == 0
    r = cli(kit, "accept", "0001")
    assert r.returncode == 2 and r.stderr.startswith("✖") and "write the Decision section" in r.stderr


def test_the_catalog_knows_adr(kit):
    from lib import catalog
    assert catalog.COMMANDS["adr"]["verdict"] == "app"
    assert catalog.COMMANDS["adr"]["zone"] == "team"


def test_accept_decides_as_the_git_user_and_takes_the_attendees_given(kit, adr):
    decided(adr)
    r = cli(kit, "accept", "0001", "--attendee", "LA", "--attendee", "MP", "--json")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["status"] == "accepted" and out["state"]["decided"]["by"] == "Test"
    assert "LA, MP" in out["sections"]["decided_by"]
    fm, _ = kit.docs.split_fm((kit.root / "docs" / out["path"]).read_text(encoding="utf-8"))
    assert fm["x-owner"] == "human" and fm["x-confirmed"]["by"] == "Test"
    assert "0001  accepted  Sessions in Redis" in cli(kit, "list").stdout


def test_pack_gathers_the_evidence_of_a_project_without_a_graph(kit):
    cli(kit, "new", "Sessions", "--kind", "new", "--touch", "api:pom.xml")
    r = cli(kit, "pack", "0001")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() != ""
    out = json.loads(cli(kit, "pack", "0001", "--json").stdout)
    assert set(out) == {"summary", "markdown"} and out["markdown"].strip() != ""
    assert json.loads(cli(kit, "show", "0001", "--json").stdout)["state"]["phase"] == "evidence"


def test_candidates_print_one_line_per_decision_the_code_took(kit):
    from lib.common import WORK, save_json
    row = dict(ecosystem="maven", version="1", declared="1", language="java", scope="runtime", category="cache")
    save_json(WORK / "inventory.json", {"libraries": [
        {**row, "repo": "api", "name": "redis.clients:jedis", "source": "api:pom.xml"},
        {**row, "repo": "web", "name": "redis.clients:jedis", "source": "web:pom.xml"}]})
    plain = cli(kit, "candidates")
    assert plain.returncode == 0 and plain.stdout.splitlines() == ["cache  jedis  [api, web]"]
    [one] = json.loads(cli(kit, "candidates", "--json").stdout)
    assert one["key"] == "cache:jedis" and one["repos"] == ["api", "web"]


def test_an_unknown_action_is_argparses_error(kit):
    r = cli(kit, "burn")
    assert r.returncode == 2 and "invalid choice" in r.stderr


# ---------- in this process ----------
def test_a_title_may_be_several_words_and_flags_reach_the_framing(kit, capsys):
    code, out, _ = call(capsys, "new", "Sessions", "in", "Redis", "--kind", "retro", "--problem", "why it is there",
                        "--touch", "api:a.java", "--touch", "web:b.ts", "--supersedes", "3", "--json")
    state = json.loads(out)["state"]
    assert code == 0
    assert (state["title"], state["kind"], state["problem"], state["supersedes"]) == (
        "Sessions in Redis", "retro", "why it is there", "0003")
    assert state["touches"] == ["api:a.java", "web:b.ts"]


def test_new_without_a_kind_or_a_title_is_refused_plainly(kit, capsys):
    assert call(capsys, "new", "A") == (2, "", "✖ kind must be one of new, retro\n")
    assert call(capsys, "new", "--kind", "new") == (2, "", "✖ usage: camaron adr new TITLE --kind new|retro\n")
    assert call(capsys, "list", "--json")[1].strip() == "[]"


def test_list_prints_a_line_per_adr_and_json_is_the_functions_result(kit, capsys):
    call(capsys, "new", "A", "--kind", "new")
    call(capsys, "new", "B", "--kind", "retro")
    assert call(capsys, "list") == (0, "0002  running  B\n0001  running  A\n", "")
    rows = json.loads(call(capsys, "list", "--json")[1])
    assert [(r["id"], r["chip"], r["title"]) for r in rows] == [("0002", "running", "B"), ("0001", "running", "A")]


def test_a_project_without_decisions_lists_nothing_and_says_how_to_start(kit, capsys):
    code, out, err = call(capsys, "list")
    assert code == 0 and out == "" and "camaron adr new" in err and "🦐" not in err


def test_a_project_without_candidates_is_an_empty_list_not_an_error(kit, capsys):
    assert call(capsys, "candidates", "--json") == (0, "[]\n", "")
    code, out, err = call(capsys, "candidates")
    assert code == 0 and out == "" and err.strip() != ""


def test_write_creates_the_proposed_file_and_says_so(kit, capsys):
    call(capsys, "new", "Sessions in Redis", "--kind", "new")
    assert call(capsys, "write", "0001") == (0, "0001  review  Sessions in Redis\n", "")
    assert [f.name for f in (kit.root / "docs" / "decisions").glob("0001-*.md")] == ["0001-sessions-in-redis.md"]
    assert json.loads(call(capsys, "write", "0001", "--json")[1])["path"] == "decisions/0001-sessions-in-redis.md"


def test_write_tells_a_script_the_number_it_ended_up_with(kit, capsys):
    call(capsys, "new", "Sessions", "--kind", "new")
    folder = kit.root / "docs" / "decisions"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "0001-taken.md").write_text("# 0001 — Taken\n\n## Status\n\nAccepted\n", encoding="utf-8")
    assert call(capsys, "write", "0001") == (0, "0002  review  Sessions\nrenumbered 0001 -> 0002\n", "")


def test_accept_without_attendees_keeps_those_of_the_review(kit, adr, capsys):
    a = decided(adr)
    adr.set_attendees(a["id"], ["AB"])
    code, out, _ = call(capsys, "accept", "0001", "--json")
    assert code == 0 and json.loads(out)["state"]["attendees"] == ["AB"]


def test_reject_needs_a_reason_and_records_it(kit, adr, capsys):
    decided(adr)
    code, out, err = call(capsys, "reject", "0001")
    assert (code, out) == (2, "") and err.startswith("✖") and "reason" in err
    assert call(capsys, "reject", "0001", "--why", "the team already runs Postgres") == (
        0, "0001  rejected  Sessions in Redis\n", "")
    shown = json.loads(call(capsys, "show", "0001", "--json")[1])
    assert shown["sections"]["status"] == f"Rejected ({shown['state']['decided']['date']}): the team already runs Postgres"


def test_a_decided_adr_cannot_be_decided_twice(kit, adr, capsys):
    decided(adr)
    assert call(capsys, "accept", "0001")[0] == 0
    code, _, err = call(capsys, "reject", "0001", "--why", "changed my mind")
    assert code == 2 and "already accepted" in err


def test_a_stale_save_is_one_plain_line_too(kit, adr, capsys, monkeypatch):
    """Between reading the sha and saving, a pull or an editor changes the file: nothing is overwritten."""
    a = decided(adr)
    real = adr.accept

    def late(id, by, attendees, base_sha):
        (kit.root / "docs" / a["path"]).write_text(a["raw"].replace("Keep sessions in Redis.", "Changed."), encoding="utf-8")
        return real(id, by, attendees, base_sha)
    monkeypatch.setattr(adr, "accept", late)
    code, out, err = call(capsys, "accept", "0001")
    assert (code, out) == (2, "") and err == "✖ 0001 changed while you were editing it: reload it\n"
    assert "Changed." in (kit.root / "docs" / a["path"]).read_text(encoding="utf-8")


def test_show_prints_the_row_and_the_file(kit, adr, capsys):
    decided(adr)
    out = call(capsys, "show", "0001")[1]
    assert out.splitlines()[0] == "0001  review  Sessions in Redis"
    assert "## Decision" in out and "Keep sessions in Redis." in out


def test_show_of_an_adr_with_no_file_prints_its_problem(kit, capsys):
    call(capsys, "new", "A", "--kind", "retro", "--problem", "nobody remembers why")
    out = call(capsys, "show", "0001")[1]
    assert out.splitlines()[0] == "0001  running  A" and "nobody remembers why" in out


def test_an_id_is_read_with_or_without_its_zeros(kit, capsys):
    call(capsys, "new", "A", "--kind", "new")
    assert call(capsys, "show", "1")[1].startswith("0001  running  A\n")
    assert call(capsys, "show", "0001")[0] == 0


@pytest.mark.parametrize("args", [("show", "0042"), ("pack", "0042"), ("write", "0042"), ("accept", "0042"),
                                  ("reject", "0042", "--why", "x"), ("show", "x/../y")])
def test_an_unknown_adr_is_one_plain_line(kit, capsys, args):
    code, out, err = call(capsys, *args)
    assert code == 2 and out == ""
    assert err.startswith("✖ no ADR ") and err.count("\n") == 1 and "🦐" not in err


@pytest.mark.parametrize("args, flag, only", [
    (("show", "0001", "--why", "x"), "--why", "reject"),
    (("show", "0001", "--attendee", "LA"), "--attendee", "accept"),
    (("reject", "0001", "--kind", "new"), "--kind", "new"),
    (("list", "--touch", "api:a.java"), "--touch", "new"),
    (("accept", "0001", "--supersedes", "2"), "--supersedes", "new"),
    (("accept", "0001", "--problem", "x"), "--problem", "new"),
])
def test_a_flag_for_another_action_is_an_error_not_ignored(kit, capsys, args, flag, only):
    assert call(capsys, *args) == (2, "", f"✖ {flag} only goes with: {only}\n")


@pytest.mark.parametrize("args", [("show",), ("show", "0001", "0002"), ("pack",), ("write",), ("accept",),
                                  ("reject",), ("list", "extra"), ("candidates", "extra")])
def test_wrong_arguments_say_the_usage(kit, capsys, args):
    code, out, err = call(capsys, *args)
    assert code == 2 and out == "" and err.startswith(f"✖ usage: camaron adr {args[0]}")
