"""Agent guidance (P9, X12, X9): where to look for what (the AGENTS.md routing table and the lookup skill), a handoff
that separates verified results from intents, and a page of what was removed on purpose so agents do not recreate it."""
from __future__ import annotations

import os, subprocess, sys

from conftest import KIT_DIR

TEMPLATE = (KIT_DIR / "templates" / "AGENTS.md").read_text(encoding="utf-8")


def test_agents_md_routes_questions_to_pages_inside_the_managed_block():
    block = TEMPLATE[TEMPLATE.index("<!-- camarones:start -->"):TEMPLATE.index("<!-- camarones:end -->")]
    for where in ("docs/repos/<repo>/brief.md", "reference.md", "docs/flows/", "docs/domain/glossary.md",
                  "docs/decisions/", "docs/overview/removed.md"):
        assert where in block
    assert "search_docs" in block and "read_doc(path, section)" in block and "ask" in block


def test_the_lookup_skill_follows_the_same_order():
    skill = (KIT_DIR / "templates" / "skills" / "cam-docs-lookup" / "SKILL.md").read_text(encoding="utf-8")
    assert "removed.md" in skill and "ask" in skill


SKILLS = KIT_DIR / "templates" / "skills"


def test_the_diagrams_skill_teaches_mermaid_and_the_generated_block_rules():
    text = (SKILLS / "cam-docs-diagrams" / "SKILL.md").read_text(encoding="utf-8")
    front = text.split("---")[1]
    assert "name: cam-docs-diagrams" in front and "Mermaid" in front.split("description:")[1]
    for part in ("never edit a generated block", "<!-- proposal:", "stateDiagram-v2", "25", "{{CLI}} check",
                 "{{CLI}} diagrams", "repo:path#Symbol", "confirmed", "base="):
        assert part in text, part


def test_the_update_and_lookup_skills_know_about_diagrams():
    assert "diagrams" in (SKILLS / "cam-docs-update" / "SKILL.md").read_text(encoding="utf-8")
    lookup = (SKILLS / "cam-docs-lookup" / "SKILL.md").read_text(encoding="utf-8")
    assert "confirmed" in lookup and "diagram" in lookup and "proposal" in lookup


def test_conventions_and_playbook_carry_the_same_diagram_rules():
    conventions = (KIT_DIR / "CONVENTIONS.md").read_text(encoding="utf-8")
    section = conventions[conventions.index("## 5. Markdown diagrams"):conventions.index("## 6. Page templates")]
    assert "generated:" in section and "proposal" in section and "confirmed" in section
    playbook = (KIT_DIR / "PLAYBOOK.md").read_text(encoding="utf-8")
    unit = playbook[playbook.index("## diagrams"):playbook.index("## doc-fixes")]
    assert "CLI diagrams" in unit and "proposal" in unit and "never" in unit


def test_the_diagram_texts_do_not_promise_what_delivery_2b_adds():
    import re
    playbook = (KIT_DIR / "PLAYBOOK.md").read_text(encoding="utf-8")
    conventions = (KIT_DIR / "CONVENTIONS.md").read_text(encoding="utf-8")
    texts = {"skill": (SKILLS / "cam-docs-diagrams" / "SKILL.md").read_text(encoding="utf-8"),
             "conventions": conventions[conventions.index("## 5. Markdown diagrams"):conventions.index("## 6. Page templates")],
             "playbook": playbook[playbook.index("## diagrams"):playbook.index("## doc-fixes")]}
    for name, text in texts.items():
        assert not re.search(r"diagrams\s+(propose|accept|discard)", text), name
        assert not re.search(r"accept\w*[^.\n]{0,40}portal|portal[^.\n]{0,40}accept", text, re.I), name


def test_the_texts_say_where_each_generated_diagram_lives_and_the_real_check_wording():
    skill = (SKILLS / "cam-docs-diagrams" / "SKILL.md").read_text(encoding="utf-8")
    assert "system-map.md` holds the context map" in skill and "diagrams.md` holds the endpoints map" in skill
    conventions = (KIT_DIR / "CONVENTIONS.md").read_text(encoding="utf-8")
    assert "messaging" in conventions[conventions.index("## 5. Markdown diagrams"):conventions.index("## 6. Page templates")]
    lookup = (SKILLS / "cam-docs-lookup" / "SKILL.md").read_text(encoding="utf-8")
    assert "the code changed since this diagram was confirmed" in lookup and "out of date with the code" in lookup


def test_the_diagrams_skill_reaches_every_project_on_every_run():
    from lib import env
    files = env.kit_skill_files("Demo")
    for host in (".claude", ".agents"):
        text = files[f"{host}/skills/cam-docs-diagrams/SKILL.md"]
        assert "{{" not in text


def test_the_handoff_separates_verified_from_intended(kit):
    kit.plan.sync()
    text = kit.plan.prompt("discovery:api", "en")
    for part in ("Verified", "Not verified", "Commands run", "Next action"):
        assert part in text
    playbook = (KIT_DIR / "PLAYBOOK.md").read_text(encoding="utf-8")
    assert "- Verified (with evidence" in playbook and "- Next action:" in playbook
    assert "Verified" in (KIT_DIR / "templates" / "docs" / ".work" / "handoff.md").read_text(encoding="utf-8")


def test_removed_on_purpose_page(kit):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    cli = lambda *a: subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "removed", *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    r = cli("add", "SOAP billing endpoint", "--why", "replaced by the REST API in 2025",
            "--decision", "decisions/0007-drop-soap.md")
    assert r.returncode == 0, r.stderr
    page = kit.root / "docs" / "overview" / "removed.md"
    text = page.read_text(encoding="utf-8")
    assert "| SOAP billing endpoint |" in text and "replaced by the REST API in 2025" in text
    assert "[0007-drop-soap](../decisions/0007-drop-soap.md)" in text
    cli("add", "Legacy cron", "--why", "moved to the scheduler")
    assert page.read_text(encoding="utf-8").count("\n| ") == 3                           # header + 2 rows
    _, warns = kit.quality.check_structure(kit.docs.collect())
    assert not [w for w in warns if "removed.md" in w]



def test_removed_keeps_its_spanish_twin_current(kit):
    ws = kit.docs.workspace(); ws["project"]["translations"] = ["es"]; kit.docs.save_workspace(ws)
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    for what in ("SOAP billing endpoint", "Old admin UI"):
        r = subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "removed", "add", what, "--why", "gone"],
                           env=env, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr
    es = (kit.root / "docs" / "i18n" / "es" / "overview" / "removed.md").read_text(encoding="utf-8")
    assert "Quitado a propósito" in es and "| Old admin UI |" in es
    row = next(r for r in kit.docs.collect() if r["path"] == "overview/removed.md")
    assert row["i18n"] == {"es": "current"}
