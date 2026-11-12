import importlib


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
