"""`docs reset`: an older project's docs started again — redo (reopen every finished unit, nothing deleted) or wipe
(the generated docs go, interviews and pages a person wrote or confirmed stay, the plan starts over)."""
from __future__ import annotations

import importlib, os, subprocess, sys

import pytest

from conftest import KIT_DIR


def unit(data, uid):
    return next(u for u in data["units"] if u["id"] == uid)


def page(root, rel, fm: str = "", body: str = "# Page\n"):
    f = root / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text((f"---\n{fm}---\n" if fm else "") + body, encoding="utf-8")
    return f


@pytest.fixture
def documented(wired):
    """A project documented by an older run: units done, AI pages, a person's pages, interview notes, a wiki."""
    kit, root = wired, wired.root
    plan = kit.plan
    plan.sync()
    for uid in ("setup", "discovery:api", "discovery:web", "discovery:worker", "discovery-cross", "repo-brief:api",
                "domain"):
        plan.set_status(uid, "done", record=False)
    plan.set_status("interview-context", "done", "context agreed")
    plan.note("interview-context", "bounded contexts agreed with the team")
    plan.note("domain", "glossary drafted")
    plan.add("flow:checkout", "Flow: checkout")
    page(root, "docs/domain/glossary.md", "title: Glossary\nx-owner: ai\nx-confirmed: {by: ana, at: x, body_sha: y}\n")
    page(root, "docs/decisions/0001-db.md", "title: DB\nx-owner: human\n")
    page(root, "docs/domain/context-map.md", "title: Context map\nx-owner: ai\n")
    page(root, "docs/i18n/es/domain/glossary.md", "title: Glosario\n")
    page(root, "docs/i18n/es/domain/context-map.md", "title: Mapa\n")
    page(root, "docs/interview/context.md", "title: Interview 1\ntype: interview\n")
    page(root, "docs/architecture/model.c4", body="model { }\n")
    (root / "docs" / "assets").mkdir(parents=True)
    (root / "docs" / "assets" / "logo.png").write_bytes(b"\x89PNG")
    wiki = kit.docs.wiki_dir("api")
    page(wiki, "index.md", "title: api\n")
    page(wiki, "runbook.md", "title: Runbook\nx-owner: human\n")
    page(wiki, "INSTRUCTIONS.md", body="brief\n")
    kit.common.save_json(kit.common.WORK / "fresh.json", {"v": 1, "pages": {"gone/old.md": {"body_sha": "x", "at": "x"}}})
    kit.common.save_json(root / "docs" / ".state.json", {"api": "abc"})
    kit.env.checkpoint_commit("documented")
    kit.reset = importlib.import_module("lib.reset")
    return kit


def test_wipe_preview_lists_what_goes_and_changes_nothing(documented, capsys):
    root, reset = documented.root, documented.reset
    assert reset.main("wipe", dry_run=True) == 0
    out = capsys.readouterr().out
    assert "docs/domain/context-map.md" in out and "docs/overview.md" in out
    assert "docs/domain/glossary.md" not in out.split("Kept:")[0]                    # a person's page is kept
    assert "spec.c4" not in out                                                        # the template, as the kit wrote it
    assert "dry run" in out
    assert (root / "docs" / "domain" / "context-map.md").exists()
    assert unit(documented.plan.load(), "domain")["status"] == "done"


def test_wipe_deletes_the_generated_docs_and_keeps_what_people_wrote(documented):
    root, wiki = documented.root, documented.docs.wiki_dir("api")
    documented.reset.run("wipe")
    gone = ["docs/overview.md", "docs/domain/context-map.md", "docs/i18n/es/domain/context-map.md",
            "docs/architecture/model.c4", "docs/.state.json"]
    kept = ["docs/domain/glossary.md", "docs/i18n/es/domain/glossary.md", "docs/decisions/0001-db.md",
            "docs/interview/context.md", "docs/assets/logo.png", ".camarones/workspace.yaml"]
    assert [p for p in gone if (root / p).exists()] == []
    assert [p for p in kept if not (root / p).exists()] == []
    assert "gone/old.md" not in (root / "docs" / ".work" / "fresh.json").read_text(encoding="utf-8")   # stamped anew
    assert not (wiki / "index.md").exists() and not (wiki / "INSTRUCTIONS.md").exists()
    assert (wiki / "runbook.md").exists() and wiki.is_dir()                            # the repo's link still resolves
    assert (root / "docs" / "architecture" / "spec.c4").exists()                       # templates put back
    assert (root / "docs" / "llms.txt").exists()


def test_wipe_starts_the_plan_over_but_keeps_the_interviews(documented):
    plan = documented.plan
    documented.reset.run("wipe")
    data = plan.load()
    assert unit(data, "interview-context")["status"] == "done"
    assert unit(data, "setup")["status"] == "done"
    for uid in ("domain", "repo-brief:api", "discovery:api"):
        u = unit(data, uid)
        assert u["status"] == "todo" and "redo" not in u and not u["notes"]
    assert "flow:checkout" not in [u["id"] for u in data["units"]]                    # flows-catalog proposes them again
    assert plan.note_file("interview-context").exists()
    assert not plan.note_file("domain").exists()
    assert "docs reset (wipe)" in plan.LOG.read_text(encoding="utf-8")


def test_wipe_tags_the_docs_before_deleting_them(documented):
    root = documented.root
    documented.reset.run("wipe")
    tags = subprocess.run(["git", "tag", "--list", "camaron/pre-reset-*"], cwd=root, capture_output=True, text=True,
                          encoding="utf-8").stdout.split()
    assert len(tags) == 1
    old = subprocess.run(["git", "show", f"{tags[0]}:docs/domain/context-map.md"], cwd=root, capture_output=True,
                         text=True, encoding="utf-8")
    assert old.returncode == 0 and "Context map" in old.stdout
    clean = subprocess.run(["git", "status", "--porcelain", "--", "docs"], cwd=root, capture_output=True, text=True,
                           encoding="utf-8").stdout
    assert clean.strip() == ""                                                         # the reset is its own commit


def test_redo_reopens_every_finished_unit_and_deletes_nothing(documented):
    root, plan = documented.root, documented.plan
    reopened = documented.reset.run("redo")["reopened"]
    data = plan.load()
    assert {"domain", "repo-brief:api", "discovery:api"} <= set(reopened)
    assert "interview-context" not in reopened and "setup" not in reopened
    assert unit(data, "domain")["status"] == "todo" and "redo" in unit(data, "domain")
    assert unit(data, "interview-context")["status"] == "done"
    assert (root / "docs" / "domain" / "context-map.md").exists()
    assert plan.old_notes("domain")                                                    # old checkpoints archived


def test_redo_with_nothing_finished_reopens_nothing(kit):
    kit.plan.sync()
    reset = importlib.import_module("lib.reset")
    assert reset.run("redo")["reopened"] == []


def test_templates_follow_the_kit_again_only_when_asked(documented):
    root, reset = documented.root, documented.reset
    playbook = root / ".camarones" / "PLAYBOOK.md"
    playbook.write_text("team's own playbook\n", encoding="utf-8")
    reset.run("redo")
    assert playbook.read_text(encoding="utf-8") == "team's own playbook\n"
    reset.run("wipe", templates=True)
    assert playbook.read_bytes() == (documented.kit_dir / "PLAYBOOK.md").read_bytes()
    aside = list(playbook.parent.glob("PLAYBOOK.md.before-reset-*"))
    assert len(aside) == 1 and aside[0].read_text(encoding="utf-8") == "team's own playbook\n"


def test_reset_waits_for_a_running_documentation_run(documented, monkeypatch):
    from lib.harness import scheduler
    monkeypatch.setattr(scheduler, "busy", lambda: {"pid": 1, "what": "documentation run"})
    assert documented.reset.guard()
    assert documented.reset.main("wipe", yes=True) == 1
    assert (documented.root / "docs" / "domain" / "context-map.md").exists()


# ---------- CLI ----------
def cli(kit, *args):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root), "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "docs", *args], env=env,
                          capture_output=True, text=True, encoding="utf-8", cwd=kit.ws)


def test_cli_docs_reset(documented):
    root = documented.root
    assert cli(documented, "reset").returncode == 2                                    # redo or wipe: say which
    r = cli(documented, "reset", "--wipe", "--dry-run")
    assert r.returncode == 0 and "docs/domain/context-map.md" in r.stdout, r.stdout + r.stderr
    r = cli(documented, "reset", "--wipe")                                             # no --yes, no terminal: cancelled
    assert r.returncode == 1 and (root / "docs" / "domain" / "context-map.md").exists()
    r = cli(documented, "reset", "--redo", "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    assert unit(documented.plan.load(), "domain")["status"] == "todo"
    r = cli(documented, "reset", "--wipe", "--yes")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (root / "docs" / "domain" / "context-map.md").exists()


def test_wipe_starts_a_new_epoch_and_redo_keeps_it(documented, monkeypatch):
    plan = documented.plan
    old = plan.load()["epoch"]
    monkeypatch.setattr(plan, "utcnow", lambda: "2099-01-01T00:00:00Z")
    documented.reset.run("redo")
    assert plan.load()["epoch"] == old
    documented.reset.run("wipe")
    assert plan.load()["epoch"] == "2099-01-01T00:00:00Z"
