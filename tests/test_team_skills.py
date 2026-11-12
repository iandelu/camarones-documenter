import importlib
import shutil

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
