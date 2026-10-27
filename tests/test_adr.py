"""An ADR's working state and the actions that need no model (`lib/adr.py`): the list, numbering, writing the proposed
file, review parts and decision points. An ADR the kit did not write is read as it is and never rewritten."""
from __future__ import annotations

import importlib
import threading

import pytest

LEGACY = "# 0003 — JPA\n\n## Estado\n\nPropuesto <!-- x -->\n\n## Contexto\n\nwhy\n\n## Notas\n\nkeep\n"


@pytest.fixture
def adr(kit):
    return importlib.import_module("lib.adr")


def decisions(kit):
    folder = kit.root / "docs" / "decisions"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def written(adr, **fields):
    return adr.write_without_ai(adr.new({"title": "A", "kind": "new", **fields})["id"])


def two_options(adr, a, question="Where?"):
    return adr.point(a["id"], "add", {"question": question, "options": [{"name": "Redis"}, {"name": "Postgres"}]}, a["sha"])


def test_new_reserves_the_next_number_and_lists(adr, kit):
    (decisions(kit) / "0007-old.md").write_text("# 0007 — Old\n\n## Status\n\nAccepted\n", encoding="utf-8")
    got = adr.new({"title": "Sessions in Redis", "kind": "new", "touches": ["api:src/main/java/demo/Api.java"]})
    assert got["id"] == "0008" and got["state"]["phase"] == "problem" and got["state"]["implementation"] == "pending"
    rows = adr.list_adrs()
    assert [r["id"] for r in rows] == ["0008", "0007"]
    assert rows[1]["legacy"] is True and rows[1]["chip"] == "accepted" and rows[0]["chip"] == "running"


def test_a_framed_adr_has_no_file_yet(adr, kit):
    got = adr.new({"title": "Sessions in Redis", "kind": "retro", "problem": "why", "drivers": ["fast", " "],
                   "touches": ["api:a.java", "api:a.java", "web:b.ts"], "supersedes": "3"})
    assert got["state"] == {
        "id": "0001", "slug": "sessions-in-redis", "kind": "retro", "mode": "manual", "title": "Sessions in Redis",
        "problem": "why", "drivers": ["fast"], "constraints": [], "options_hint": [],
        "touches": ["api:a.java", "web:b.ts"], "phase": "problem", "parts": {}, "points": [], "attendees": [],
        "supersedes": "0003", "implementation": "n/a"}
    assert got["sha"] == "" and got["path"] == "" and got["raw"] == "" and got["notice"] is None
    assert got["affected"] == [] and set(got["sections"]) == set(importlib.import_module("lib.adr_doc").KEYS)
    assert all(text == "" for text in got["sections"].values())
    assert [p["id"] for p in got["parts"]] == ["context", "drivers", "options", "consequences", "confirmation", "affected"]
    assert got["repos"] == ["api", "web"] and got["points"] == []
    assert not (kit.root / "docs" / "decisions").exists()
    assert adr.state_file("0001").read_text(encoding="utf-8").startswith("id: '0001'\nslug: sessions-in-redis\n")


@pytest.mark.parametrize("fields, msg", [
    ({"title": "A", "kind": "maybe"}, "kind"),
    ({"title": "A"}, "kind"),
    ({"title": "  ", "kind": "new"}, "title"),
    ({"title": "A", "kind": "new", "touches": "api:a.java"}, "touches"),
    ({"title": "A", "kind": "new", "drivers": ["ok", 3]}, "drivers"),
    ({"title": "A", "kind": "new", "problem": ["x"]}, "problem"),
    ({"title": "A", "kind": "new", "supersedes": "../x"}, "supersedes"),
])
def test_a_framing_with_bad_input_is_refused(adr, fields, msg):
    with pytest.raises(adr.AdrError, match=msg):
        adr.new(fields)
    assert adr.list_adrs() == []


def test_a_legacy_adr_is_never_rewritten_by_reading_or_starting_a_review(adr, kit):
    f = decisions(kit) / "0003-jpa.md"
    f.write_text(LEGACY, encoding="utf-8")
    assert adr.get("0003")["status"] == "proposed"
    st = adr.start_review("0003")["state"]
    assert st["phase"] == "review" and st["kind"] == "retro" and st["points"] == [] and f.read_text(encoding="utf-8") == LEGACY
    assert st["title"] == "JPA" and st["slug"] == "jpa" and st["implementation"] == "n/a"
    row = adr.list_adrs()[0]
    assert row["legacy"] is False and row["chip"] == "review" and row["title"] == "JPA" and row["path"] == "decisions/0003-jpa.md"


def test_starting_a_review_twice_keeps_the_first_state(adr, kit):
    (decisions(kit) / "0003-jpa.md").write_text(LEGACY, encoding="utf-8")
    adr.start_review("0003")
    adr.set_attendees("0003", ["LA"])
    assert adr.start_review("0003")["state"]["attendees"] == ["LA"]
    with pytest.raises(KeyError):
        adr.start_review("0004")


@pytest.mark.parametrize("heading, title", [
    ("# 0003 — JPA", "JPA"), ("# 3. Record architecture decisions", "Record architecture decisions"),
    ("# ADR-0003: Use JPA", "Use JPA"), ("# 0003-JPA", "JPA"), ("# Plain title", "Plain title"), ("# 30 apples", "30 apples")])
def test_a_legacy_title_loses_its_number(adr, kit, heading, title):
    (decisions(kit) / "0003-x.md").write_text(heading + "\n\n## Status\n\nAccepted\n", encoding="utf-8")
    assert adr.list_adrs()[0]["title"] == title


def test_a_legacy_row_reads_status_repos_and_date_from_the_file(adr, kit):
    (decisions(kit) / "0005-x.md").write_text(
        "---\ntype: decision\ntitle: 0005 — X\nx-sources:\n  - api:a.java#L1\n  - repo://web/b.ts\n  - https://x.io/p\n"
        "  - cam-docs:overview.md\n---\n# 0005 — X\n\n## Status\n\nAccepted (2026-10-21)\n", encoding="utf-8")
    row = adr.list_adrs()[0]
    assert (row["status"], row["repos"], row["decided"], row["kind"]) == ("accepted", ["api", "web"], "2026-10-21", "retro")
    assert row["points"] == {"total": 0, "decided": 0} and row["updated"].endswith("+00:00")


def test_the_decided_date_of_a_state_wins_over_the_file(adr, kit):
    (decisions(kit) / "0005-x.md").write_text("# 0005 — X\n\n## Status\n\nAccepted (2026-10-21)\n", encoding="utf-8")
    state = adr.start_review("0005")["state"]
    assert adr.list_adrs()[0]["decided"] == "2026-10-21"
    adr.save_state({**state, "decided": {"date": "2026-11-02", "by": "T", "driver": "T"}})
    assert adr.list_adrs()[0]["decided"] == "2026-11-02"
    adr.save_state({**state, "decided": "yesterday"})
    assert adr.list_adrs()[0]["decided"] == "2026-10-21"


def test_a_state_without_a_slug_still_writes_a_named_file(adr, kit):
    got = adr.new({"title": "Sessions in Redis", "kind": "new"})
    adr.save_state({k: v for k, v in got["state"].items() if k != "slug"})
    assert adr.write_without_ai(got["id"])["path"] == "decisions/0001-sessions-in-redis.md"


def test_writing_without_ai_renders_the_proposed_file_and_opens_the_review(adr, kit):
    a = written(adr, problem="why", touches=["api:a.java"])
    f = kit.root / "docs" / "decisions" / "0001-a.md"
    assert a["path"] == "decisions/0001-a.md" and f.read_text(encoding="utf-8").startswith("---\n")
    assert a["state"]["phase"] == "review" and a["chip"] == "review" and a["notice"] is None
    assert a["sections"]["context"] == "why" and a["sha"] == kit.docs.body_sha(kit.docs.split_fm(a["raw"])[1])
    fm, _ = kit.docs.split_fm(a["raw"])
    assert fm["x-owner"] == "ai"


def test_writing_without_ai_renumbers_when_the_number_was_taken(adr, kit):
    got = adr.new({"title": "A", "kind": "new"})
    (decisions(kit) / f"{got['id']}-pulled.md").write_text("# pulled\n", encoding="utf-8")
    out = adr.write_without_ai(got["id"])
    assert out["notice"] == {"renumbered": {"from": got["id"], "to": "0002"}} and out["id"] == "0002"
    assert not adr.state_file(got["id"]).exists() and adr.state_file("0002").exists()
    assert (decisions(kit) / "0002-a.md").read_text(encoding="utf-8").count("# 0002 — A") == 1
    assert (decisions(kit) / "0001-pulled.md").read_text(encoding="utf-8") == "# pulled\n"
    assert out["state"]["id"] == "0002" and [r["id"] for r in adr.list_adrs()] == ["0002", "0001"]


def test_renumbering_takes_the_evidence_cache_along(adr, kit):
    got = adr.new({"title": "A", "kind": "new"})
    cache = kit.common.CACHE / "adr" / got["id"]
    cache.mkdir(parents=True)
    (cache / "pack.json").write_text("{}", encoding="utf-8")
    (decisions(kit) / f"{got['id']}-pulled.md").write_text("# pulled\n", encoding="utf-8")
    adr.write_without_ai(got["id"])
    assert not cache.exists() and (kit.common.CACHE / "adr" / "0002" / "pack.json").exists()


def test_writing_twice_keeps_the_edits_of_the_first_time(adr, kit):
    a = written(adr)
    a = adr.part(a["id"], "context", "edit", "mine", base_sha=a["sha"])
    again = adr.write_without_ai(a["id"])
    assert again["sections"]["context"] == "mine" and again["notice"] is None and again["id"] == a["id"]


def test_writing_a_legacy_adr_or_an_unknown_one_is_refused(adr, kit):
    (decisions(kit) / "0003-jpa.md").write_text(LEGACY, encoding="utf-8")
    with pytest.raises(adr.AdrError):
        adr.write_without_ai("0003")
    with pytest.raises(KeyError):
        adr.write_without_ai("0009")
    assert (decisions(kit) / "0003-jpa.md").read_text(encoding="utf-8") == LEGACY


def test_a_stale_save_is_refused(adr, kit):
    a = adr.write_without_ai(adr.new({"title": "A", "kind": "new"})["id"])
    f = kit.root / "docs" / a["path"]
    f.write_text(f.read_text(encoding="utf-8") + "\nedited elsewhere\n", encoding="utf-8")
    with pytest.raises(adr.AdrConflict) as exc:
        adr.part(a["id"], "context", "edit", "mine", base_sha=a["sha"])
    assert exc.value.sha == adr.get(a["id"])["sha"] != a["sha"]
    assert "edited elsewhere" in f.read_text(encoding="utf-8") and "mine" not in f.read_text(encoding="utf-8")
    with pytest.raises(adr.AdrConflict):
        adr.point(a["id"], "add", {"question": "Q", "options": [{"name": "x"}, {"name": "y"}]}, a["sha"])
    assert adr.get(a["id"])["state"]["points"] == []


def test_approving_a_part_leaves_the_file_alone(adr, kit):
    a = written(adr)
    f = kit.root / "docs" / a["path"]
    before = f.read_bytes()
    out = adr.part(a["id"], "context", "approve", None, a["sha"])
    assert out["state"]["parts"] == {"context": "approved"} and f.read_bytes() == before and out["sha"] == a["sha"]
    out = adr.part(a["id"], "drivers", "defer", None, a["sha"])
    assert {p["id"]: p["status"] for p in out["parts"]}["drivers"] == "deferred"
    assert {p["id"]: p["status"] for p in out["parts"]}["options"] == "pending"
    with pytest.raises(adr.AdrConflict):
        adr.part(a["id"], "context", "approve", None, "old")


def test_editing_a_part_replaces_only_that_section(adr, kit):
    a = written(adr, problem="why")
    f = kit.root / "docs" / a["path"]
    out = adr.part(a["id"], "consequences", "edit", "Cheaper.\n\nSlower.", a["sha"])
    assert out["sections"]["consequences"] == "Cheaper.\n\nSlower." and out["state"]["parts"] == {"consequences": "edited"}
    assert out["sha"] != a["sha"] and out["sections"]["context"] == "why"
    assert f.read_text(encoding="utf-8") == a["raw"].replace(
        "TODO(question): what gets easier and what gets harder?", "Cheaper.\n\nSlower.")
    out = adr.part(a["id"], "diagram", "edit", "```mermaid\nflowchart LR\n```", out["sha"])
    assert [p["id"] for p in out["parts"]][-4:] == ["diagram", "consequences", "confirmation", "affected"]


@pytest.mark.parametrize("part, action, text, msg", [
    ("nope", "approve", None, "unknown part"), ("context", "burn", None, "action"), ("context", "edit", None, "text"),
    ("affected", "edit", "x", "computed"), ("point:p1", "approve", None, "unknown part")])
def test_a_bad_part_request_is_refused(adr, part, action, text, msg):
    a = written(adr)
    with pytest.raises(adr.AdrError, match=msg):
        adr.part(a["id"], part, action, text, a["sha"])
    assert adr.get(a["id"])["sha"] == a["sha"]


def test_points_need_two_options_and_render_into_the_decision(adr):
    a = adr.write_without_ai(adr.new({"title": "A", "kind": "new"})["id"])
    with pytest.raises(adr.AdrError, match="two options"):
        adr.point(a["id"], "add", {"question": "Where?", "options": [{"name": "Redis"}]}, a["sha"])
    with pytest.raises(adr.AdrError, match="two options"):
        adr.point(a["id"], "add", {"question": "Where?", "options": [{"name": "Redis"}, {"name": " "}]}, a["sha"])
    with pytest.raises(adr.AdrError, match="question"):
        adr.point(a["id"], "add", {"question": " ", "options": [{"name": "Redis"}, {"name": "Postgres"}]}, a["sha"])
    a = adr.point(a["id"], "add", {"question": "Where?", "options": [{"name": "Redis"}, {"name": "Postgres"}]}, a["sha"])
    assert a["points"][0]["id"] == "p1" and [o["id"] for o in a["points"][0]["options"]] == ["A", "B"]
    assert "#### P1 · Where?" in a["sections"]["decision"]
    assert [p["id"] for p in a["parts"]][:3] == ["context", "drivers", "point:p1"]


def test_a_point_block_keeps_the_text_written_before_it(adr, kit):
    a = written(adr)
    a = two_options(adr, a)
    decision = a["sections"]["decision"]
    assert decision.startswith("To be decided in review: see the decision points.\n\n### Decision points\n\n#### P1 · Where?")
    a = adr.part(a["id"], "decision", "edit", "Context for the meeting.", a["sha"])
    assert a["sections"]["decision"].startswith("Context for the meeting.\n\n### Decision points\n\n#### P1")
    a = two_options(adr, a, "When?")
    assert [p["id"] for p in a["points"]] == ["p1", "p2"] and a["sections"]["decision"].count("#### P") == 2
    assert a["sections"]["decision"].startswith("Context for the meeting.\n\n### Decision points")
    a = adr.point(a["id"], "remove", {"point": "p1"}, a["sha"])
    assert [p["id"] for p in a["points"]] == ["p2"] and "#### P1" not in a["sections"]["decision"]
    a = two_options(adr, a, "Who?")
    assert [p["id"] for p in a["points"]] == ["p2", "p3"]
    a = adr.point(a["id"], "remove", {"point": "p2"}, a["sha"])
    a = adr.point(a["id"], "remove", {"point": "P3"}, a["sha"])
    assert a["points"] == [] and a["sections"]["decision"] == "Context for the meeting." and a["state"]["parts"] == {"decision": "edited"}
    assert "### Decision points" not in a["raw"]


def test_choosing_decides_a_point_and_the_list_counts_it(adr, kit):
    a = two_options(adr, written(adr))
    assert adr.list_adrs()[0]["points"] == {"total": 1, "decided": 0}
    a = adr.point(a["id"], "choose", {"point": "p1", "chosen": "B", "rationale": "zero\n infra"}, a["sha"])
    p = a["points"][0]
    assert (p["chosen"], p["other"], p["rationale"], p["deferred"]) == ("B", None, "zero infra", False)
    assert adr.list_adrs()[0]["points"] == {"total": 1, "decided": 1}
    assert {x["id"]: x["status"] for x in a["parts"]}["point:p1"] == "approved"
    a = adr.point(a["id"], "choose", {"point": "p1", "other": "Hazelcast", "rationale": "ops"}, a["sha"])
    p = a["points"][0]
    assert (p["chosen"], p["other"]) == (None, "Hazelcast") and adr.list_adrs()[0]["points"]["decided"] == 1
    a = adr.point(a["id"], "defer", {"point": "p1"}, a["sha"])
    assert a["points"][0]["deferred"] is True and adr.list_adrs()[0]["points"] == {"total": 1, "decided": 0}
    assert {x["id"]: x["status"] for x in a["parts"]}["point:p1"] == "deferred"
    a = adr.point(a["id"], "choose", {"point": "p1", "chosen": "a"}, a["sha"])
    assert a["points"][0]["chosen"] == "A" and a["points"][0]["deferred"] is False


@pytest.mark.parametrize("op, data, msg", [
    ("choose", {"point": "p1"}, "one option"),
    ("choose", {"point": "p1", "chosen": "A", "other": "x"}, "one option"),
    ("choose", {"point": "p1", "chosen": "Z"}, "no option"),
    ("choose", {"point": "p9", "chosen": "A"}, "no decision point"),
    ("choose", {"chosen": "A"}, "no decision point"),
    ("defer", {"point": "p9"}, "no decision point"),
    ("remove", {}, "no decision point"),
    ("burn", {"point": "p1"}, "op"),
    ("add", {"question": "Q", "options": "A,B"}, "options")])
def test_a_bad_point_request_is_refused(adr, op, data, msg):
    a = two_options(adr, written(adr))
    with pytest.raises(adr.AdrError, match=msg):
        adr.point(a["id"], op, data, a["sha"])
    assert adr.get(a["id"])["sha"] == a["sha"] and adr.get(a["id"])["state"]["points"] == a["state"]["points"]


def test_an_option_keeps_its_pros_and_cons(adr):
    a = written(adr)
    a = adr.point(a["id"], "add", {"question": "Q", "options": [
        {"name": "Redis", "pros": ["fast", " "], "cons": ["one more service"]}, {"name": "Postgres"}]}, a["sha"])
    assert a["points"][0]["options"][0] == {"id": "A", "name": "Redis", "pros": ["fast"], "cons": ["one more service"]}
    assert "- **A · Redis** — + fast; − one more service" in a["sections"]["decision"]


def test_editing_needs_the_file_and_a_state(adr, kit):
    got = adr.new({"title": "A", "kind": "new"})
    with pytest.raises(adr.AdrError, match="write the ADR first: camaron adr write 0001"):
        adr.part(got["id"], "context", "approve", None, "")
    with pytest.raises(adr.AdrError, match="write the ADR first: camaron adr write 0001"):
        adr.point(got["id"], "add", {"question": "Q", "options": [{"name": "x"}, {"name": "y"}]}, "")
    (decisions(kit) / "0003-jpa.md").write_text(LEGACY, encoding="utf-8")
    sha = adr.get("0003")["sha"]
    with pytest.raises(adr.AdrError, match="review"):
        adr.part("0003", "context", "edit", "mine", sha)
    with pytest.raises(adr.AdrError, match="review"):
        adr.set_attendees("0003", ["LA"])
    assert (decisions(kit) / "0003-jpa.md").read_text(encoding="utf-8") == LEGACY
    for call in (lambda: adr.part("9999", "context", "approve", None, ""), lambda: adr.set_attendees("9999", [])):
        with pytest.raises(KeyError):
            call()


def test_an_accepted_adr_can_no_longer_be_edited_here(adr, kit):
    a = written(adr)
    adr.save_state({**a["state"], "phase": "accepted"})
    with pytest.raises(adr.AdrError, match="accepted"):
        adr.part(a["id"], "context", "edit", "late", a["sha"])
    with pytest.raises(adr.AdrError, match="accepted"):
        adr.point(a["id"], "add", {"question": "Q", "options": [{"name": "x"}, {"name": "y"}]}, a["sha"])
    assert "late" not in (kit.root / "docs" / a["path"]).read_text(encoding="utf-8")


def test_a_file_that_is_not_utf8_is_not_edited(adr, kit):
    f = decisions(kit) / "0003-jpa.md"
    f.write_bytes("# 0003 - JPA\n\n## Contexto\n\nañade\n".encode("cp1252"))
    assert adr.get("0003")["title"] == "JPA"
    adr.start_review("0003")
    before = f.read_bytes()
    with pytest.raises(adr.AdrError, match="UTF-8"):
        adr.part("0003", "context", "edit", "mine", adr.get("0003")["sha"])
    assert f.read_bytes() == before


def test_an_edit_keeps_the_line_endings_of_the_rest_of_the_file(adr, kit):
    f = decisions(kit) / "0004-x.md"
    raw = "# 0004 — X\r\n\r\n## Context\r\n\r\nwhy\r\n\r\n## Notes\r\n\r\nkeep\r\n".encode("utf-8")
    f.write_bytes(raw)
    adr.start_review("0004")
    adr.part("0004", "context", "edit", "mine", adr.get("0004")["sha"])
    assert f.read_bytes() == raw.replace(b"why", b"mine")


def test_attendees_are_trimmed_and_kept_once(adr):
    a = written(adr)
    out = adr.set_attendees(a["id"], [" LA ", "MP", "", "LA"])
    assert out["state"]["attendees"] == ["LA", "MP"] and out["sha"] == a["sha"]
    with pytest.raises(adr.AdrError, match="attendees"):
        adr.set_attendees(a["id"], "LA")
    assert adr.set_attendees(a["id"], [])["state"]["attendees"] == []


def test_get_of_an_unknown_or_malformed_id_is_a_key_error(adr):
    for bad in ("9999", "../x", "1", "", None):
        with pytest.raises(KeyError):
            adr.get(bad)
    with pytest.raises(KeyError):
        adr.state_file("../../escape")


def test_a_damaged_state_never_breaks_the_list_nor_gets_overwritten(adr, kit):
    (decisions(kit) / "0003-jpa.md").write_text(LEGACY, encoding="utf-8")
    adr.state_file("0003").parent.mkdir(parents=True)
    adr.state_file("0003").write_text("<<<<<<< ours\nid: '0003'\n=======\nid: x\n>>>>>>> theirs\n", encoding="utf-8")
    adr.state_file("0004").write_text("- not\n- a mapping\n", encoding="utf-8")
    assert [r["id"] for r in adr.list_adrs()] == ["0003"] and adr.list_adrs()[0]["legacy"] is True
    with pytest.raises(adr.AdrError, match="0003.yaml"):
        adr.get("0003")
    with pytest.raises(adr.AdrError, match="0003.yaml"):
        adr.start_review("0003")
    assert adr.next_id() == "0005"


def test_the_numbers_of_files_and_states_are_both_taken(adr, kit):
    adr.state_file("0002").parent.mkdir(parents=True)
    adr.state_file("0002").write_text("id: '0002'\n", encoding="utf-8")
    (decisions(kit) / "0004-x.md").write_text("# 0004 — x\n", encoding="utf-8")
    (decisions(kit) / "notes.md").write_text("# notes\n", encoding="utf-8")
    assert adr.next_id() == "0005"


def test_two_framings_at_once_never_share_a_number(adr):
    ids, errors = [], []

    def run():
        try:
            ids.append(adr.new({"title": "A", "kind": "new"})["id"])
        except Exception as e:                              # noqa: BLE001
            errors.append(e)
    threads = [threading.Thread(target=run) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and sorted(ids) == [f"{n:04d}" for n in range(1, 7)]


def test_saving_a_state_leaves_no_temp_file_behind(adr):
    a = adr.new({"title": "A", "kind": "new"})
    adr.save_state({**a["state"], "title": "B"})
    assert [p.name for p in adr.state_file("0001").parent.iterdir()] == ["0001.yaml"]
    assert adr.load_state("0001")["title"] == "B" and adr.load_state("0002") is None


def test_the_chip_follows_the_phase_then_the_file(adr):
    chip = adr.chip
    assert [chip({"phase": p}, "proposed") for p in ("problem", "evidence", "review")] == ["running", "running", "review"]
    assert [chip({"phase": "accepted"}, s) for s in ("accepted", "superseded", "rejected", "deprecated")] == [
        "accepted", "superseded", "rejected", "deprecated"]
    assert chip(None, "proposed") == "proposed" and chip(None, "unknown") == "unknown" and chip({}, "accepted") == "accepted"
    assert set(adr.CHIPS) >= {chip(None, s) for s in ("proposed", "accepted", "rejected", "superseded", "deprecated", "unknown")}


def test_the_parts_of_a_review_follow_its_points_and_diagram(adr):
    state = {"points": [{"id": "p1"}, {"id": "p2"}]}
    assert adr.parts_of(state, {}) == ["context", "drivers", "point:p1", "point:p2", "options", "consequences",
                                       "confirmation", "affected"]
    assert "diagram" in adr.parts_of({"points": []}, {"diagram": "```mermaid\n```"})
    assert "diagram" not in adr.parts_of({"points": []}, {"diagram": ""})
    assert adr.KINDS == ("new", "retro") and adr.PHASES[0] == "problem" and adr.PHASES[-1] == "rejected"
