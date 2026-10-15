"""Golden questions (R17): an exam with an answer key for the docs. Each question names the pages that should be cited
and the exact identifiers the answer must mention; an agent answers through the docs only, and a deterministic scorer
marks it. Questions are drafted by an agent and count once a person confirms them."""
from __future__ import annotations

import json, os, subprocess, sys
from pathlib import Path

import pytest
import yaml

QUESTIONS = {"questions": [
    {"id": "refund", "q": "How is a refund processed?", "expect": ["flows/refund.md"], "mention": ["POST /refunds"],
     "x-confirmed": {"by": "ana", "at": "2026-10-16"}},
    {"id": "owner", "q": "Who owns the orders table?", "expect": ["data/orders.md"], "mention": ["orders"]},
]}

# a fake agent: answers from a canned table keyed by the question text found in its prompt
FAKE = r'''
import json, os, sys
prompt = " ".join(sys.argv[1:])
answers = json.loads(os.environ["FAKE_ANSWERS"])
for q, a in answers.items():
    if q in prompt:
        print("thinking...")
        print(json.dumps(a))
        break
else:
    print("no idea")
'''


@pytest.fixture
def evals(kit):
    from lib.harness import evals
    return evals


def write_questions(kit, data=QUESTIONS):
    f = kit.root / "evals" / "questions.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return f


@pytest.mark.parametrize("cited,answer,refs,mentions", [
    (["flows/refund.md"], "Call POST /refunds with the order id.", 1.0, 1.0),
    (["cam-docs/docs/flows/refund.md"], "Use POST /refunds.", 1.0, 1.0),
    (["./docs/flows/refund.md", "flows/other.md"], "It is refunded.", 1.0, 0.0),
    ([], "POST /refunds", 0.0, 1.0),
    ([], "post /refunds", 0.0, 0.0),                        # identifiers are exact
])
def test_the_scorer_checks_cited_pages_and_exact_identifiers(evals, cited, answer, refs, mentions):
    s = evals.score(QUESTIONS["questions"][0], answer, cited)
    assert (s["refs"], s["mentions"], s["score"]) == (refs, mentions, round((refs + mentions) / 2, 3))


def test_a_mention_may_list_exact_alternatives(evals):
    q = {"q": "db?", "expect": ["data/db.md"], "mention": [["h2", "H2"], "spring-data-jpa"]}
    assert evals.score(q, "H2 with spring-data-jpa", [])["mentions"] == 1.0
    assert evals.score(q, "an in-memory database", [])["mentions"] == 0.0


def test_the_answer_is_the_last_json_object_with_an_answer(evals):
    lines = ["preamble", '{"note": "not it"}', '{"answer": "first", "cited": []}', "chatter",
             'Final: {"answer": "Use POST /refunds", "cited": ["flows/refund.md"]}']
    assert evals.extract(lines) == ("Use POST /refunds", ["flows/refund.md"])
    assert evals.extract(["no json here"]) == ("no json here", [])


def test_drafts_and_confirmed_questions_are_told_apart(kit, evals):
    write_questions(kit)
    qs = evals.load()
    assert [q["id"] for q in evals.confirmed(qs)] == ["refund"] and [q["id"] for q in evals.drafts(qs)] == ["owner"]
    assert evals.problems(qs) == []
    assert evals.problems([{"id": "x", "q": ""}, {"id": "x", "q": "?", "expect": []}]) == [
        "questions[0]: needs q and expect", "questions[1]: needs q and expect", "questions[1].id: 'x' is used twice"]


def test_confirm_marks_who_approved_a_question(kit, evals):
    write_questions(kit)
    assert evals.confirm(["owner"], by="luis") == ["owner"]
    q = next(q for q in evals.load() if q["id"] == "owner")
    assert q["x-confirmed"]["by"] == "luis" and q["x-confirmed"]["at"]
    with pytest.raises(KeyError):
        evals.confirm(["nope"], by="luis")


@pytest.fixture
def fake_runner(kit, tmp_path, monkeypatch):
    script = tmp_path / "fake.py"
    script.write_text(FAKE, encoding="utf-8")
    from lib.common import PREFS, save_json
    save_json(PREFS, {"runners": {"fake": {"argv": [sys.executable, str(script), "{prompt}"]}}})

    def answers(table):
        monkeypatch.setenv("FAKE_ANSWERS", json.dumps(table))
    return answers


def test_eval_asks_the_confirmed_questions_and_records_a_score(kit, evals, fake_runner):
    write_questions(kit)
    fake_runner({"How is a refund processed?": {"answer": "POST /refunds", "cited": ["flows/refund.md"]},
                 "Who owns the orders table?": {"answer": "nobody", "cited": []}})
    r = evals.run("fake", echo=lambda _: None)
    assert [x["id"] for x in r["questions"]] == ["refund"] and r["score"] == 1.0 and r["drafts_skipped"] == 1
    saved = list((kit.root / "docs" / ".work" / "evals").glob("*.json"))
    assert len(saved) == 1 and json.loads(saved[0].read_text(encoding="utf-8"))["score"] == 1.0
    assert evals.latest()["score"] == 1.0
    all_ = evals.run("fake", include_drafts=True, echo=lambda _: None)
    assert len(all_["questions"]) == 2 and all_["score"] == 0.5


def test_eval_asks_with_read_only_tools(kit, evals):
    from lib.adapters import runners
    from lib.harness.ports import RunRequest
    req = evals.request("How?", kit.ws)
    assert isinstance(req, RunRequest) and req.allow_tools and "Edit" not in req.allow_tools
    assert any("search_docs" in t for t in req.allow_tools)
    assert "Do not change any file" in req.prompt and '"cited"' in req.prompt
    argv = runners.get("claude").build(req).argv
    assert "--dangerously-skip-permissions" not in argv


def test_an_optional_judge_adds_a_graded_score(kit, evals, fake_runner, monkeypatch):
    write_questions(kit)
    fake_runner({"Rate from 0 to 10": {"grade": 8},                # the judge's prompt quotes the question too: first
                 "How is a refund processed?": {"answer": "POST /refunds", "cited": ["flows/refund.md"]}})
    r = evals.run("fake", judge="fake", echo=lambda _: None)
    assert r["questions"][0]["judge"] == 0.8 and r["judge"] == 0.8


def test_eval_draft_adds_a_bounded_unit_for_an_agent(kit, evals):
    kit.plan.sync()
    u = evals.draft_unit()
    assert u["id"] == "eval-questions" and u["type"] == "eval-questions"
    assert kit.plan.settings("eval-questions")["tier"] == "bounded"
    assert "## eval-questions" in (kit.kit_dir / "PLAYBOOK.md").read_text(encoding="utf-8")


def test_questions_are_committed_with_the_docs(kit):
    assert "evals" in kit.env.CHECKPOINT_PATHS


def test_the_petclinic_set_is_well_formed(kit, evals):
    data = yaml.safe_load((Path(kit.kit_dir).parent / "scripts" / "evals" / "petclinic.yaml").read_text(encoding="utf-8"))
    qs = data["questions"]
    assert len(qs) >= 8 and evals.problems(qs) == [] and all(q.get("mention") for q in qs)


def test_kpis_show_the_latest_eval_score(kit, evals, fake_runner):
    write_questions(kit)
    fake_runner({"How is a refund processed?": {"answer": "POST /refunds", "cited": []}})
    evals.run("fake", echo=lambda _: None)
    from lib.harness import kpis
    assert kpis.report(run_check=False)["usefulness"]["eval_score"] == 0.5


def test_the_eval_command(kit, fake_runner):
    write_questions(kit)
    fake_runner({"How is a refund processed?": {"answer": "POST /refunds", "cited": ["flows/refund.md"]}})
    env = {**os.environ, "CAMARONES_ROOT": str(kit.root)}
    cli = lambda *a: subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "eval", *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    out = cli("list").stdout
    assert "refund" in out and "owner" in out and "draft" in out
    r = json.loads(cli("run", "--runner", "fake", "--json").stdout)
    assert r["score"] == 1.0
    assert cli("confirm", "owner", "--by", "luis").returncode == 0
    kp = subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "kpis", "--no-check"], env=env,
                        capture_output=True, text=True, encoding="utf-8").stdout
    assert "golden questions: score 1.0" in kp
