"""Deferred team interviews: a questionnaire the team answers offline, then agent units that consolidate the answers."""
from __future__ import annotations

import json, os, subprocess, sys

import pytest

from conftest import KIT_DIR


def unit(data, uid):
    return next(u for u in data["units"] if u["id"] == uid)


def ids(data):
    return [u["id"] for u in data["units"]]


def set_mode(kit, mode):
    ws = kit.docs.workspace()
    ws["project"]["interviews"] = mode
    kit.docs.save_workspace(ws)


# ---------- plan ----------
def test_projects_without_the_key_keep_live_interviews(kit):
    """3.x projects have no `interviews` key: same plan as before, no questionnaire units."""
    assert kit.docs.interview_mode() == "live"
    data = kit.plan.sync()
    assert "questionnaire" not in ids(data) and "answers" not in ids(data)
    assert unit(data, "interview-context")["deps"] == ["discovery-cross"]


def test_team_mode_adds_questionnaire_then_answers_before_the_interviews(kit):
    set_mode(kit, "team")
    data = kit.plan.sync()
    q, a = unit(data, "questionnaire"), unit(data, "answers")
    assert (q["runner"], q["deps"]) == ("agent", ["discovery-cross"])
    assert (a["runner"], a["deps"]) == ("wizard", ["questionnaire"])
    assert unit(data, "interview-context")["deps"] == ["answers"]
    assert ids(data).index("questionnaire") < ids(data).index("answers") < ids(data).index("interview-context")


def test_unknown_mode_falls_back_to_live(kit):
    set_mode(kit, "carrier-pigeon")
    assert kit.docs.interview_mode() == "live"


def test_switching_back_to_live_drops_the_pending_questionnaire(kit):
    set_mode(kit, "team")
    kit.plan.sync()
    set_mode(kit, "live")
    data = kit.plan.sync()
    assert unit(data, "questionnaire")["status"] == "dropped"
    assert unit(data, "answers")["status"] == "dropped"
    assert unit(data, "interview-context")["deps"] == ["discovery-cross"]
    set_mode(kit, "team")                                                 # and it comes back when chosen again
    data = kit.plan.sync()
    assert unit(data, "questionnaire")["status"] == "todo" and unit(data, "questionnaire")["notes"] == ""


def test_a_finished_questionnaire_is_kept_when_switching_to_live(kit):
    set_mode(kit, "team")
    kit.plan.sync()
    kit.plan.set_status("questionnaire", "done")
    set_mode(kit, "live")
    assert unit(kit.plan.sync(), "questionnaire")["status"] == "done"


def test_team_mode_after_live_interviews_does_not_ask_again(kit):
    kit.plan.sync()
    kit.plan.set_status("interview-context", "done")
    set_mode(kit, "team")
    data = kit.plan.sync()
    assert unit(data, "questionnaire")["status"] == "dropped"
    assert unit(data, "answers")["status"] == "dropped"
    assert unit(data, "interview-context")["status"] == "done"


# ---------- autopilot ----------
@pytest.fixture
def pilot(kit, monkeypatch):
    plan = kit.plan
    calls = []

    def run_agent(agent, text, lang, uid, echo):
        calls.append(uid)
        plan.set_status(uid, "done")
        return subprocess.CompletedProcess([agent], 0, "", "")
    monkeypatch.setattr(plan, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(plan, "_run_agent", run_agent)
    monkeypatch.setattr(plan, "prompt", lambda uid, lang="es", unattended=False: f"prompt {uid}")
    return calls


def finish(kit, *prefixes):
    for u in kit.plan.load()["units"]:
        if u["id"].startswith(prefixes):
            kit.plan.set_status(u["id"], "done")


def test_autopilot_writes_the_questionnaire_and_waits_for_answers(kit, pilot):
    set_mode(kit, "team")
    kit.plan.sync()
    finish(kit, "setup", "discovery")
    echo = []
    kit.plan.run_autopilot(echo=echo.append)
    assert "questionnaire" in pilot
    assert not any(uid.startswith("interview-") for uid in pilot)
    assert any("answers" in l and "wizard step" in l for l in echo)


def test_autopilot_consolidates_team_answers(kit, pilot):
    set_mode(kit, "team")
    kit.plan.sync()
    finish(kit, "setup", "discovery", "questionnaire", "answers")
    kit.plan.run_autopilot(echo=lambda _: None, max_units=3)
    assert pilot[0] == "interview-context"


def test_autopilot_still_leaves_live_interviews_to_a_human(kit, pilot):
    kit.plan.sync()
    finish(kit, "setup", "discovery")
    kit.plan.run_autopilot(echo=lambda _: None)
    assert pilot == []


# ---------- questionnaire: format, export, import, status ----------
QUESTIONNAIRE = """\
title: Demo — team questionnaire
intro: We read the code; tell us where we got it wrong.
questions:
  - id: ctx-contexts
    topic: context
    text: Which bounded contexts does the system have?
    inferred: Pets and Visits, one per service.
    evidence: api:src/main/java/demo/Api.java#L1-L4
    kind: multi
    options: [Pets, Visits, Billing]
  - id: ctx-envs
    topic: context
    text: Is there a staging environment?
    inferred: Only dev and prod appear in the Helm values.
    kind: confirm
  - id: lang-owner
    topic: language
    text: Who is the "owner" in the business language?
    kind: single
    options: [The pet's owner, The clinic, A vet]
  - id: hist-why
    topic: history
    text: Why was the worker written in Python?
    kind: text
"""


@pytest.fixture
def q(kit):
    kit.questionnaire.SOURCE.parent.mkdir(parents=True, exist_ok=True)
    kit.questionnaire.SOURCE.write_text(QUESTIONNAIRE, encoding="utf-8")
    return kit.questionnaire


def answers_file(tmp_path, name, answers, fname=None):
    f = tmp_path / (fname or f"answers-{name.lower()}.json")
    f.write_text(json.dumps({"respondent": name, "role": "dev", "date": "2026-09-25", "answers": answers}),
                 encoding="utf-8")
    return f


def test_invalid_questionnaire_is_reported(q):
    q.SOURCE.write_text("questions:\n  - id: a\n    text: A?\n    kind: single\n", encoding="utf-8")
    with pytest.raises(ValueError, match="options"):
        q.load()
    q.SOURCE.unlink()
    with pytest.raises(ValueError, match="questionnaire.yaml"):
        q.load()


def test_export_writes_a_self_contained_form_and_a_markdown_copy(q):
    html, md = q.export(lang="es")
    page = html.read_text(encoding="utf-8")
    assert "<script" in page and "ctx-contexts" in page and "Descargar" in page
    assert "http://" not in page and "https://" not in page                  # works offline, nothing external
    text = md.read_text(encoding="utf-8")
    assert text.startswith("---\ntype: interview")                           # a doc page: frontmatter, not translated
    assert "## ctx-contexts" in text and "- [ ] Billing" in text


def test_the_form_cannot_be_broken_by_question_text(q):
    q.SOURCE.write_text(QUESTIONNAIRE.replace("Why was the worker", "</script><b>Why was the worker"), encoding="utf-8")
    page = q.export(lang="en")[0].read_text(encoding="utf-8")
    assert page.count("</script>") == page.count("<script")


def test_import_json_answers_from_the_form(q, tmp_path):
    f = answers_file(tmp_path, "Ana", {"ctx-contexts": {"choice": ["Pets", "Visits"], "other": "Clinics"},
                                        "ctx-envs": {"choice": "no", "comment": "there is a pre env"}})
    [(src, who, err)] = q.import_files([f])
    assert (who, err) == ("Ana", None)
    saved = q.responses()
    assert saved["Ana"]["answers"]["ctx-contexts"] == {"choice": ["Pets", "Visits"], "other": "Clinics"}
    before = (q.RESPONSES / "ana.yaml").read_bytes()
    q.import_files([f])                                                      # idempotent
    assert (q.RESPONSES / "ana.yaml").read_bytes() == before
    assert len(list(q.RESPONSES.iterdir())) == 1


def test_import_a_filled_markdown_copy(q, tmp_path):
    md = q.export(lang="en")[1].read_text(encoding="utf-8")
    md = (md.replace("Name:", "Name: Luis", 1)
            .replace("- [ ] Pets", "- [x] Pets").replace("- [ ] Billing", "- [X] Billing")
            .replace("- [ ] Yes, correct", "- [x] Yes, correct")
            .replace("- [ ] The clinic", "- [x] The clinic"))
    md = md.replace("Answer:", "Answer:\nThe team knew Python.\nAnd it was quick.", 1)
    f = tmp_path / "questionnaire-luis.md"
    f.write_text(md, encoding="utf-8")
    [(_, who, err)] = q.import_files([f])
    assert (who, err) == ("Luis", None)
    a = q.responses()["Luis"]["answers"]
    assert a["ctx-contexts"] == {"choice": ["Pets", "Billing"]}
    assert a["ctx-envs"] == {"choice": "yes"}
    assert a["lang-owner"] == {"choice": "The clinic"}
    assert a["hist-why"] == {"text": "The team knew Python.\nAnd it was quick."}


def test_spanish_markdown_copy_round_trips(q, tmp_path):
    md = q.export(lang="es")[1].read_text(encoding="utf-8")
    md = md.replace("Nombre:", "Nombre: Marta", 1).replace("- [ ] No sé", "- [x] No sé")
    md = md.replace("- [ ] Otra:", "- [x] Otra: Facturación", 1)
    f = tmp_path / "cuestionario-marta.md"
    f.write_text(md, encoding="utf-8")
    [(_, who, err)] = q.import_files([f])
    a = q.responses()["Marta"]["answers"]
    assert a["ctx-envs"] == {"choice": "unsure"} and a["ctx-contexts"] == {"other": "Facturación"}


def test_import_rejects_files_without_a_name_or_answers(q, tmp_path):
    nameless = answers_file(tmp_path, "", {"ctx-envs": {"choice": "yes"}}, "a.json")
    empty = answers_file(tmp_path, "Bob", {"unknown-q": {"choice": "yes"}}, "b.json")
    junk = tmp_path / "c.json"
    junk.write_text("{not json", encoding="utf-8")
    results = q.import_files([nameless, empty, junk])
    assert all(who is None and err for _, who, err in results)
    assert q.responses() == {}


def test_import_a_folder_takes_only_answer_files(q, tmp_path):
    inbox = tmp_path / "Downloads"
    inbox.mkdir()
    answers_file(inbox, "Ana", {"ctx-envs": {"choice": "yes"}}, "respuestas-ana.json")
    answers_file(inbox, "Bob", {"ctx-envs": {"choice": "no"}}, "answers-bob.json")
    (inbox / "holiday.json").write_text("{}", encoding="utf-8")
    assert sorted(who for _, who, _ in q.import_files([inbox])) == ["Ana", "Bob"]


def test_status_counts_respondents_and_flags_conflicts(q, tmp_path):
    q.import_files([answers_file(tmp_path, "Ana", {"ctx-envs": {"choice": "yes"}, "lang-owner": {"choice": "A vet"}}),
                    answers_file(tmp_path, "Bob", {"ctx-envs": {"choice": "no"}, "lang-owner": {"choice": "A vet"}})])
    s = q.status()
    assert s["questions"] == 4 and [r["name"] for r in s["respondents"]] == ["Ana", "Bob"]
    assert [c["id"] for c in s["conflicts"]] == ["ctx-envs"]
    assert s["conflicts"][0]["answers"] == {"yes": ["Ana"], "no": ["Bob"]}
    assert s["unanswered"] == ["ctx-contexts", "hist-why"]


# ---------- CLI ----------
def cli(kit, *args):
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root), "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, str(KIT_DIR / "camarones.py"), "interview", *args], env=env,
                          capture_output=True, text=True, encoding="utf-8", cwd=kit.ws)


def test_cli_mode_export_import_status(kit, q, tmp_path):
    assert cli(kit, "mode").stdout.strip() == "live"
    assert cli(kit, "mode", "team").stdout.strip() == "team"
    assert "questionnaire" in [u["id"] for u in kit.plan.load()["units"]]
    r = cli(kit, "export", "--lang", "en")
    assert r.returncode == 0 and "questionnaire.html" in r.stdout
    good = answers_file(tmp_path, "Ana", {"ctx-envs": {"choice": "yes"}})
    bad = answers_file(tmp_path, "", {"ctx-envs": {"choice": "no"}}, "answers-x.json")
    r = cli(kit, "import", str(good), str(bad))
    assert r.returncode == 1 and "✔ Ana" in r.stdout and "no name" in r.stdout
    s = json.loads(cli(kit, "status", "--json").stdout)
    assert [p["name"] for p in s["respondents"]] == ["Ana"]
    assert cli(kit, "mode", "carrier-pigeon").returncode == 2


# ---------- wizard ----------
@pytest.fixture
def quiet(kit, monkeypatch):
    monkeypatch.setattr(kit.wizard.time, "sleep", lambda _s: None)
    monkeypatch.setattr(kit.wizard.console, "clear", lambda *a, **kw: None)
    monkeypatch.setattr(kit.wizard.W, "reveal", lambda self, p: None)


@pytest.fixture
def launched(kit, monkeypatch):
    prompts = []
    monkeypatch.setattr(kit.wizard.W, "launch_agent", lambda self, prompt, resume_agent=None: prompts.append(prompt) or "bg")
    return prompts


def test_first_interview_asks_live_or_team(kit, quiet, launched, fake_wizard):
    kit.plan.sync()
    finish(kit, "setup", "discovery")
    fake_wizard(["team"]).run_unit(unit(kit.plan.load(), "interview-context"))
    assert kit.docs.interview_mode() == "team"
    assert "unit `questionnaire`" in launched[0]                             # the agent writes the questionnaire first
    assert unit(kit.plan.load(), "interview-context")["status"] == "todo"


def test_live_choice_keeps_the_interview(kit, quiet, launched, fake_wizard):
    kit.plan.sync()
    finish(kit, "setup", "discovery")
    fake_wizard(["live"]).run_unit(unit(kit.plan.load(), "interview-context"))
    assert kit.docs.workspace()["project"]["interviews"] == "live"
    assert "unit `interview-context`" in launched[0]
    fake_wizard([]).run_unit(unit(kit.plan.load(), "interview-language"))   # asked once per project


def test_answers_step_exports_imports_and_closes(kit, q, quiet, fake_wizard, tmp_path):
    set_mode(kit, "team")
    kit.plan.sync()
    finish(kit, "setup", "discovery", "questionnaire")
    f = answers_file(tmp_path, "Ana", {"ctx-envs": {"choice": "yes"}})
    fake_wizard(["export", "import", str(f), "close"]).run_unit(unit(kit.plan.load(), "answers"))
    assert (q.QDIR / "questionnaire.html").exists()
    assert list(q.responses()) == ["Ana"]
    assert unit(kit.plan.load(), "answers")["status"] == "done"
    assert "interview-context" in [u["id"] for u in kit.plan.available()]


def test_answers_step_cannot_close_without_answers(kit, q, quiet, fake_wizard):
    set_mode(kit, "team")
    kit.plan.sync()
    finish(kit, "setup", "discovery", "questionnaire")
    fake_wizard([None]).run_unit(unit(kit.plan.load(), "answers"))
    assert unit(kit.plan.load(), "answers")["status"] == "todo"


def test_team_interview_prompt_consolidates_instead_of_asking(kit, q):
    set_mode(kit, "team")
    kit.plan.sync()
    text = kit.plan.prompt("interview-context", lang="es")
    assert "responses/" in text and "consolidate" in text.lower()
    assert "interview status" in text
