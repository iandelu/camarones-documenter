import importlib
import shutil
import subprocess
from pathlib import PurePosixPath

import pytest


def skills(kit):
    return importlib.import_module("lib.skills")


def team(kit, name, text="---\nname: x\ndescription: Team text.\n---\n# x\n", extra=None):
    d = kit.root / ".camarones" / "skills" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    for rel, body in (extra or {}).items():
        (d / rel).write_text(body, encoding="utf-8")
    return d


def test_kit_skills_are_listed_with_their_raw_text(kit):
    s = skills(kit)
    assert {"cam-docs-lookup", "cam-docs-update"} <= set(s.kit_names())
    assert "{{CLI}}" in s.kit_files("cam-docs-update")["SKILL.md"]
    assert s.origin("cam-docs-update") == "kit" and s.origin("nope") is None


def test_a_team_copy_wins_and_a_team_only_skill_is_added(kit):
    s = skills(kit)
    team(kit, "cam-docs-update", extra={"notes.md": "n"})
    team(kit, "our-review")
    assert s.origin("cam-docs-update") == "team" and s.origin("our-review") == "team-only"
    src = s.sources()
    assert src["cam-docs-update"]["SKILL.md"].startswith("---\nname: x")
    assert set(src["cam-docs-update"]) == {"SKILL.md", "notes.md"}
    assert "our-review" in src and s.description("our-review") == "Team text."


def test_bad_team_folders_are_skipped_with_a_reason(kit):
    s = skills(kit)
    team(kit, "My Skill"); team(kit, "Cam_Task")
    (kit.root / ".camarones" / "skills" / "empty-one").mkdir()
    (kit.root / ".camarones" / "skills" / ".reset").mkdir()
    assert s.team_names() == []
    assert sorted((i["name"], i["why"]) for i in s.ignored()) == [
        ("Cam_Task", "invalid name"), ("My Skill", "invalid name"), ("empty-one", "no SKILL.md")]


def test_a_team_copy_is_rendered_in_both_hosts_and_repair_keeps_it(wired):
    team(wired, "cam-docs-update", text="---\nname: cam-docs-update\ndescription: Ours.\n---\nUse {{CLI}} check.\n")
    wired.env.write_kit_skills()
    for host in (".claude", ".agents"):
        text = (wired.root / host / "skills" / "cam-docs-update" / "SKILL.md").read_text(encoding="utf-8")
        assert "Ours." in text and "{{CLI}}" not in text
    assert [d for d in importlib.import_module("lib.install_state").drift() if "skills" in d["path"]] == []


def test_a_crlf_team_copy_renders_with_lf(wired):
    d = team(wired, "cam-docs-unit")
    (d / "SKILL.md").write_bytes(b"---\r\nname: cam-docs-unit\r\ndescription: Ours.\r\n---\r\nbody\r\n")
    assert b"\r" not in "".join(wired.env.skill_files().values()).encode("utf-8")
    wired.env.write_kit_skills()
    data = (wired.root / ".claude" / "skills" / "cam-docs-unit" / "SKILL.md").read_bytes()
    assert b"Ours." in data and b"\r" not in data


def test_an_unedited_crlf_fork_stays_the_kits_text(wired):
    trust = importlib.import_module("lib.trust")
    raw = skills(wired).kit_files("cam-docs-update")["SKILL.md"]
    d = team(wired, "cam-docs-update")
    (d / "SKILL.md").write_bytes(raw.replace("\n", "\r\n").encode("utf-8"))
    wired.env.write_kit_skills()
    assert [x for x in importlib.import_module("lib.install_state").drift() if "skills" in x["path"]] == []
    assert [it for it, _ in trust.pending() if "cam-docs-update" in it.id] == []


def test_a_removed_nested_team_skill_leaves_no_folder(wired):
    d = team(wired, "our-deep")
    (d / "references").mkdir()
    (d / "references" / "a.md").write_text("a", encoding="utf-8")
    wired.env.write_kit_skills()
    assert (wired.root / ".agents" / "skills" / "our-deep" / "references" / "a.md").is_file()
    shutil.rmtree(d)
    wired.env.write_kit_skills()
    for host in (".claude", ".agents"):
        assert not (wired.root / host / "skills" / "our-deep").exists()
        assert (wired.root / host / "skills").is_dir()


def test_a_removed_team_skill_leaves_no_rendered_copy_and_foreign_files_stay(wired):
    d = team(wired, "our-review")
    wired.env.write_kit_skills()
    for host in (".claude", ".agents"):
        assert (wired.root / host / "skills" / "our-review" / "SKILL.md").is_file()
    mine = wired.root / ".claude" / "skills" / "handmade" / "SKILL.md"
    mine.parent.mkdir(parents=True); mine.write_text("x", encoding="utf-8")
    shutil.rmtree(d)
    wired.env.write_kit_skills()
    assert not (wired.root / ".claude" / "skills" / "our-review").exists()
    assert not (wired.root / ".agents" / "skills" / "our-review").exists()
    assert mine.exists()


def test_trust_asks_for_an_edited_team_copy_once_and_names_it(wired):
    trust = importlib.import_module("lib.trust")
    team(wired, "cam-docs-update", text="---\nname: cam-docs-update\ndescription: Ours.\n---\nbody\n")
    wired.env.write_kit_skills()
    rows = [(it, st) for it, st in trust.pending() if "cam-docs-update" in it.id]
    assert rows and all(it.kind == "skill" and "(team copy)" in it.detail for it, _ in rows)
    trust.approve()
    assert [it for it, _ in trust.pending() if "cam-docs-update" in it.id] == []


def test_budget_counts_only_kit_skills_as_the_kits(wired):
    team(wired, "our-review"); wired.env.write_kit_skills()
    rows = {i["path"]: i["kit"] for i in importlib.import_module("lib.budget").standing()["items"] if i["kind"] == "skill"}
    assert rows[".claude/skills/our-review/SKILL.md"] is False
    assert rows[".claude/skills/cam-docs-lookup/SKILL.md"] is True


def test_fork_copies_the_kit_text_and_stays_trusted_until_edited(wired):
    s = skills(wired)
    d = s.fork("cam-docs-update")
    assert (d / "SKILL.md").read_text(encoding="utf-8") == s.kit_files("cam-docs-update")["SKILL.md"]
    assert s.load_stamp()["forks"]["cam-docs-update"]["kit"] == wired.env.VERSIONS["kit"]
    wired.env.write_kit_skills()
    assert [it for it, _ in importlib.import_module("lib.trust").pending() if "cam-docs-update" in it.id] == []
    assert s.diff("cam-docs-update") == ""


def test_diff_shows_the_team_edit_and_what_the_kit_changed_since(wired, monkeypatch):
    s = skills(wired)
    d = s.fork("cam-docs-update")
    (d / "SKILL.md").write_text("team line\n", encoding="utf-8")
    assert "+team line" in s.diff("cam-docs-update")
    real = s.kit_files
    monkeypatch.setattr(s, "kit_files", lambda n: {"SKILL.md": real(n)["SKILL.md"] + "kit line\n"})
    assert s.outdated() == ["cam-docs-update"] and "+kit line" in s.diff("cam-docs-update", against_fork=True)


def test_reset_puts_the_team_copy_aside_and_follows_the_kit(wired):
    s = skills(wired)
    s.fork("cam-docs-update")
    aside = s.reset("cam-docs-update", now="20261112-101500")
    assert aside == wired.root / ".camarones" / "skills" / ".reset" / "cam-docs-update-20261112-101500"
    assert (aside / "SKILL.md").exists() and s.origin("cam-docs-update") == "kit"
    assert "cam-docs-update" not in s.load_stamp()["forks"]


def test_reset_refuses_a_team_only_skill_and_fork_refuses_twice(wired):
    s = skills(wired)
    team(wired, "our-review")
    with pytest.raises(ValueError, match="team skill"):
        s.reset("our-review")
    s.fork("cam-docs-unit")
    with pytest.raises(ValueError, match="already has a team copy"):
        s.fork("cam-docs-unit")


def test_legacy_layout_has_no_team_copies(kit, monkeypatch):
    s = skills(kit)
    monkeypatch.setattr(s, "team_dir", lambda: None)
    assert s.team_names() == [] and s.origin("cam-docs-update") == "kit"
    with pytest.raises(ValueError, match="cam-docs layout"):
        s.fork("cam-docs-update")


def test_doctor_reports_outdated_team_copies(wired, monkeypatch):
    s = skills(wired)
    monkeypatch.setattr(s, "outdated", lambda: ["cam-docs-update"])
    assert importlib.import_module("lib.doctor").report()["skills_outdated"] == ["cam-docs-update"]


def test_reset_never_nests_when_the_aside_name_is_taken(wired):
    s = skills(wired)
    s.fork("cam-docs-update")
    first = s.reset("cam-docs-update", now="20261112-101500")
    s.fork("cam-docs-update")
    second = s.reset("cam-docs-update", now="20261112-101500")
    assert first != second and second.name == first.name + "-2" and second.parent == first.parent
    assert (first / "SKILL.md").is_file() and (second / "SKILL.md").is_file()


def link(path, target, folder=False):
    try:
        path.symlink_to(target, target_is_directory=folder)
    except OSError:
        pytest.skip("no symlink rights")


def test_a_symlink_in_a_team_skill_is_never_followed(wired, tmp_path):
    s = skills(wired)
    secret = tmp_path / "hosts.yml"
    secret.write_text("oauth_token: gho_secret", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("---\nname: x\ndescription: Not ours.\n---\ngho_secret\n", encoding="utf-8")
    d = team(wired, "our-leak")
    link(d / "notes.md", secret)
    link(d / "refs", outside, folder=True)
    link(wired.root / ".camarones" / "skills" / "our-linked", outside, folder=True)
    md = wired.root / ".camarones" / "skills" / "our-md"
    md.mkdir()
    link(md / "SKILL.md", outside / "SKILL.md")
    wired.env.write_kit_skills()
    assert s.team_names() == ["our-leak"]
    assert "gho_secret" not in "".join(wired.env.skill_files().values())
    for host in (".claude", ".agents"):
        rendered = sorted(p.relative_to(wired.root / host / "skills").as_posix()
                          for p in (wired.root / host / "skills").rglob("*") if "our-" in p.as_posix())
        assert rendered == ["our-leak", "our-leak/SKILL.md"]
    assert sorted((i["name"], i["why"]) for i in s.ignored()) == [
        ("our-leak", "symlinked file notes.md"), ("our-leak", "symlinked folder refs"), ("our-linked", "symlink"),
        ("our-md", "symlinked file SKILL.md")]


def test_a_symlinked_team_folder_gives_no_team_copies(wired, tmp_path):
    s = skills(wired)
    outside = tmp_path / "elsewhere"
    (outside / "our-review").mkdir(parents=True)
    (outside / "our-review" / "SKILL.md").write_text("---\nname: x\ndescription: Not ours.\n---\n", encoding="utf-8")
    shutil.rmtree(wired.root / ".camarones" / "skills", ignore_errors=True)
    link(wired.root / ".camarones" / "skills", outside, folder=True)
    assert s.team_names() == [] and "our-review" not in s.sources()
    assert s.ignored() == [{"name": "", "why": "symlink"}]


def test_junk_and_binary_files_in_a_team_skill_are_left_out(wired):
    s = skills(wired)
    d = team(wired, "our-review", extra={"Thumbs.db": "x", "desktop.ini": "x", ".hidden.md": "x"})
    (d / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1\xff\xfe")
    (d / "__pycache__").mkdir()
    (d / "__pycache__" / "x.cpython-312.pyc").write_bytes(b"\xcb\r\r\n\x00\x00\xff")
    (d / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\xff\xfe")
    files = wired.env.skill_files()
    assert sorted(r for r in files if "/our-review/" in r) == [
        ".agents/skills/our-review/SKILL.md", ".claude/skills/our-review/SKILL.md"]
    assert s.ignored() == [{"name": "our-review", "why": "not UTF-8 text: logo.png"}]
    wired.env.write_kit_skills()
    assert [x for x in importlib.import_module("lib.install_state").drift() if "our-review" in x["path"]] == []


def test_a_team_copy_whose_skill_md_is_not_utf8_is_not_a_team_copy(wired):
    s = skills(wired)
    d = team(wired, "cam-docs-unit")
    (d / "SKILL.md").write_bytes(b"---\nname: cam-docs-unit\ndescription: Caf\xe9.\n---\n")
    assert s.origin("cam-docs-unit") == "kit"
    assert s.ignored() == [{"name": "cam-docs-unit", "why": "not UTF-8 text: SKILL.md"}]
    wired.env.write_kit_skills()


def test_a_team_copy_saved_with_a_bom_keeps_its_frontmatter(wired):
    s = skills(wired)
    trust = importlib.import_module("lib.trust")
    d = team(wired, "our-review")
    (d / "SKILL.md").write_bytes(b"\xef\xbb\xbf---\nname: our-review\ndescription: Ours.\n---\nbody\n")
    assert s.description("our-review") == "Ours."
    raw = s.kit_files("cam-docs-update")["SKILL.md"]
    f = team(wired, "cam-docs-update")
    (f / "SKILL.md").write_bytes(b"\xef\xbb\xbf" + raw.encode("utf-8"))
    wired.env.write_kit_skills()
    assert not (wired.root / ".claude" / "skills" / "our-review" / "SKILL.md").read_bytes().startswith(b"\xef\xbb\xbf")
    assert [x for x in importlib.import_module("lib.install_state").drift() if "skills" in x["path"]] == []
    assert [it for it, _ in trust.pending() if "cam-docs-update" in it.id] == []


def test_the_render_manifest_only_removes_rendered_skill_files(wired):
    victim = wired.root.parent / "victim.txt"
    victim.write_text("keep", encoding="utf-8")
    settings = wired.root / ".claude" / "settings.json"
    before = settings.read_bytes()
    wired.env.save_json(wired.env.RENDERED_SKILLS, ["../victim.txt", ".claude/settings.json", ".claude/skills",
                                                    ".claude/skills/x/../../settings.json", victim.as_posix(),
                                                    ".claude/skills/x/..\\..\\settings.json"])
    wired.env.write_kit_skills()
    assert victim.read_text(encoding="utf-8") == "keep" and settings.read_bytes() == before
    assert (wired.root / ".claude" / "skills").is_dir()


def linked_at(wired, at, victim):
    """`at` (a cam-docs-relative folder) replaced by a committed-style symlink to the folder `victim`."""
    path = wired.root / at
    shutil.rmtree(path, ignore_errors=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    link(path, victim, folder=True)


@pytest.mark.parametrize("at", [".claude", ".claude/skills", ".claude/skills/projects"])
def test_the_render_cleanup_never_deletes_through_a_link(wired, tmp_path, at):
    victim = tmp_path / "fake-home"
    projects = victim / PurePosixPath(".claude/skills/projects").relative_to(at)
    (projects / "old").mkdir(parents=True)
    (projects / "important.txt").write_text("keep", encoding="utf-8")
    linked_at(wired, at, victim)
    wired.env.save_json(wired.env.RENDERED_SKILLS, [".claude/skills/projects/important.txt",
                                                    ".claude/skills/projects/old/gone.md"])
    wired.env.write_kit_skills()
    assert (projects / "important.txt").read_text(encoding="utf-8") == "keep"
    assert (projects / "old").is_dir()


def test_an_approved_team_copy_edited_again_needs_approval_again(wired):
    trust = importlib.import_module("lib.trust")
    d = team(wired, "cam-docs-update", text="---\nname: cam-docs-update\ndescription: Ours.\n---\nbody\n")
    wired.env.write_kit_skills()
    trust.approve()
    (d / "SKILL.md").write_text("---\nname: cam-docs-update\ndescription: Ours.\n---\nother body\n", encoding="utf-8")
    wired.env.write_kit_skills()
    rows = [(it, st) for it, st in trust.pending() if "cam-docs-update" in it.id]
    assert rows and all(st == "changed" for _, st in rows)


def test_a_checkpoint_commits_a_team_copy_with_its_stamp_and_rendering(wired):
    s = skills(wired)
    d = s.fork("cam-docs-update")
    (d / "SKILL.md").write_text("---\nname: cam-docs-update\ndescription: Ours.\n---\nbody\n", encoding="utf-8")
    wired.env.write_kit_skills()
    assert wired.env.checkpoint_commit("team copy") is True
    files = subprocess.run(["git", "show", "--name-only", "--format=", "HEAD"], cwd=wired.root, capture_output=True,
                           text=True, encoding="utf-8").stdout.splitlines()
    assert {".camarones/skills/cam-docs-update/SKILL.md", ".camarones/.kit-skills.json",
            ".claude/skills/cam-docs-update/SKILL.md"} <= set(files)


def test_a_symlinked_rendered_file_is_replaced_never_written_through(wired, tmp_path):
    victim = tmp_path / "victim.md"
    victim.write_text("keep", encoding="utf-8")
    dst = wired.root / ".claude" / "skills" / "cam-docs-update" / "SKILL.md"
    dst.unlink()
    link(dst, victim)
    wired.env.write_kit_skills()
    assert victim.read_text(encoding="utf-8") == "keep"
    assert not dst.is_symlink()
    assert dst.read_text(encoding="utf-8") == wired.env.skill_files()[".claude/skills/cam-docs-update/SKILL.md"]


@pytest.mark.parametrize("at", [".claude", ".claude/skills", ".claude/skills/cam-docs-update"])
def test_a_symlinked_host_or_skill_folder_gets_nothing_written_into_it(wired, tmp_path, at):
    victim = tmp_path / "fake-home"
    victim.mkdir()
    linked_at(wired, at, victim)
    wired.env.write_kit_skills()
    assert list(victim.rglob("*")) == []
    assert (wired.root / at).is_symlink()
    assert (wired.root / ".agents" / "skills" / "cam-docs-update" / "SKILL.md").is_file()
    if at == ".claude/skills/cam-docs-update":
        assert (wired.root / ".claude" / "skills" / "cam-docs-lookup" / "SKILL.md").is_file()


def test_fork_refuses_a_symlinked_team_folder(wired, tmp_path):
    s = skills(wired)
    victim = tmp_path / "elsewhere"
    victim.mkdir()
    linked_at(wired, ".camarones/skills", victim)
    with pytest.raises(ValueError, match="is a link"):
        s.fork("cam-docs-update")
    assert list(victim.iterdir()) == [] and "cam-docs-update" not in s.load_stamp()["forks"]
