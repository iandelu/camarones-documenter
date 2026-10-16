"""Section-level retrieval (R26a, ai-first-docs P6–P7): headings get the portal's slugs, `read_doc(path, section)`
returns the TL;DR plus one section, search hits name the section they matched and the page's trust and freshness, and
`check` validates `#anchors` the way the portal resolves them."""
from __future__ import annotations

import importlib

import pytest

PAGE = """---
title: Checkout
description: How an order goes from the cart to a paid invoice, and what happens when the payment fails.
---
# Checkout

> **TL;DR:** The cart calls the payments service; a failed payment leaves the order pending.

## Summary
The flow in one paragraph.

## Failure handling
Payments are retried once by the `PaymentRetryJob`.

### Idempotency
The `Idempotency-Key` header guards double charges.

## Data touched
The `orders` table.

## Data touched
A second section with the same title.
"""


@pytest.fixture
def mcp(kit):
    f = kit.root / "docs" / "flows" / "checkout.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(PAGE, encoding="utf-8")
    kit.docs.confirm([str(f)], by="ana")
    return importlib.import_module("lib.mcp")


@pytest.mark.parametrize("heading, slug", [
    ("Failure handling", "failure-handling"),
    ("Pago y facturación (v2)", "pago-y-facturación-v2"),
    ("`POST /orders` — create", "post-orders-create"),   # runs of spaces collapse, as in the portal
    ("Año ñandú", "año-ñandú"),
    ("[Glossary](glossary.md) terms", "glossary-terms"),
])
def test_slugs_match_the_portal(kit, heading, slug):
    assert kit.docs.slug(heading) == slug


def test_repeated_headings_get_numbered_slugs_like_the_portal(kit):
    body = kit.docs.split_fm(PAGE)[1]
    assert [s["slug"] for s in kit.docs.sections(body)] == ["summary", "failure-handling", "data-touched", "data-touched-1"]


def test_read_doc_with_a_section_returns_the_tldr_and_that_section_only(kit, mcp):
    text = mcp.read_doc("flows/checkout.md", section="failure-handling")
    assert "TL;DR" in text and "PaymentRetryJob" in text and "Idempotency-Key" in text      # its subsections come along
    assert "The flow in one paragraph" not in text and "`orders` table" not in text
    assert mcp.read_doc("flows/checkout.md", section="Failure handling") == text           # the title works too


def test_an_unknown_section_lists_the_ones_there_are(kit, mcp):
    text = mcp.read_doc("flows/checkout.md", section="nope")
    assert "No section" in text and "failure-handling" in text and "data-touched-1" in text


def test_a_whole_page_read_starts_with_its_outline(kit, mcp):
    head = mcp.read_doc("flows/checkout.md").splitlines()[0]
    assert "sections: summary, failure-handling, data-touched, data-touched-1" in head


def test_search_hits_name_the_section_trust_and_freshness(kit, mcp):
    hit = kit.docs.search("PaymentRetryJob")[0]
    assert hit["section"] == "failure-handling"
    text = mcp.search_docs("PaymentRetryJob")
    assert "flows/checkout.md#failure-handling" in text and "confirmed" in text
    assert 'read_doc("flows/checkout.md", section="failure-handling")' in text


def test_description_and_answers_rank_like_the_title(kit, mcp):
    other = kit.root / "docs" / "flows" / "refunds.md"
    other.write_text("---\ntitle: Refunds\nx-answers:\n  - How is a chargeback handled?\n---\n# Refunds\n\nMoney back.\n"
                     "\nfiller " * 30, encoding="utf-8")
    assert kit.docs.search("chargeback")[0]["path"] == "flows/refunds.md"


def test_check_flags_anchors_that_do_not_exist(kit, mcp):
    g = kit.root / "docs" / "guides" / "links.md"
    g.parent.mkdir(parents=True, exist_ok=True)
    g.write_text("---\ntitle: Links\n---\n# Links\n\n## Here\n\n[ok](../flows/checkout.md#failure-handling) "
                 "[dup](../flows/checkout.md#data-touched-1) [self](#here) [bad](../flows/checkout.md#retries) "
                 "[badself](#nowhere)\n", encoding="utf-8")
    errors, warns = kit.quality.check_links(kit.docs.collect())
    flagged = [w for w in warns if "links.md" in w]
    assert errors == [] and len(flagged) == 2
    assert any("#retries" in w for w in flagged) and any("#nowhere" in w for w in flagged)
    errors, _ = kit.quality.check_links(kit.docs.collect(), strict=True)
    assert len([e for e in errors if "links.md" in e]) == 2


def test_the_tool_schema_offers_the_section(kit, mcp):
    schema = next(t for t in mcp.TOOLS if t["name"] == "read_doc")["inputSchema"]
    assert "section" in schema["properties"] and schema["required"] == ["path"]


def test_html_comments_neither_rank_nor_show_in_snippets(kit, mcp):
    f = kit.root / "docs" / "flows" / "other.md"
    f.write_text("---\ntitle: Other\n---\n# Other\n\n<!-- generated:endpoints repo=api sha=1 -->\nNothing.\n"
                 "<!-- /generated:endpoints -->\n", encoding="utf-8")
    assert not any(h["path"] == "flows/other.md" for h in kit.docs.search("generated endpoints"))


def test_a_confirmed_page_with_comments_keeps_its_trust_in_hits(kit, mcp):
    f = kit.root / "docs" / "flows" / "noted.md"
    f.write_text("---\ntitle: Noted\n---\n# Noted\n\n<!-- a note -->\nThe ledger closes nightly.\n", encoding="utf-8")
    kit.docs.confirm([str(f)], by="ana")
    assert kit.docs.search("ledger")[0]["trust"] == "confirmed"
