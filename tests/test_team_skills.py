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
    wired.env.write_kit_skills()
    assert b"\r\n" not in (wired.root / ".claude" / "skills" / "cam-docs-unit" / "SKILL.md").read_bytes()


def test_a_removed_team_skill_leaves_no_rendered_copy_and_foreign_files_stay(wired):
    d = team(wired, "our-review")
    wired.env.write_kit_skills()
    mine = wired.root / ".claude" / "skills" / "handmade" / "SKILL.md"
    mine.parent.mkdir(parents=True); mine.write_text("x", encoding="utf-8")
    import shutil; shutil.rmtree(d)
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
