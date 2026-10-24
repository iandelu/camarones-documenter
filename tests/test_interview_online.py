"""The team questionnaire answered online in the portal (GET /api/interview, POST /api/interview/answer): the same
response file `interview import` writes, so the offline form and the consolidating units keep working unchanged."""
from __future__ import annotations

import json, threading, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

import pytest

from test_questionnaire import QUESTIONNAIRE, answers_file

ANSWERS = {"ctx-contexts": {"choice": ["Pets", "Visits"], "other": "Clinics"},
           "ctx-envs": {"choice": "no", "comment": "there is a pre env"}}


@pytest.fixture
def q(kit):
    kit.questionnaire.SOURCE.parent.mkdir(parents=True, exist_ok=True)
    kit.questionnaire.SOURCE.write_text(QUESTIONNAIRE, encoding="utf-8")
    return kit.questionnaire


@pytest.fixture
def portal(kit):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), kit.serve.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(url, body=None, header=True):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json", **({"X-Camarones": "1"} if header else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def test_an_online_answer_is_the_same_file_as_an_imported_one(q, tmp_path):
    q.answer({"respondent": "Ana", "role": "dev", "date": "2026-09-25", "answers": ANSWERS})
    online = (q.RESPONSES / "ana.yaml").read_bytes()
    (q.RESPONSES / "ana.yaml").unlink()
    q.import_files([answers_file(tmp_path, "Ana", ANSWERS)])
    assert (q.RESPONSES / "ana.yaml").read_bytes() == online


@pytest.mark.parametrize("rec,why", [({"respondent": " ", "answers": ANSWERS}, "name"),
                                     ({"respondent": "Ana", "answers": {"nope": {"text": "x"}}}, "answers")])
def test_an_answer_without_name_or_answers_is_refused(q, rec, why):
    with pytest.raises(ValueError, match=why):
        q.answer(rec)
    assert not q.RESPONSES.exists()


def test_the_portal_serves_the_form_and_a_persons_answers(q, portal):
    code, f = call(portal + "/api/interview")
    assert code == 200 and f["available"] is True and f["mode"] in ("team", "live")
    assert [x["id"] for x in f["questions"]][:2] == ["ctx-contexts", "ctx-envs"] and f["labels"]["es"]["yes"]
    assert f["status"]["respondents"] == [] and f["user"] == "Test"
    code, s = call(portal + "/api/interview/answer", {"respondent": "Ana", "role": "dev", "answers": ANSWERS})
    assert code == 200 and [r["name"] for r in s["respondents"]] == ["Ana"]
    code, f = call(portal + "/api/interview?who=Ana")
    assert f["mine"]["answers"]["ctx-envs"] == {"choice": "no", "comment": "there is a pre env"}
    assert call(portal + "/api/interview/answer", {"respondent": "Ana", "answers": ANSWERS}, header=False)[0] == 403
    assert call(portal + "/api/interview/answer", {"respondent": "", "answers": ANSWERS})[0] == 400


def test_without_a_questionnaire_the_portal_says_what_writes_it(kit, portal):
    code, f = call(portal + "/api/interview")
    assert code == 200 and f["available"] is False and "questionnaire" in f["reason"]
