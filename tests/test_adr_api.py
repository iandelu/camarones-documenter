"""The desktop app's decisions API (`/api/app/adr…`, app token only) and the ADRs a doc page lists (`/api/doc`)."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from test_app_api import TOKEN, app_server, call, portal_server   # noqa: F401 — fixtures reused

ACTIONS = ("new", "pack", "write", "review", "part", "point", "attendees", "accept", "reject")


@pytest.fixture
def adr(kit):
    return importlib.import_module("lib.adr")


def api(server):
    return f"{server}/api/app/adr"


def post(server, action, body):
    return call(f"{api(server)}/{action}", body, token=TOKEN)


def framed(server, **fields):
    return post(server, "new", {"title": "Sessions", "kind": "new", "touches": ["api:pom.xml"], **fields})[1]


def written(server, **fields):
    framed(server, **fields)
    return post(server, "write", {"id": "0001"})[1]


def with_point(server, **fields):
    a = written(server, **fields)
    return post(server, "point", {"id": "0001", "op": "add", "question": "Where?", "base_sha": a["sha"],
                                  "options": [{"name": "Redis"}, {"name": "Postgres"}]})[1]


def decided(server, **fields):
    a = with_point(server, **fields)
    return post(server, "point", {"id": "0001", "op": "choose", "point": "p1", "chosen": "A", "rationale": "r",
                                  "base_sha": a["sha"]})[1]


# ---------- the token ----------

@pytest.mark.parametrize("path, body", [("", None), ("/candidates", None), ("/0001", None), ("/0001/pack", None),
                                        *[(f"/{a}", {"id": "0001"}) for a in ACTIONS]])
def test_adr_routes_need_the_app_token(app_server, portal_server, path, body):
    url = f"/api/app/adr{path}"
    for server, token in ((app_server, None), (app_server, "nope"), (portal_server, None)):
        code, answer = call(server + url, body, token=token)
        assert code == 403 and answer["app"] is True


@pytest.mark.parametrize("path, body", [("", None), ("/0001", None), ("/new", {"title": "A", "kind": "new"})])
def test_a_portal_without_the_app_token_refuses_even_a_token(portal_server, path, body):
    code, answer = call(f"{portal_server}/api/app/adr{path}", body, token=TOKEN)
    assert code == 403 and answer["app"] is True


# ---------- reading ----------

def test_the_list_and_the_next_number(app_server):
    assert call(api(app_server), token=TOKEN) == (200, {"adrs": [], "next": "0001"})
    framed(app_server)
    code, body = call(api(app_server), token=TOKEN)
    assert code == 200 and body["next"] == "0002"
    assert [(a["id"], a["chip"], a["points"]) for a in body["adrs"]] == [("0001", "running", {"total": 0, "decided": 0})]


def test_candidates_of_a_fresh_project_is_an_empty_list(app_server):
    assert call(f"{api(app_server)}/candidates", token=TOKEN) == (200, {"candidates": []})


def test_one_adr_and_its_pack(app_server):
    framed(app_server)
    code, a = call(f"{api(app_server)}/0001", token=TOKEN)
    assert code == 200 and a["id"] == "0001" and a["state"]["phase"] == "problem" and isinstance(a["points"], list)
    assert call(f"{api(app_server)}/0001/pack", token=TOKEN)[0] == 404                      # nothing gathered yet
    post(app_server, "pack", {"id": "0001"})
    code, pack = call(f"{api(app_server)}/0001/pack", token=TOKEN)
    assert code == 200 and pack["summary"]["files"] == 1 and pack["markdown"]


@pytest.mark.parametrize("path", ["0042", "0042/pack", "42", "abc", "0001/"])
def test_an_unknown_adr_is_a_404(app_server, path):
    code, body = call(f"{api(app_server)}/{path}", token=TOKEN)
    assert code == 404 and "error" in body


def test_the_404_names_the_adr(app_server):
    assert call(f"{api(app_server)}/0042", token=TOKEN)[1] == {"error": "no ADR 0042"}
    assert call(f"{api(app_server)}/abc/pack", token=TOKEN)[1] == {"error": "no ADR abc"}
    assert "0042" in call(f"{api(app_server)}/0042/pack", token=TOKEN)[1]["error"]
    assert call(f"{api(app_server)}/0001/nope", token=TOKEN)[0] == 404


def test_an_unknown_action_is_a_404(app_server):
    assert post(app_server, "nope", {})[0] == 404


# ---------- the whole way ----------

def test_a_decision_from_new_to_accepted(app_server):
    u = api(app_server)
    code, a = call(f"{u}/new", {"title": "Sessions", "kind": "new", "touches": ["api:pom.xml"]}, token=TOKEN)
    assert code == 200 and a["id"] == "0001"
    assert call(f"{u}/pack", {"id": "0001"}, token=TOKEN)[1]["summary"]["files"] == 1
    a = call(f"{u}/write", {"id": "0001"}, token=TOKEN)[1]
    a = call(f"{u}/point", {"id": "0001", "op": "add", "question": "Where?", "base_sha": a["sha"],
                            "options": [{"name": "Redis"}, {"name": "Postgres"}]}, token=TOKEN)[1]
    a = call(f"{u}/point", {"id": "0001", "op": "choose", "point": "p1", "chosen": "A", "rationale": "r",
                            "base_sha": a["sha"]}, token=TOKEN)[1]
    code, a = call(f"{u}/accept", {"id": "0001", "attendees": ["LA"], "base_sha": a["sha"]}, token=TOKEN)
    assert code == 200 and a["status"] == "accepted"
    assert call(u, token=TOKEN)[1]["adrs"][0]["chip"] == "accepted"


def test_the_person_is_recorded_and_the_review_attendees_are_kept(app_server, kit):
    a = decided(app_server)
    assert post(app_server, "attendees", {"id": "0001", "attendees": ["LA", "MP"]})[1]["state"]["attendees"] == ["LA", "MP"]
    code, out = post(app_server, "accept", {"id": "0001", "by": "Ana Diaz", "base_sha": a["sha"]})
    assert code == 200 and out["state"]["attendees"] == ["LA", "MP"] and out["state"]["decided"]["by"] == "Ana Diaz"


def test_without_a_name_the_decision_is_taken_by_the_git_user(app_server):
    a = decided(app_server)
    assert post(app_server, "accept", {"id": "0001", "base_sha": a["sha"]})[1]["state"]["decided"]["by"] == "Test"


def test_given_attendees_replace_those_of_the_review(app_server):
    a = decided(app_server)
    post(app_server, "attendees", {"id": "0001", "attendees": ["LA"]})
    assert post(app_server, "accept", {"id": "0001", "attendees": ["MP"], "base_sha": a["sha"]})[1]["state"]["attendees"] == ["MP"]


def test_a_rejection_needs_its_reason(app_server):
    a = written(app_server)
    code, body = post(app_server, "reject", {"id": "0001", "base_sha": a["sha"]})
    assert code == 400 and "reason" in body["error"]
    code, out = post(app_server, "reject", {"id": "0001", "why": "not now", "base_sha": a["sha"]})
    assert code == 200 and out["status"] == "rejected"


def test_a_part_and_the_review_of_an_adr_the_kit_did_not_write(app_server, kit):
    folder = kit.root / "docs" / "decisions"
    folder.mkdir(parents=True)
    (folder / "0003-jpa.md").write_text("# 0003 — JPA\n\n## Estado\n\nPropuesto\n\n## Contexto\n\nwhy\n", encoding="utf-8")
    before = (folder / "0003-jpa.md").read_bytes()
    legacy = call(f"{api(app_server)}/0003", token=TOKEN)[1]
    assert legacy["legacy"] is True and legacy["state"] is None and (folder / "0003-jpa.md").read_bytes() == before
    code, started = post(app_server, "review", {"id": "0003"})
    assert code == 200 and started["state"]["phase"] == "review"
    code, out = post(app_server, "part", {"id": "0003", "part": "context", "action": "approve", "base_sha": started["sha"]})
    assert code == 200 and [p for p in out["parts"] if p["id"] == "context"][0]["status"] == "approved"


def test_a_decided_adr_the_kit_did_not_write_is_not_reopened(app_server, kit):
    folder = kit.root / "docs" / "decisions"
    folder.mkdir(parents=True)
    (folder / "0003-jpa.md").write_text("# 0003 — JPA\n\n## Estado\n\nAceptada\n", encoding="utf-8")
    code, body = post(app_server, "review", {"id": "0003"})
    assert (code, body) == (400, {"error": "ADR 0003 is already accepted: supersede it with a new ADR instead"})
    assert call(f"{api(app_server)}/0003", token=TOKEN)[1]["state"] is None


def test_a_part_is_edited(app_server):
    a = written(app_server)
    code, out = post(app_server, "part", {"id": "0001", "part": "context", "action": "edit", "text": "Because.",
                                          "base_sha": a["sha"]})
    assert code == 200 and out["sections"]["context"] == "Because." and out["sha"] != a["sha"]


def test_a_number_taken_meanwhile_is_told_when_the_file_is_written(app_server, kit):
    framed(app_server)
    folder = kit.root / "docs" / "decisions"
    folder.mkdir(parents=True)
    (folder / "0001-taken.md").write_text("# 0001 — Taken\n\n## Status\n\nAccepted\n", encoding="utf-8")
    code, out = post(app_server, "write", {"id": "0001"})
    assert code == 200 and out["id"] == "0002" and out["notice"] == {"renumbered": {"from": "0001", "to": "0002"}}


# ---------- a stale save ----------

def test_a_stale_part_is_a_409_with_the_current_sha(app_server, kit):
    u = api(app_server)
    call(f"{u}/new", {"title": "A", "kind": "new"}, token=TOKEN)
    a = call(f"{u}/write", {"id": "0001"}, token=TOKEN)[1]
    code, body = call(f"{u}/part", {"id": "0001", "part": "context", "action": "edit", "text": "x", "base_sha": "old"},
                      token=TOKEN)
    assert code == 409 and body["sha"] == a["sha"] and "changed" in body["error"]
    assert call(f"{u}/0001", token=TOKEN)[1]["sha"] == a["sha"]                              # nothing was overwritten


@pytest.mark.parametrize("action, extra", [("point", {"op": "add", "question": "Q", "options": [{"name": "a"}, {"name": "b"}]}),
                                           ("accept", {}), ("reject", {"why": "no"})])
def test_every_save_checks_the_file_it_started_from(app_server, action, extra):
    a = decided(app_server)
    code, body = post(app_server, action, {"id": "0001", "base_sha": "old", **extra})
    assert code == 409 and body["sha"] == a["sha"]


def test_a_busy_lock_is_a_409_to_try_again(app_server, adr, monkeypatch):
    from lib.harness.locks import LockBusy

    def busy(_id):
        raise LockBusy(Path("adr.lock"), {"pid": 1})
    monkeypatch.setattr(adr, "write_without_ai", busy)
    code, body = post(app_server, "write", {"id": "0001"})
    assert code == 409 and body == {"error": "another change to this ADR is being saved: try again"}


# ---------- bad input ----------

@pytest.mark.parametrize("body, code", [({"title": "", "kind": "new"}, 400), ({"title": "A", "kind": "maybe"}, 400),
                                        ({"title": "A", "kind": "new", "touches": "api:x"}, 400),
                                        ({"title": 5, "kind": "new"}, 400), ({"kind": "new"}, 400),
                                        ({"title": "A", "kind": "new", "problem": ["x"]}, 400),
                                        ({"title": "A", "kind": "new", "drivers": [1]}, 400),
                                        ({"title": "A", "kind": "new", "supersedes": 3}, 400),
                                        ({"title": "A", "kind": "new", "supersedes": "x"}, 400),
                                        ({"title": "A", "kind": "retro"}, 200)])
def test_bad_input_is_a_400(app_server, body, code):
    assert call(f"{app_server}/api/app/adr/new", body, token=TOKEN)[0] == code


def test_a_bad_input_creates_nothing(app_server):
    post(app_server, "new", {"title": "A", "kind": "new", "touches": "api:x"})
    assert call(api(app_server), token=TOKEN)[1] == {"adrs": [], "next": "0001"}


@pytest.mark.parametrize("action, body", [
    ("write", {}), ("write", {"id": 1}), ("pack", {"id": None}), ("review", {"id": ["0001"]}),
    ("part", {"id": "0001", "part": "context", "action": "approve"}),
    ("part", {"id": "0001", "part": "context", "action": "approve", "base_sha": 5}),
    ("part", {"id": "0001", "part": "context", "action": "edit", "text": 7, "base_sha": "x"}),
    ("part", {"id": "0001", "part": ["context"], "action": "edit", "base_sha": "x"}),
    ("point", {"id": "0001", "op": "add", "question": ["Q"], "base_sha": "x"}),
    ("point", {"id": "0001", "op": "add", "options": "A, B", "base_sha": "x"}),
    ("point", {"id": "0001", "op": "choose", "point": 1, "base_sha": "x"}),
    ("point", {"id": "0001", "base_sha": "x"}),
    ("attendees", {"id": "0001", "attendees": "LA"}), ("attendees", {"id": "0001", "attendees": [1]}),
    ("attendees", {"id": "0001"}),
    ("accept", {"id": "0001", "attendees": "LA", "base_sha": "x"}),
    ("reject", {"id": "0001", "why": 3, "base_sha": "x"})])
def test_a_field_of_the_wrong_shape_is_a_400(app_server, action, body):
    framed(app_server)
    code, answer = post(app_server, action, body)
    assert code == 400 and "must be" in answer["error"]


def test_the_wrong_state_for_an_action_is_a_400(app_server):
    framed(app_server)
    code, body = post(app_server, "accept", {"id": "0001", "base_sha": ""})
    assert code == 400 and "write the ADR first" in body["error"]


def test_a_body_that_is_not_an_object_is_a_400(kit):
    from lib import adr_api
    assert adr_api.post("new", ["x"], "Ana")[1] == 400 and adr_api.post("nope", ["x"], "Ana")[1] == 404


def test_who_decides_must_be_a_name(app_server, kit):
    from lib import adr_api
    a = decided(app_server)
    body, code = adr_api.post("accept", {"id": "0001", "base_sha": a["sha"]}, 4)
    assert code == 400 and "name" in body["error"]


@pytest.mark.parametrize("action", [a for a in ACTIONS if a != "new"])
def test_an_unknown_id_is_a_404_on_every_action(app_server, action):
    code, body = post(app_server, action, {"id": "0042", "part": "context", "action": "approve", "op": "add",
                                           "attendees": [], "why": "x", "base_sha": "x"})
    assert code == 404 and body == {"error": "no ADR 0042"}


# ---------- the decisions a doc page lists ----------

def accepted(adr, touches):
    a = adr.write_without_ai(adr.new({"title": "T", "kind": "new", "touches": touches})["id"])
    a = adr.part(a["id"], "decision", "edit", "Yes.", base_sha=a["sha"])
    return adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])


def orders_page(kit, sources=("api:src/S.java",)):
    f = kit.root / "docs" / "orders.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    listed = "x-sources:\n" + "".join(f"  - {s}\n" for s in sources)
    f.write_text(f"---\ntitle: Orders\n{listed}---\n# Orders\n", encoding="utf-8")


@pytest.mark.parametrize("server, token", [("app_server", TOKEN), ("app_server", None), ("portal_server", None)])
def test_a_doc_page_lists_the_accepted_adrs_that_cover_it(request, kit, adr, server, token):
    base = request.getfixturevalue(server)
    orders_page(kit)
    out = accepted(adr, ["api:src/S.java"])
    code, doc = call(f"{base}/api/doc?path=orders.md", token=token)
    assert code == 200 and doc["decisions"] == [{"id": out["id"], "title": "T", "path": out["path"], "kind": "new",
                                                 "implementation": "pending"}]


def test_a_page_no_adr_covers_lists_none(portal_server, kit, adr):
    orders_page(kit, ["api:src/Other.java"])
    accepted(adr, ["api:src/S.java"])
    assert call(f"{portal_server}/api/doc?path=orders.md")[1]["decisions"] == []


def test_a_failure_listing_the_decisions_never_breaks_reading_a_page(portal_server, kit, adr, monkeypatch):
    orders_page(kit)

    def broken(_logical):
        raise OSError("disk")
    monkeypatch.setattr(adr, "covering", broken)
    code, doc = call(f"{portal_server}/api/doc?path=orders.md")
    assert code == 200 and doc["decisions"] == [] and doc["raw"]
