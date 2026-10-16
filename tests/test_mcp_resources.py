"""R26 part 2 (ai-first-docs P8 + MCP): `llms.txt` per llmstxt.org with interviews under `## Optional`, `llms-full.txt`
with every page agents may read, MCP resources (`camdocs://`), prompts, and `ask`: the best sections for a question,
each with its citation, assembled without a model. The freshness gate applies to all of them."""
from __future__ import annotations

import importlib

import pytest

FLOW = """---
title: Checkout
description: How an order goes from the cart to a paid invoice, and what happens when the payment fails.
---
# Checkout

> **TL;DR:** The cart calls the payments service; a failed payment leaves the order pending.

## Failure handling
Payments are retried once by the `PaymentRetryJob`.

## Data touched
The `orders` table.
"""


def write(kit, rel, text, confirm=True):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    if confirm:
        kit.docs.confirm([str(f)], by="ana")
    return f


@pytest.fixture
def mcp(kit):
    write(kit, "index.md", "---\ntitle: Home\ndescription: The demo shop, its services and how orders flow.\n---\n# Home\n")
    write(kit, "flows/checkout.md", FLOW)
    write(kit, "interview/repo-api.md", "---\ntitle: api interview\ntype: interview\n---\n# Notes\n\nRaw answers.\n")
    write(kit, "flows/draft.md", "---\ntitle: Draft\n---\n# Draft\n\nGuessing the retry policy.\n", confirm=False)
    return importlib.import_module("lib.mcp")


def test_llms_txt_follows_llmstxt_org(kit, mcp):
    kit.docs.llms()
    text = (kit.root / "docs" / "llms.txt").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "# demo" and lines[2].startswith("> The demo shop, its services and how orders flow.")
    head, _, optional = text.partition("## Optional")
    assert "interview/repo-api.md" not in head and "interview/repo-api.md" in optional
    assert "llms-full.txt" in head


def test_llms_full_has_every_readable_page_without_frontmatter(kit, mcp):
    kit.docs.llms()
    full = (kit.root / "docs" / "llms-full.txt").read_text(encoding="utf-8")
    assert "<!-- flows/checkout.md · confirmed · How an order goes" in full and "PaymentRetryJob" in full
    assert "\ntitle: Checkout" not in full and "Raw answers" not in full                  # no YAML, no interviews
    assert "Guessing the retry policy" not in full                                        # withheld: unreviewed


def test_llms_full_is_a_derived_file(kit):
    from lib.harness import integrate
    assert "docs/llms-full.txt" in integrate.DERIVED
    assert ":(exclude)docs/llms-full.txt" in (kit.kit_dir / "lib" / "env.py").read_text(encoding="utf-8")


def test_resources_list_the_readable_pages(kit, mcp):
    res = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "resources/list"})["result"]["resources"]
    uris = {r["uri"]: r for r in res}
    assert "camdocs://flows/checkout.md" in uris and "camdocs://llms.txt" in uris
    assert "camdocs://flows/draft.md" not in uris
    assert uris["camdocs://flows/checkout.md"]["mimeType"] == "text/markdown"
    assert uris["camdocs://flows/checkout.md"]["description"].startswith("How an order goes")


def test_resources_read_goes_through_the_gate(kit, mcp):
    read = lambda uri: mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "resources/read",  # noqa: E731
                                   "params": {"uri": uri}})["result"]["contents"][0]["text"]
    assert "PaymentRetryJob" in read("camdocs://flows/checkout.md")
    assert "Guessing" not in read("camdocs://flows/draft.md") and "awaits review" in read("camdocs://flows/draft.md")
    assert "flows/checkout.md" in read("camdocs://llms.txt")


def test_initialize_announces_resources_and_prompts(kit, mcp):
    caps = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})["result"]["capabilities"]
    assert {"tools", "resources", "prompts"} <= set(caps)


def test_prompts(kit, mcp):
    names = {p["name"] for p in mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "prompts/list"})["result"]["prompts"]}
    assert {"implement-feature", "update-docs"} <= names
    got = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "prompts/get",
                      "params": {"name": "implement-feature", "arguments": {"feature": "retry failed payments"}}})
    text = got["result"]["messages"][0]["content"]["text"]
    assert "retry failed payments" in text and "search_docs" in text and "confirmed" in text
    bad = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "prompts/get", "params": {"name": "nope"}})
    assert bad["error"]["code"] == -32602


def test_ask_returns_cited_sections_and_never_withheld_ones(kit, mcp):
    text = mcp.ask("how are failed payments retried?")
    assert "[flows/checkout.md#failure-handling]" in text and "PaymentRetryJob" in text
    assert "The `orders` table" not in text                                               # only the matching section
    assert "Guessing" not in text and "cite" in text.lower()


def test_ask_with_nothing_found(kit, mcp):
    assert "Nothing in the docs" in mcp.ask("quantum teleportation")
