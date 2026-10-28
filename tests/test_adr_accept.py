"""The human decision on an ADR (`lib/adr.py`): accept, reject, supersede, and the pages an accepted ADR covers."""
from __future__ import annotations

import importlib
import re

import pytest

LEGACY = "# 0003 — JPA\n\n## Estado\n\nPropuesto <!-- x -->\n\n## Contexto\n\nwhy\n\n## Notas\n\nkeep\n"
OLD = "# 0001 — EhCache\n\n## Status\n\nAccepted\n\n## Context\n\nx\n"


@pytest.fixture
def adr(kit):
    return importlib.import_module("lib.adr")


@pytest.fixture
def doc(adr):
    return importlib.import_module("lib.adr_doc")


def decisions(kit):
    folder = kit.root / "docs" / "decisions"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def with_point(adr):
    a = adr.write_without_ai(adr.new({"title": "Sessions", "kind": "new", "touches": ["api:src/S.java"]})["id"])
    return adr.point(a["id"], "add", {"question": "Where?", "options": [{"name": "Redis"}, {"name": "Postgres"}]}, a["sha"])


def decided(adr, **choice):
    a = with_point(adr)
    return adr.point(a["id"], "choose", {"point": "p1", **choice}, a["sha"])


def read(kit, out):
    return kit.docs.split_fm((kit.root / "docs" / out["path"]).read_text(encoding="utf-8"))


def accepted_adr(adr, touches, **fields):
    a = adr.write_without_ai(adr.new({"title": "T", "kind": "new", "touches": touches, **fields})["id"])
    a = adr.part(a["id"], "decision", "edit", "Yes.", base_sha=a["sha"])
    return adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])


def page(kit, name, sources):
    f = kit.root / "docs" / name
    f.parent.mkdir(parents=True, exist_ok=True)
    listed = "x-sources:\n" + "".join(f"  - {s}\n" for s in sources) if sources else ""
    f.write_text(f"---\ntitle: P\n{listed}---\n# P\n", encoding="utf-8")
    return f


def test_accept_writes_the_outcome_owns_and_confirms(adr, kit):
    a = decided(adr, chosen="A", rationale="already used by notifications")
    out = adr.accept(a["id"], by="Test", attendees=["LA", "MP"], base_sha=a["sha"])
    fm, body = kit.docs.split_fm((kit.root / "docs" / out["path"]).read_text(encoding="utf-8"))
    assert fm["x-owner"] == "human" and fm["x-confirmed"]["by"] == "Test"
    assert kit.docs.trust_of(fm, kit.docs.body_sha(body)) == "confirmed"
    assert out["status"] == "accepted" and out["state"]["phase"] == "accepted"
    assert "**Where?** — Redis. already used by notifications" in out["sections"]["decision"]
    assert "#### P1" not in out["sections"]["decision"] and "LA, MP" in out["sections"]["decided_by"]


def test_accept_dates_the_decision_from_one_place(adr, kit, monkeypatch):
    monkeypatch.setattr(adr, "today", lambda: "2026-10-27")
    a = decided(adr, chosen="B", rationale="r")
    out = adr.accept(a["id"], by="Test", attendees=["LA"], base_sha=a["sha"])
    assert out["sections"]["status"] == "Accepted (2026-10-27)" and out["decided"] == "2026-10-27"
    assert out["state"]["decided"] == {"date": "2026-10-27", "by": "Test", "driver": "Test"}
    assert out["sections"]["decided_by"] == "- Date: 2026-10-27\n- Attendees: LA\n- Mode: manual\n- Led by: Test"
    assert adr.list_adrs()[0]["decided"] == "2026-10-27"


def test_today_is_an_iso_date(adr):
    assert re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", adr.today())


def test_accept_changes_the_status_decision_and_owner_and_nothing_else(adr, kit, doc):
    a = decided(adr, chosen="A", rationale="r")
    before_fm, before = kit.docs.split_fm(a["raw"])
    out = adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    fm, body = read(kit, out)
    assert {k: v for k, v in fm.items() if k not in ("x-owner", "x-confirmed")} == \
        {k: v for k, v in before_fm.items() if k != "x-owner"}
    for key in ("context", "consequences", "evidence"):
        assert doc.section(body, key) == doc.section(before, key)
    assert doc.section(before, "options") == "TODO(question): which options were considered?"
    assert doc.section(body, "options") == "### P1 · Where?\n\n- **A · Redis** (chosen)\n- **B · Postgres**"
    assert kit.docs.tldr(body) == kit.docs.tldr(before) and body.startswith(before.split("## Status")[0])
    assert doc.PLACEHOLDER not in body and "### Decision points" not in body


@pytest.mark.parametrize("options", [None, "", "<!-- which? -->"])
def test_accept_puts_what_the_points_weighed_in_an_empty_considered_options(adr, kit, doc, options):
    a = adr.write_without_ai(adr.new({"title": "Sessions", "kind": "new"})["id"])
    if options is not None:
        a = adr.part(a["id"], "options", "edit", options, base_sha=a["sha"])
    a = adr.point(a["id"], "add", {"question": "Where?", "options": [
        {"name": "Redis", "pros": ["fast"], "cons": ["one more service"]}, {"name": "Postgres", "pros": ["already there"]}]},
        a["sha"])
    a = adr.point(a["id"], "add", {"question": "Who?", "options": [{"name": "Gateway"}, {"name": "Each service"}]}, a["sha"])
    a = adr.point(a["id"], "choose", {"point": "p1", "chosen": "B", "rationale": "no new service"}, a["sha"])
    a = adr.point(a["id"], "choose", {"point": "p2", "other": "A job"}, a["sha"])
    out = adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert out["sections"]["options"] == (
        "### P1 · Where?\n\n- **A · Redis** — + fast; − one more service\n- **B · Postgres** (chosen) — + already there\n\n"
        "### P2 · Who?\n\n- **A · Gateway**\n- **B · Each service**")
    assert out["sections"]["decision"] == "**Where?** — Postgres. no new service\n\n**Who?** — A job."
    assert "TODO(question): which options" not in out["raw"] and out["raw"].count("## Considered options") == 1


def test_accept_adds_to_considered_options_a_person_wrote_only_the_options_it_does_not_name(adr, kit):
    a = decided(adr, chosen="A", rationale="r")
    written = "### A · redis\n\nWe run it for notifications."
    a = adr.part(a["id"], "options", "edit", written, base_sha=a["sha"])
    out = adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert out["sections"]["options"] == written + "\n\n### P1 · Where?\n\n- **B · Postgres**"
    assert out["sections"]["decision"] == "**Where?** — Redis. r"


def test_accept_leaves_considered_options_alone_when_they_name_every_option(adr, kit):
    a = decided(adr, chosen="A", rationale="r")
    written = "- Redis: in use\n- POSTGRES: a write per request"
    a = adr.part(a["id"], "options", "edit", written, base_sha=a["sha"])
    out = adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert out["sections"]["options"] == written


def test_accept_keeps_what_a_person_wrote_in_the_decision(adr, kit):
    a = decided(adr, chosen="A", rationale="r")
    a = adr.part(a["id"], "decision", "edit", "We go with Redis.", base_sha=a["sha"])
    out = adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert out["sections"]["decision"] == "We go with Redis.\n\n**Where?** — Redis. r"


@pytest.mark.parametrize("defer, msg", [(True, "P1 is deferred"), (False, "P1 has no choice")])
def test_accept_refuses_what_is_not_decided(adr, defer, msg):
    a = with_point(adr)
    if defer:
        a = adr.point(a["id"], "defer", {"point": "p1"}, a["sha"])
    with pytest.raises(adr.AdrError, match=msg):
        adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])


def test_accept_names_the_message_the_app_shows(adr):
    a = with_point(adr)
    with pytest.raises(adr.AdrError) as exc:
        adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert str(exc.value) == "point P1 has no choice yet"
    a = adr.point(a["id"], "defer", {"point": "p1"}, a["sha"])
    with pytest.raises(adr.AdrError) as exc:
        adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert str(exc.value) == "point P1 is deferred: decide it or remove it"


def test_accept_with_no_points_needs_a_written_decision(adr):
    a = adr.write_without_ai(adr.new({"title": "A", "kind": "retro"})["id"])
    with pytest.raises(adr.AdrError, match="Decision"):
        adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    a = adr.part(a["id"], "decision", "edit", "We keep JPA.", base_sha=a["sha"])
    assert adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])["status"] == "accepted"


def test_accept_with_no_points_and_no_decision_section_is_refused(adr, kit):
    (decisions(kit) / "0003-jpa.md").write_text(LEGACY, encoding="utf-8")
    got = adr.start_review("0003")
    with pytest.raises(adr.AdrError) as exc:
        adr.accept("0003", by="Test", attendees=[], base_sha=got["sha"])
    assert str(exc.value) == "write the Decision section or add a decision point"
    assert (decisions(kit) / "0003-jpa.md").read_text(encoding="utf-8") == LEGACY


def test_accept_refuses_a_stale_read_and_changes_nothing(adr, kit):
    a = decided(adr, chosen="A", rationale="r")
    f = kit.root / "docs" / a["path"]
    f.write_text(f.read_text(encoding="utf-8") + "\nedited elsewhere\n", encoding="utf-8")
    before = f.read_bytes()
    with pytest.raises(adr.AdrConflict) as exc:
        adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert exc.value.sha == adr.get(a["id"])["sha"] != a["sha"]
    assert f.read_bytes() == before and adr.get(a["id"])["state"]["phase"] == "review"


@pytest.mark.parametrize("action", ["accept", "reject"])
def test_deciding_an_adr_with_no_file_says_to_write_it_first(adr, action):
    got = adr.new({"title": "A", "kind": "new"})
    call = (lambda: adr.accept(got["id"], by="Test", attendees=[], base_sha="x")) if action == "accept" else \
        (lambda: adr.reject(got["id"], why="no", by="Test", base_sha="x"))
    with pytest.raises(adr.AdrError) as exc:
        call()
    assert str(exc.value) == f"write the ADR first: camaron adr write {got['id']}"


@pytest.mark.parametrize("action", ["accept", "reject"])
def test_deciding_an_unknown_adr_is_a_key_error(adr, action):
    with pytest.raises(KeyError):
        adr.accept("0042", by="Test", attendees=[], base_sha="x") if action == "accept" else \
            adr.reject("0042", why="no", by="Test", base_sha="x")


def test_a_decided_adr_cannot_be_decided_again(adr, kit):
    a = decided(adr, chosen="A", rationale="r")
    out = adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    f = kit.root / "docs" / out["path"]
    before = f.read_bytes()
    with pytest.raises(adr.AdrError, match="already accepted"):
        adr.accept(a["id"], by="Other", attendees=[], base_sha=out["sha"])
    with pytest.raises(adr.AdrError, match="already accepted"):
        adr.reject(a["id"], why="changed my mind", by="Other", base_sha=out["sha"])
    assert f.read_bytes() == before


@pytest.mark.parametrize("by", ["", "  ", None])
def test_a_decision_needs_who_takes_it(adr, by):
    a = decided(adr, chosen="A", rationale="r")
    with pytest.raises(adr.AdrError, match="name"):
        adr.accept(a["id"], by=by, attendees=[], base_sha=a["sha"])
    with pytest.raises(adr.AdrError, match="name"):
        adr.reject(a["id"], why="no", by=by, base_sha=a["sha"])
    assert adr.get(a["id"])["state"]["phase"] == "review"


def test_the_attendees_of_the_review_are_kept_unless_the_caller_gives_others(adr, kit):
    a = decided(adr, chosen="A", rationale="r")
    adr.set_attendees(a["id"], ["LA", "MP"])
    out = adr.accept(a["id"], by="Test", attendees=None, base_sha=a["sha"])
    assert "LA, MP" in out["sections"]["decided_by"] and out["state"]["attendees"] == ["LA", "MP"]
    b = decided(adr, chosen="A", rationale="r")
    adr.set_attendees(b["id"], ["LA"])
    out = adr.accept(b["id"], by="Test", attendees=[" JD ", "JD", "", "AB"], base_sha=b["sha"])
    assert "Attendees: JD, AB" in out["sections"]["decided_by"] and out["state"]["attendees"] == ["JD", "AB"]


def test_attendees_must_be_a_list_of_text(adr):
    a = decided(adr, chosen="A", rationale="r")
    with pytest.raises(adr.AdrError, match="attendees"):
        adr.accept(a["id"], by="Test", attendees="LA", base_sha=a["sha"])
    assert adr.get(a["id"])["state"]["phase"] == "review"


def test_accept_can_be_retried_after_a_crash_before_the_state_was_saved(adr, kit, monkeypatch):
    a, save = decided(adr, chosen="A", rationale="r"), adr.save_state

    def crash(_state):
        raise RuntimeError("crash")
    monkeypatch.setattr(adr, "save_state", crash)
    with pytest.raises(RuntimeError):
        adr.accept(a["id"], by="Test", attendees=["LA"], base_sha=a["sha"])
    monkeypatch.setattr(adr, "save_state", save)
    half = adr.get(a["id"])
    assert half["status"] == "accepted" and half["state"]["phase"] == "review"
    out = adr.accept(a["id"], by="Test", attendees=["LA"], base_sha=half["sha"])
    assert out["state"]["phase"] == "accepted" and out["sections"]["decision"] == "**Where?** — Redis. r"
    fm, body = read(kit, out)
    assert kit.docs.trust_of(fm, kit.docs.body_sha(body)) == "confirmed" and body.count("## Decided by") == 1


def test_a_legacy_adr_without_frontmatter_is_accepted_in_a_session(adr, kit, monkeypatch):
    monkeypatch.setattr(adr, "today", lambda: "2026-10-27")
    f = decisions(kit) / "0003-jpa.md"
    f.write_text(LEGACY, encoding="utf-8")
    got = adr.start_review("0003")
    got = adr.part("0003", "decision", "edit", "We keep JPA.", base_sha=got["sha"])
    assert f.read_text(encoding="utf-8").startswith(LEGACY)
    out = adr.accept("0003", by="Test", attendees=["LA"], base_sha=got["sha"])
    fm, body = kit.docs.split_fm(f.read_text(encoding="utf-8"))
    assert fm["type"] == "decision" and fm["title"] == "0003 — JPA" and fm["x-owner"] == "human"
    assert kit.docs.trust_of(fm, kit.docs.body_sha(body)) == "confirmed"
    assert body.startswith("# 0003 — JPA\n\n## Estado\n\nAccepted (2026-10-27)\n\n## Contexto\n\nwhy\n\n## Notas\n\nkeep\n")
    assert out["chip"] == "accepted" and out["legacy"] is False and out["state"]["phase"] == "accepted"


def test_a_file_whose_frontmatter_cannot_be_read_is_not_rewritten(adr, kit):
    f = decisions(kit) / "0004-x.md"
    f.write_text("---\nfoo: [unclosed\n---\n# 0004 — X\n\n## Decision\n\nKeep.\n", encoding="utf-8")
    got = adr.start_review("0004")
    before = f.read_bytes()
    with pytest.raises(adr.AdrError, match="frontmatter"):
        adr.accept("0004", by="Test", attendees=[], base_sha=got["sha"])
    with pytest.raises(adr.AdrError, match="frontmatter"):
        adr.reject("0004", why="no", by="Test", base_sha=got["sha"])
    assert f.read_bytes() == before and adr.get("0004")["state"]["phase"] == "review"


@pytest.mark.parametrize("why", ["", "  \n ", None])
def test_a_rejection_needs_a_reason(adr, why):
    a = with_point(adr)
    with pytest.raises(adr.AdrError) as exc:
        adr.reject(a["id"], why=why, by="Test", base_sha=a["sha"])
    assert str(exc.value) == "a rejection needs a reason" and adr.get(a["id"])["state"]["phase"] == "review"


def test_reject_writes_the_reason_owns_and_confirms(adr, kit, monkeypatch):
    monkeypatch.setattr(adr, "today", lambda: "2026-10-27")
    a = with_point(adr)
    out = adr.reject(a["id"], why="too   costly\nfor now", by="Test", base_sha=a["sha"])
    fm, body = read(kit, out)
    assert out["sections"]["status"] == "Rejected (2026-10-27): too costly for now"
    assert fm["x-owner"] == "human" and fm["x-confirmed"]["by"] == "Test"
    assert kit.docs.trust_of(fm, kit.docs.body_sha(body)) == "confirmed"
    assert (out["status"], out["chip"], out["state"]["phase"], out["decided"]) == ("rejected", "rejected", "rejected", "2026-10-27")
    assert "#### P1" in out["sections"]["decision"]


COMMENTS = ["<!-- pick one -->", "<!-- pick one:\nproposed | accepted -->"]


@pytest.mark.parametrize("comment", COMMENTS)
def test_accepting_a_legacy_adr_replaces_the_status_it_reads_not_a_comment_above_it(adr, kit, comment, monkeypatch):
    monkeypatch.setattr(adr, "today", lambda: "2026-10-27")
    f = decisions(kit) / "0003-jpa.md"
    legacy = LEGACY.replace("Propuesto <!-- x -->", f"{comment}\nPropuesto")
    f.write_text(legacy, encoding="utf-8")
    got = adr.start_review("0003")
    got = adr.part("0003", "decision", "edit", "We keep JPA.", base_sha=got["sha"])
    out = adr.accept("0003", by="Test", attendees=[], base_sha=got["sha"])
    body = kit.docs.split_fm(f.read_text(encoding="utf-8"))[1]
    assert body.startswith(f"# 0003 — JPA\n\n## Estado\n\n{comment}\nAccepted (2026-10-27)\n\n## Contexto\n\nwhy\n")
    assert "Propuesto" not in body and out["status"] == "accepted" and adr.list_adrs()[0]["status"] == "accepted"


@pytest.mark.parametrize("comment", COMMENTS)
def test_superseding_replaces_the_status_an_old_adr_reads_not_a_comment_above_it(adr, kit, comment):
    old = decisions(kit) / "0001-ehcache.md"
    old.write_text(OLD.replace("Accepted", f"{comment}\nAccepted"), encoding="utf-8")
    accepted_adr(adr, [], supersedes="1")
    assert old.read_text(encoding="utf-8") == OLD.replace("Accepted", f"{comment}\nSuperseded by [0002](0002-t.md)")
    assert adr.get("0001")["chip"] == "superseded"


def test_superseding_marks_an_old_adr_even_without_frontmatter(adr, kit):
    old = kit.root / "docs" / "decisions" / "0001-ehcache.md"
    old.parent.mkdir(parents=True)
    old.write_text("# 0001 — EhCache\n\n## Status\n\nAccepted\n\n## Context\n\nx\n", encoding="utf-8")
    a = adr.write_without_ai(adr.new({"title": "Caffeine", "kind": "new", "supersedes": "0001"})["id"])
    a = adr.part(a["id"], "decision", "edit", "Caffeine.", base_sha=a["sha"])
    adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    text = old.read_text(encoding="utf-8")
    assert "Superseded by [0002](0002-caffeine.md)" in text and "## Context\n\nx\n" in text
    assert adr.get("0001")["chip"] == "superseded"


def test_superseding_changes_only_the_status_line_of_an_old_adr_with_no_frontmatter(adr, kit):
    old = decisions(kit) / "0001-ehcache.md"
    old.write_text(OLD, encoding="utf-8")
    accepted_adr(adr, [], supersedes="1")
    assert old.read_text(encoding="utf-8") == OLD.replace("Accepted", "Superseded by [0002](0002-t.md)")
    assert adr.get("0001")["state"] is None and adr.get("0001")["legacy"] is True


def test_superseding_confirms_an_old_adr_that_has_frontmatter_and_keeps_its_notes(adr, kit):
    old = decisions(kit) / "0001-ehcache.md"
    old.write_text("---\ntype: decision\ntitle: 0001 — EhCache\nx-owner: human\n---\n# 0001 — EhCache\n\n"
                   "## Status\n\nAccepted (2026-01-02)\n\nSee the thread.\n\n## Context\n\nx\n", encoding="utf-8")
    accepted_adr(adr, [], supersedes="1")
    fm, body = kit.docs.split_fm(old.read_text(encoding="utf-8"))
    assert body == ("# 0001 — EhCache\n\n## Status\n\nSuperseded by [0002](0002-t.md)\n\nSee the thread.\n\n"
                    "## Context\n\nx\n")
    assert (fm["type"], fm["title"], fm["x-owner"]) == ("decision", "0001 — EhCache", "human")
    assert fm["x-confirmed"]["by"] == "Test" and kit.docs.trust_of(fm, kit.docs.body_sha(body)) == "confirmed"


def test_superseding_an_adr_that_does_not_exist_changes_nothing(adr, kit):
    a = adr.write_without_ai(adr.new({"title": "Caffeine", "kind": "new", "supersedes": "9"})["id"])
    a = adr.part(a["id"], "decision", "edit", "Caffeine.", base_sha=a["sha"])
    f = kit.root / "docs" / a["path"]
    before = f.read_bytes()
    with pytest.raises(adr.AdrError, match="0009"):
        adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert f.read_bytes() == before and adr.get(a["id"])["state"]["phase"] == "review"


def test_an_adr_cannot_supersede_itself(adr, kit):
    a = adr.write_without_ai(adr.new({"title": "Caffeine", "kind": "new", "supersedes": "1"})["id"])
    a = adr.part(a["id"], "decision", "edit", "Caffeine.", base_sha=a["sha"])
    with pytest.raises(adr.AdrError, match="itself"):
        adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert adr.get(a["id"])["state"]["phase"] == "review"


def test_superseding_refuses_an_old_adr_that_is_not_utf8_before_writing_anything(adr, kit):
    old = decisions(kit) / "0001-old.md"
    old.write_bytes(OLD.encode("utf-8") + b"\xff\n")
    a = adr.write_without_ai(adr.new({"title": "Caffeine", "kind": "new", "supersedes": "1"})["id"])
    a = adr.part(a["id"], "decision", "edit", "Caffeine.", base_sha=a["sha"])
    new = kit.root / "docs" / a["path"]
    before = new.read_bytes()
    with pytest.raises(adr.AdrError, match="UTF-8"):
        adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert new.read_bytes() == before and old.read_bytes().endswith(b"\xff\n")


def test_superseding_a_file_that_links_outside_docs_decisions_is_refused(adr, kit, tmp_path):
    outside = tmp_path / "AGENTS.md"
    outside.write_text(OLD, encoding="utf-8")
    try:
        (decisions(kit) / "0001-ehcache.md").symlink_to(outside)
    except OSError:
        pytest.skip("this machine cannot make symbolic links")
    a = adr.write_without_ai(adr.new({"title": "Caffeine", "kind": "new", "supersedes": "1"})["id"])
    a = adr.part(a["id"], "decision", "edit", "Caffeine.", base_sha=a["sha"])
    new = kit.root / "docs" / a["path"]
    before = new.read_bytes()
    with pytest.raises(adr.AdrError, match="docs/decisions"):
        adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert outside.read_text(encoding="utf-8") == OLD and new.read_bytes() == before


def test_covering_finds_accepted_adrs_through_shared_sources(adr, kit):
    page = kit.root / "docs" / "orders.md"
    page.parent.mkdir(exist_ok=True)
    page.write_text("---\ntitle: Orders\nx-sources:\n  - api:src/S.java#L1-L9\n---\n# Orders\n", encoding="utf-8")
    a = decided(adr, chosen="A", rationale="r")
    assert adr.covering("orders.md") == []                                  # proposed ADRs cover nothing
    adr.accept(a["id"], by="Test", attendees=[], base_sha=a["sha"])
    assert [(c["id"], c["implementation"]) for c in adr.covering("orders.md")] == [(a["id"], "pending")]
    assert adr.covering(a["path"]) == []


def test_covering_rows_name_the_adr(adr, kit):
    page(kit, "orders.md", ["api:src/S.java"])
    out = accepted_adr(adr, ["api:src/S.java"])
    assert adr.covering("orders.md") == [{"id": out["id"], "title": "T", "path": out["path"], "kind": "new",
                                          "implementation": "pending"}]


@pytest.mark.parametrize("name, sources, touch, covers", [
    ("orders.md", ["api:src/S.java#L1-L9"], "api:src/S.java", True),
    ("orders.md", ["repo://api/src/S.java#x"], "api:src/S.java", True),
    ("orders.md", ["api:src/Other.java"], "api:src/S.java", False),
    ("orders.md", [], "api:src/S.java", False),
    ("orders.md", [], "cam-docs:docs/orders.md", True),
    ("flows/pay.md", [], "cam-docs:docs/flows/pay.md", True),
    ("flows/pay.md", [], "cam-docs:docs/pay.md", False)])
def test_covering_matches_references_not_fragments_or_prefixes(adr, kit, name, sources, touch, covers):
    page(kit, name, sources)
    out = accepted_adr(adr, [touch])
    assert [c["id"] for c in adr.covering(name)] == ([out["id"]] if covers else [])


def test_only_an_accepted_adr_covers_a_page(adr, kit):
    page(kit, "orders.md", ["api:src/S.java"])
    first = accepted_adr(adr, ["api:src/S.java"])
    refused = adr.write_without_ai(adr.new({"title": "No", "kind": "new", "touches": ["api:src/S.java"]})["id"])
    adr.reject(refused["id"], why="no", by="Test", base_sha=refused["sha"])
    assert [c["id"] for c in adr.covering("orders.md")] == [first["id"]]
    second = accepted_adr(adr, ["api:src/S.java"], supersedes=first["id"])
    assert [c["id"] for c in adr.covering("orders.md")] == [second["id"]]


def test_a_legacy_accepted_adr_covers_a_page_too(adr, kit):
    page(kit, "orders.md", ["api:src/S.java"])
    (decisions(kit) / "0003-jpa.md").write_text(
        "---\nx-sources:\n  - api:src/S.java\n---\n# 0003 — JPA\n\n## Estado\n\nAceptada\n", encoding="utf-8")
    (decisions(kit) / "0004-draft.md").write_text(
        "---\nx-sources:\n  - api:src/S.java\n---\n# 0004 — Draft\n\n## Estado\n\nPropuesta\n", encoding="utf-8")
    assert adr.covering("orders.md") == [{"id": "0003", "title": "JPA", "path": "decisions/0003-jpa.md", "kind": "retro",
                                          "implementation": "n/a"}]


def test_covering_an_unknown_page_is_empty(adr, kit):
    accepted_adr(adr, ["api:src/S.java"])
    assert adr.covering("nope.md") == [] and adr.covering("../x.md") == []


def test_a_decision_page_is_never_covered_but_a_normal_page_is(adr, kit):
    page(kit, "orders.md", ["api:src/S.java"])
    first = accepted_adr(adr, ["api:src/S.java"])
    second = accepted_adr(adr, ["api:src/S.java"])
    guide = kit.root / "docs" / "guides" / "why-redis.md"
    guide.parent.mkdir(parents=True, exist_ok=True)
    guide.write_text("---\ntype: decision\nx-sources:\n  - api:src/S.java\n---\n# Why Redis\n", encoding="utf-8")
    assert [c["id"] for c in adr.covering("orders.md")] == [first["id"], second["id"]]
    assert adr.covering(first["path"]) == [] and adr.covering(second["path"]) == []
    assert adr.covering("guides/why-redis.md") == []


def test_a_page_under_decisions_is_not_covered_even_without_type_decision(adr, kit):
    accepted_adr(adr, ["api:src/S.java"])
    (decisions(kit) / "0003-jpa.md").write_text(
        "---\nx-sources:\n  - api:src/S.java\n---\n# 0003 — JPA\n\n## Estado\n\nPropuesta\n", encoding="utf-8")
    assert adr.covering("decisions/0003-jpa.md") == []
