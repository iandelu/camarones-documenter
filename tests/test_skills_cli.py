import json
import os
import shutil
import subprocess
import sys

from conftest import KIT_DIR


def cli(kit, *args):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "skills", *args], env=env,
                          capture_output=True, text=True, encoding="utf-8")


def test_list_fork_diff_reset_from_the_command_line(wired):
    (wired.root / ".camarones" / "skills" / "My Skill").mkdir(parents=True)
    (wired.root / ".camarones" / "skills" / "My Skill" / "SKILL.md").write_text("x", encoding="utf-8")
    assert "· skipped .camarones/skills/My Skill: invalid name" in cli(wired, "list").stderr
    r = cli(wired, "list", "--json")
    assert r.returncode == 0, r.stderr
    rows = {s["name"]: s for s in json.loads(r.stdout)["skills"]}
    assert rows["cam-docs-update"]["origin"] == "kit" and rows["cam-docs-update"]["description"]
    assert cli(wired, "fork", "cam-docs-update").stdout.startswith("✔ team copy of cam-docs-update: .camarones/skills/")
    assert cli(wired, "diff", "cam-docs-update").stdout.strip() == "cam-docs-update: same as the kit"
    assert "follows the kit again" in cli(wired, "reset", "cam-docs-update").stdout


def test_note_and_notes(wired):
    r = cli(wired, "note", "cam-docs-update", "the", "check", "step", "came", "too", "late", "--source", "retro",
            "--step", "verify", "--change", "wi-12")
    assert r.returncode == 0, r.stderr
    out = cli(wired, "notes").stdout
    assert "cam-docs-update (1)" in out and "  verify (1)" in out and "the check step came too late" in out
    assert json.loads(cli(wired, "notes", "--json").stdout)[0]["change"] == "wi-12"


def test_bad_input_is_one_line_and_exit_2(wired):
    for args in (("note", "nope", "x", "--source", "retro"), ("note", "cam-docs-update", "x", "--source", "chat"),
                 ("note", "cam-docs-update", "x"), ("fork",), ("list", "--kit"),
                 ("diff", "cam-docs-update", "--source", "retro")):
        r = cli(wired, *args)
        assert r.returncode == 2 and r.stderr.startswith("✖") and len(r.stderr.strip().splitlines()) == 1, args
    assert not (wired.root / "docs" / ".work" / "skill-notes").exists()


def test_fork_reset_and_note_print_data_with_json(wired):
    r = cli(wired, "fork", "cam-docs-update", "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"name": "cam-docs-update", "path": ".camarones/skills/cam-docs-update"}
    r = cli(wired, "reset", "cam-docs-update", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["name"] == "cam-docs-update" and data["path"].startswith(".camarones/skills/.reset/cam-docs-update-")
    r = cli(wired, "note", "cam-docs-update", "too", "late", "--source", "retro", "--json")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == {"skill": "cam-docs-update", "path": "docs/.work/skill-notes/cam-docs-update.md"}


def test_fork_renders_only_where_the_kit_wires_the_agents(wired):
    ws = wired.docs.workspace()
    ws["project"]["components"] = ["quality"]
    wired.docs.save_workspace(ws)
    shutil.rmtree(wired.root / ".claude" / "skills")
    r = cli(wired, "fork", "cam-docs-update")
    assert r.returncode == 0, r.stderr
    assert not (wired.root / ".claude" / "skills").exists()
