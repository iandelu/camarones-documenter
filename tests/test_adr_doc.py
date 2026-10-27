"""The ADR document, pure (`lib/adr_doc.py`): numbering, slugs, the status of an ADR the kit did not write, sections read
and replaced in place (every other byte kept), and the one template a new ADR is rendered from."""
from __future__ import annotations

import importlib

import pytest

LEGACY = ("---\ntype: decision\ntitle:   0003 — JPA\ntags: [api,   db]\n# kept as typed\n---\n"
          "# 0003 — JPA\n\n## Estado\n\nPropuesto <!-- x -->\n\n## Contexto\n\nwhy\n\n## Notas\n\nkeep\n")


@pytest.fixture
def adr_doc(kit):
    return importlib.import_module("lib.adr_doc")


def test_slug_folds_accents_and_caps_length(adr_doc):
    assert adr_doc.slugify("Sesiones en Redis, ¿sí o no?") == "sesiones-en-redis-si-o-no"
    assert adr_doc.slugify("  ") == "decision"
    assert len(adr_doc.slugify("x" * 200)) == 60


def test_a_slug_cut_never_ends_on_a_dash(adr_doc):
    slug = adr_doc.slugify("a" * 59 + " tail")
    assert slug == "a" * 59


def test_next_number_skips_gaps_and_ignores_junk(adr_doc):
    assert adr_doc.next_number([]) == "0001"
    assert adr_doc.next_number(["0001", "0007", "0003"]) == "0008"
    assert adr_doc.next_number(["0002", "notes", "", "12x"]) == "0003"
    assert adr_doc.number_of("0012-sessions.md") == "0012" and adr_doc.number_of("notes.md") is None


def test_number_of_reads_a_path_and_wants_an_md_file(adr_doc):
    assert adr_doc.number_of("docs/decisions/0004-cache.md") == "0004"
    assert adr_doc.number_of("0004-cache.yaml") is None and adr_doc.number_of("0004.md") is None


@pytest.mark.parametrize("body, want", [
    ("## Status\n\nProposed <!-- agents only write \"Proposed\" -->\n", ("proposed", None)),
    ("## Estado\n\nAceptada (2026-10-21)\n", ("accepted", None)),
    ("Status: accepted\n\n## Context\n", ("accepted", None)),
    ("## Status\n\nSuperseded by [0010](0010-caffeine.md)\n", ("superseded", "0010")),
    ("## Estado\n\nSustituida por 0010\n", ("superseded", "0010")),
    ("## Context\n\nno status here\n", ("unknown", None)),
    ("## Status\n\nRejected (2026-10-22): too costly\n", ("rejected", None)),
    ("## Estado\n\nRechazado\n", ("rejected", None)),
    ("## Status\n\nDeprecated\n", ("deprecated", None)),
    ("## Estado\n\nObsoleta\n", ("deprecated", None)),
    ("**Status:** Accepted\n\n## Context\n", ("accepted", None)),
    ("# 0001 — X\n\nEstado: propuesta\n\n## Contexto\n", ("proposed", None)),
    ("## Status\n\nStatus: Accepted\n", ("accepted", None)),
    ("## Status\n\n<!-- a note -->\n\n**ACCEPTED**\n", ("accepted", None)),
    ("## Status\n\nSuperseded\n", ("superseded", None)),
    ("## Status\n\nPending review\n", ("unknown", None)),
    ("## Status\n\n## Context\n\nStatus: accepted\n", ("accepted", None)),
    ("", ("unknown", None)),
])
def test_status_is_read_in_both_languages(adr_doc, body, want):
    assert adr_doc.status_of(body) == want


def test_a_status_inside_a_comment_is_not_a_status(adr_doc):
    assert adr_doc.status_of("<!-- Status: accepted -->\n\n## Context\n\nx\n") == ("unknown", None)


def test_section_reads_both_languages_and_stops_at_the_next_heading(adr_doc):
    body = ("# 0001 — X\n\n## Contexto\n\nwhy\n\n### Detail\n\nmore\n\n## Decision drivers\n\n- fast\n\n"
            "## Decisión\n\nWe keep it.\n")
    assert adr_doc.section(body, "context") == "why\n\n### Detail\n\nmore"
    assert adr_doc.section(body, "drivers") == "- fast"
    assert adr_doc.section(body, "decision") == "We keep it."
    assert adr_doc.section(body, "consequences") is None


def test_section_ignores_headings_inside_code(adr_doc):
    body = "## Context\n\n```md\n## Decision\n```\n\n## Decision\n\nreal\n"
    assert adr_doc.section(body, "decision") == "real"
    assert adr_doc.section(body, "context") == "```md\n## Decision\n```"


def test_section_is_empty_text_when_the_heading_has_no_body(adr_doc):
    assert adr_doc.section("## Status\n\n## Context\n\nx\n", "status") == ""


def test_the_keys_are_ordered_and_have_an_english_heading(adr_doc):
    assert adr_doc.KEYS == ("status", "context", "drivers", "options", "decision", "consequences", "confirmation",
                            "diagram", "evidence", "decided_by")
    assert adr_doc.ORDER == adr_doc.KEYS
    assert adr_doc.HEADINGS == {"status": "Status", "context": "Context", "drivers": "Decision drivers",
                                "options": "Considered options", "decision": "Decision",
                                "consequences": "Consequences", "confirmation": "Confirmation", "diagram": "Diagram",
                                "evidence": "Evidence", "decided_by": "Decided by"}


def test_replace_section_keeps_every_other_byte(adr_doc):
    text = "---\ntitle: X\n---\n# 0001 — X\n\n## Status\n\nProposed\n\n## Contexto\n\nold\n\n## Notes\n\nmine\n"
    out = adr_doc.replace_section(text, "context", "new text")
    assert out == text.replace("old", "new text")
    added = adr_doc.replace_section(text, "decided_by", "2026-10-27 · LA")
    assert added.startswith(text.rstrip("\n")) and added.endswith("## Decided by\n\n2026-10-27 · LA\n")


def test_replace_section_leaves_a_legacy_file_untouched_outside_the_section(adr_doc):
    out = adr_doc.replace_section(LEGACY, "status", "Accepted (2026-10-27)")
    assert out == LEGACY.replace("Propuesto <!-- x -->", "Accepted (2026-10-27)")
    assert out.startswith("---\ntype: decision\ntitle:   0003 — JPA\ntags: [api,   db]\n# kept as typed\n---\n")
    assert adr_doc.status_of(out.split("---\n", 2)[2]) == ("accepted", None)


def test_replace_section_works_on_a_file_with_no_frontmatter(adr_doc):
    text = "# 0002 — Y\n\n## Estado\n\nPropuesta\n"
    assert adr_doc.replace_section(text, "status", "Rejected (2026-10-27): no budget") == (
        "# 0002 — Y\n\n## Estado\n\nRejected (2026-10-27): no budget\n")


def test_replace_section_keeps_a_missing_final_newline_and_replaces_a_whole_section(adr_doc):
    text = "# T\n\n## Context\n\nline one\nline two\n\n## Evidence\n\nlast"
    out = adr_doc.replace_section(text, "evidence", "a\nb")
    assert out == "# T\n\n## Context\n\nline one\nline two\n\n## Evidence\n\na\nb"
    assert adr_doc.replace_section(text, "context", "one") == "# T\n\n## Context\n\none\n\n## Evidence\n\nlast"


def test_replace_section_fills_an_empty_section(adr_doc):
    assert adr_doc.replace_section("# T\n\n## Status\n\n## Context\n\nx\n", "status", "Proposed") == (
        "# T\n\n## Status\n\nProposed\n\n## Context\n\nx\n")
    assert adr_doc.replace_section("# T\n\n## Status\n", "status", "Proposed") == "# T\n\n## Status\n\nProposed\n"


def test_replace_section_keeps_subsections_it_does_not_replace(adr_doc):
    text = "# T\n\n## Decision\n\nchosen\n\n### Decision points\n\n#### P1 · Q\n\n## Evidence\n\nx\n"
    out = adr_doc.replace_section(text, "decision", "chosen\n\n### Decision points\n\n#### P1 · Q2")
    assert out == text.replace("Q\n", "Q2\n")


def test_a_missing_section_goes_before_the_first_later_one(adr_doc):
    text = "# T\n\n## Status\n\nProposed\n\n## Consequences\n\nc\n\n## Notes\n\nmine\n"
    out = adr_doc.replace_section(text, "decision", "We keep it.")
    assert out == "# T\n\n## Status\n\nProposed\n\n## Decision\n\nWe keep it.\n\n## Consequences\n\nc\n\n## Notes\n\nmine\n"
    assert adr_doc.section(out, "decision") == "We keep it."


def test_a_missing_section_is_added_at_the_end_when_none_should_follow_it(adr_doc):
    text = "# T\n\n## Context\n\nc\n\n## Notes\n\nmine\n"
    out = adr_doc.replace_section(text, "evidence", "e")
    assert out == "# T\n\n## Context\n\nc\n\n## Notes\n\nmine\n\n## Evidence\n\ne\n"


def test_a_file_out_of_order_gets_the_section_before_the_first_one_that_should_follow(adr_doc):
    text = "# T\n\n## Evidence\n\ne\n\n## Context\n\nc\n"
    out = adr_doc.replace_section(text, "drivers", "- fast")
    assert out == "# T\n\n## Decision drivers\n\n- fast\n\n## Evidence\n\ne\n\n## Context\n\nc\n"


def test_a_missing_section_is_added_after_a_file_with_no_final_newline_or_no_sections(adr_doc):
    assert adr_doc.replace_section("# T\n\n## Status\n\nProposed", "context", "why") == (
        "# T\n\n## Status\n\nProposed\n\n## Context\n\nwhy\n")
    assert adr_doc.replace_section("---\ntitle: X\n---\n", "context", "why") == (
        "---\ntitle: X\n---\n## Context\n\nwhy\n")


def test_a_section_is_inserted_with_a_blank_line_before_the_next_heading(adr_doc):
    out = adr_doc.replace_section("# T\ntext\n## Evidence\n\ne\n", "context", "why")
    assert out == "# T\ntext\n\n## Context\n\nwhy\n\n## Evidence\n\ne\n"


def test_an_unknown_key_is_an_error(adr_doc):
    with pytest.raises(KeyError):
        adr_doc.replace_section("# T\n", "notes", "x")
    with pytest.raises(KeyError):
        adr_doc.section("# T\n", "notes")


def test_evidence_table_escapes_cells(adr_doc):
    assert adr_doc.evidence_table([("a | b", "`x:y`\nz")]) == "| Claim | Evidence |\n|---|---|\n| a \\| b | `x:y` z |"
    assert adr_doc.evidence_table([]) == "| Claim | Evidence |\n|---|---|"


POINTS = [
    {"id": "p1", "question": "Where do sessions live?", "chosen": "A", "rationale": "already used by notifications",
     "options": [{"id": "A", "name": "Redis", "pros": ["already in use", "fast"], "cons": ["one more service"]},
                 {"id": "B", "name": "Postgres", "pros": [], "cons": ["a write per request"]}]},
    {"id": "p2", "question": "Who invalidates?", "other": "The gateway, on logout", "rationale": "",
     "options": [{"id": "A", "name": "Each service"}, {"id": "B", "name": "A job"}]},
    {"id": "p3", "question": "How do we migrate?", "deferred": True,
     "options": [{"id": "A", "name": "Big bang"}, {"id": "B", "name": "Gradual"}]},
]


def test_points_render_one_line_per_option_with_pros_and_cons(adr_doc):
    out = adr_doc.render_points(POINTS[:1])
    assert out == ("#### P1 · Where do sessions live?\n\n"
                   "- **A · Redis** — + already in use; + fast; − one more service\n"
                   "- **B · Postgres** — − a write per request")
    assert adr_doc.POINTS_HEADING == "### Decision points"


def test_points_without_pros_or_cons_are_just_the_option(adr_doc):
    out = adr_doc.render_points(POINTS[1:2])
    assert out == "#### P2 · Who invalidates?\n\n- **A · Each service**\n- **B · A job**"
    assert adr_doc.render_points([]) == ""


def test_points_are_separated_by_a_blank_line(adr_doc):
    out = adr_doc.render_points(POINTS)
    assert out.count("#### P") == 3 and "\n\n#### P2 · Who invalidates?" in out and "\n\n#### P3 ·" in out


def test_the_decision_names_what_each_point_chose(adr_doc):
    assert adr_doc.render_decision(POINTS[:1]) == "**Where do sessions live?** — Redis. already used by notifications"
    assert adr_doc.render_decision(POINTS[1:2]) == "**Who invalidates?** — The gateway, on logout."


def test_the_decision_skips_points_nobody_decided(adr_doc):
    out = adr_doc.render_decision(POINTS)
    assert out == ("**Where do sessions live?** — Redis. already used by notifications\n\n"
                   "**Who invalidates?** — The gateway, on logout.")
    assert adr_doc.render_decision([]) == ""


def test_decided_by_lists_date_attendees_mode_and_who_led(adr_doc):
    assert adr_doc.render_decided_by("2026-10-27", ["LA", " MP ", ""], "Luis", "manual") == (
        "- Date: 2026-10-27\n- Attendees: LA, MP\n- Mode: manual\n- Led by: Luis")
    assert adr_doc.render_decided_by("2026-10-27", [], "", "manual") == "- Date: 2026-10-27\n- Mode: manual"


def test_a_new_adr_renders_the_template(adr_doc, kit):
    fields = {"title": "Sessions in Redis", "kind": "new", "problem": "Pods lose sessions.", "drivers": ["No downtime"],
              "options_hint": ["Redis", "Postgres"], "touches": ["api:src/S.java", "cam-docs:docs/orders.md"]}
    text = adr_doc.render_new(fields, "0012", "2026-10-27")
    fm, body = kit.docs.split_fm(text)
    assert fm["type"] == "decision" and fm["x-owner"] == "ai" and fm["title"] == "0012 — Sessions in Redis"
    assert fm["x-sources"] == ["api:src/S.java", "docs/orders.md"]
    assert adr_doc.status_of(body) == ("proposed", None)
    assert adr_doc.section(body, "context") == "Pods lose sessions."
    assert "- No downtime" in adr_doc.section(body, "drivers")
    assert "### A · Redis" in adr_doc.section(body, "options") and "### B · Postgres" in adr_doc.section(body, "options")
    assert adr_doc.section(body, "decision") == adr_doc.PLACEHOLDER
    assert "| Named when the decision was framed | `api:src/S.java` |" in adr_doc.section(body, "evidence")
    assert "description" in fm and 40 <= len(fm["description"]) <= 300


def test_a_new_adr_tags_the_repos_it_touches_once_each(adr_doc, kit):
    fields = {"title": "T", "touches": ["web:a.ts", "api:b.java", "api:c.java", "cam-docs:docs/x.md", "api:b.java"]}
    fm, _ = kit.docs.split_fm(adr_doc.render_new(fields, "0001", "2026-10-27"))
    assert fm["tags"] == ["api", "web"]
    assert fm["x-sources"] == ["web:a.ts", "api:b.java", "api:c.java", "docs/x.md"]


def test_a_new_adr_with_only_a_title_asks_instead_of_inventing(adr_doc, kit):
    text = adr_doc.render_new({"title": "Caching"}, "0001", "2026-10-27")
    fm, body = kit.docs.split_fm(text)
    assert fm["tags"] == [] and fm["x-sources"] == []
    assert adr_doc.section(body, "context").startswith("TODO(question):")
    assert adr_doc.section(body, "options") == "TODO(question): which options were considered?"
    assert adr_doc.section(body, "consequences").startswith("TODO(question):")
    assert adr_doc.section(body, "drivers") is None
    assert adr_doc.section(body, "evidence") == "| Claim | Evidence |\n|---|---|"


def test_a_new_adr_keeps_the_constraints_the_person_gave(adr_doc, kit):
    fields = {"title": "T", "problem": "Pods lose sessions.", "constraints": ["No new infrastructure", "EU only"]}
    _, body = kit.docs.split_fm(adr_doc.render_new(fields, "0001", "2026-10-27"))
    assert adr_doc.section(body, "context") == "Pods lose sessions.\n\n**Constraints**\n\n- No new infrastructure\n- EU only"


def test_a_long_title_is_kept_in_the_title_and_cut_in_the_description(adr_doc, kit):
    title = "Move every session to a managed cache " * 12
    fm, body = kit.docs.split_fm(adr_doc.render_new({"title": title}, "0001", "2026-10-27"))
    assert fm["title"] == "0001 — " + title.strip() and len(fm["description"]) == 300
    assert body.startswith("# 0001 — Move every")


def test_a_title_on_two_lines_stays_on_one(adr_doc, kit):
    fm, body = kit.docs.split_fm(adr_doc.render_new({"title": "Two\nlines "}, "0001", "2026-10-27"))
    assert fm["title"] == "0001 — Two lines" and body.startswith("# 0001 — Two lines\n")


def test_a_new_adr_passes_the_kit_structure_check(adr_doc, kit):
    fields = {"title": "Sessions in Redis", "problem": "Pods lose sessions.", "drivers": ["No downtime"],
              "options_hint": ["Redis", "Postgres"], "touches": ["api:src/S.java"]}
    text = adr_doc.render_new(fields, "0012", "2026-10-27")
    assert kit.quality.structure_issues("decisions/0012-sessions-in-redis.md", text, kit.quality.skeletons()) == []


def test_a_new_adr_is_written_with_unix_line_endings_and_ends_with_one_newline(adr_doc):
    text = adr_doc.render_new({"title": "T", "options_hint": ["A", "B"]}, "0001", "2026-10-27")
    assert "\r" not in text and text.endswith("\n") and not text.endswith("\n\n")


def test_what_render_new_writes_is_read_back_by_the_section_helpers(adr_doc, kit):
    text = adr_doc.render_new({"title": "T", "problem": "P"}, "0001", "2026-10-27")
    _, body = kit.docs.split_fm(text)
    decided = adr_doc.replace_section(text, "decision", adr_doc.render_decision(POINTS[:1]))
    decided = adr_doc.replace_section(decided, "status", "Accepted (2026-10-27)")
    decided = adr_doc.replace_section(decided, "decided_by", adr_doc.render_decided_by("2026-10-27", ["LA"], "LA", "manual"))
    _, after = kit.docs.split_fm(decided)
    assert adr_doc.status_of(after) == ("accepted", None)
    assert adr_doc.section(after, "decision") == "**Where do sessions live?** — Redis. already used by notifications"
    assert adr_doc.section(after, "context") == adr_doc.section(body, "context")
    assert adr_doc.section(after, "decided_by").startswith("- Date: 2026-10-27")
