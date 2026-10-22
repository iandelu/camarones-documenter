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
