import importlib

import pytest


def test_a_note_round_trips_through_its_line_format(kit):
    skills = importlib.import_module("lib.skills")
    n = {"date": "2026-11-12", "source": "retro", "step": "verify", "change": "wi-12", "ref": "", "by": "Ana López",
         "text": "the plan missed the  integration\ntests"}
    line = skills.format_note(n)
    assert line == ("- 2026-11-12 · retro · step verify · change wi-12 · ref - · Ana López — "
                    "the plan missed the integration tests")
    assert skills.parse_note(line) == {**n, "text": "the plan missed the integration tests"}
    assert skills.parse_note("# Skill notes: x") is None


def test_add_note_writes_one_file_per_skill_and_notes_reads_them_newest_first(kit):
    s = importlib.import_module("lib.skills")
    f = s.add_note("cam-docs-update", "first", "retro", "ana", today="2026-11-10")
    s.add_note("cam-docs-update", "second", "review", "bo", ref="https://git.example/pr/3#c1", today="2026-11-12")
    assert f == kit.root / "docs" / ".work" / "skill-notes" / "cam-docs-update.md"
    assert f.read_text(encoding="utf-8").startswith("# Skill notes: cam-docs-update\n")
    assert [n["text"] for n in s.notes("cam-docs-update")] == ["second", "first"]
    assert s.notes()[0]["skill"] == "cam-docs-update"


def test_add_note_refuses_unknown_skills_sources_and_empty_text(kit):
    s = importlib.import_module("lib.skills")
    for args, msg in ((("nope", "x", "retro", "a"), "unknown skill"), (("cam-docs-update", "x", "chat", "a"), "source"),
                      (("cam-docs-update", "  ", "retro", "a"), "empty")):
        with pytest.raises(ValueError, match=msg):
            s.add_note(*args)
    assert not (kit.root / "docs" / ".work" / "skill-notes").exists()


def test_notes_never_become_pages(kit):
    s = importlib.import_module("lib.skills")
    s.add_note("cam-docs-update", "x", "retro", "ana")
    assert not [r for r in kit.docs.collect() if "skill-notes" in r["path"]]
