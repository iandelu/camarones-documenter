"""R35: exporters. Built in: a print-ready single HTML (PDF when a headless Chrome is around) and a guided tour from a
business flow. Confluence and Notion ship as kit plugins that send the docs outside, so they stay off until approved
on this machine (trust), and they need their own URL and token."""
from __future__ import annotations

import io, json

import pytest

FLOW = """---
type: business-flow
title: Checkout
description: How an order goes from the cart to a paid invoice, and what happens when the payment fails.
x-sources:
  - api:README.md
---
# Checkout

> **TL;DR:** The cart calls the payments service; a failed payment leaves the order pending.

## Summary
An **owner** pays for the cart.

## Sequence
```mermaid
sequenceDiagram
  Web->>Api: POST /orders
```

## Steps

| Step | Repo | Entrypoint | Evidence |
|---|---|---|---|
| Pick the items | `web` | `CartPage` | `src/cart.tsx` |
| Place the order | `api` | `POST /orders` | `OrderController.java#L10-L30` |
| Charge the card | `api` | `PaymentService.charge` | `PaymentService.java` |

## Failure handling
Retries once.
"""


@pytest.fixture
def ex(kit):
    import importlib
    f = kit.root / "docs" / "flows" / "checkout.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(FLOW, encoding="utf-8")
    kit.docs.confirm([str(f)], by="ana")
    return importlib.import_module("lib.exporters")


def test_markdown_to_html_covers_what_pages_use(ex):
    html = ex.to_html("# T\n\nA **b** and `c` [link](x.md).\n\n- one\n- two\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
                      "```java\nint x = 1 < 2;\n```\n\n> **TL;DR:** quick.\n")
    assert "<h1" in html and "<strong>b</strong>" in html and "<code>c</code>" in html and '<a href="x.md">' in html
    assert "<ul>" in html and "<table>" in html and "<td>2</td>" in html
    assert "int x = 1 &lt; 2;" in html and "<blockquote>" in html


def test_the_tour_follows_the_flows_steps(kit, ex):
    tour = ex.tour("flows/checkout.md")
    assert [s["title"] for s in tour["steps"]] == ["Pick the items", "Place the order", "Charge the card"]
    assert tour["steps"][1]["repo"] == "api" and tour["steps"][1]["entrypoint"] == "POST /orders"
    out = ex.export_tour("flows/checkout.md")
    html = out.read_text(encoding="utf-8")
    assert out.name == "tour-checkout.html" and "Place the order" in html and "TL;DR" not in html.split("<body")[0]


def test_print_export_has_every_readable_page_once(kit, ex):
    out = ex.export_print()
    html = out.read_text(encoding="utf-8")
    assert html.count("<article") >= 1 and "Checkout" in html and "@media print" in html


def test_pdf_uses_a_headless_chrome_when_there_is_one(kit, ex, monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        out = [a for a in cmd if a.startswith("--print-to-pdf=")][0].split("=", 1)[1]
        open(out, "wb").write(b"%PDF-1.7")
        import subprocess
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(ex, "_chrome", lambda: "/usr/bin/chromium")
    monkeypatch.setattr(ex, "run", fake_run)
    pdf = ex.export_pdf()
    assert pdf.suffix == ".pdf" and pdf.read_bytes().startswith(b"%PDF") and "--headless" in " ".join(seen["cmd"])
    monkeypatch.setattr(ex, "_chrome", lambda: None)
    assert ex.export_pdf().suffix == ".html"                                   # no browser: the print-ready HTML


# ---------- third-party exporters: off until approved, never without their own config ----------
def test_confluence_and_notion_need_approval(wired, ex):
    import importlib
    trust = importlib.import_module("lib.trust")
    plugins = importlib.import_module("lib.harness.plugins")
    for name in ("confluence", "notion"):
        p = next(x for x in plugins.discover() if x.name == name)
        assert p.source == "kit" and p.sends_data and not p.active
    assert not {"plugin confluence", "plugin notion"} & {it.id for it, _ in trust.pending()}      # no nagging
    with pytest.raises(ex.ExportError, match="plugins enable confluence"):
        ex.export_to("confluence", env={})
    plugins.enable("confluence")
    assert next(x for x in plugins.discover() if x.name == "confluence").active
    plugins.disable("confluence")
    assert not next(x for x in plugins.discover() if x.name == "confluence").active
    plugins.enable("confluence")
    with pytest.raises(ex.ExportError, match="CONFLUENCE_URL"):
        ex.export_to("confluence", env={})


class Api:
    def __init__(self):
        self.calls = []

    def __call__(self, req, timeout=None):
        self.calls.append((req.get_method(), req.full_url, json.loads(req.data) if req.data else None,
                           dict(req.header_items())))
        if req.get_method() == "GET":
            return io.BytesIO(json.dumps({"results": []}).encode())
        return io.BytesIO(json.dumps({"id": "1"}).encode())


def test_confluence_publishes_readable_pages_as_storage_html(wired, ex):
    import importlib
    importlib.import_module("lib.harness.plugins").enable("confluence")
    api = Api()
    env = {"CONFLUENCE_URL": "https://acme.atlassian.net/wiki", "CONFLUENCE_TOKEN": "t", "CONFLUENCE_USER": "a@acme",
           "CONFLUENCE_SPACE": "DOCS"}
    n = ex.export_to("confluence", env=env, opener=api)
    posts = [c for c in api.calls if c[0] == "POST"]
    assert n == len(posts) >= 1
    body = next(p for p in posts if p[2]["title"] == "Checkout")[2]
    assert body["space"] == {"key": "DOCS"} and "<h2" in body["body"]["storage"]["value"]
    assert posts[0][3]["Authorization"].startswith("Basic ")


def test_notion_publishes_blocks(wired, ex):
    import importlib
    importlib.import_module("lib.harness.plugins").enable("notion")
    api = Api()
    n = ex.export_to("notion", env={"NOTION_TOKEN": "t", "NOTION_PARENT_PAGE": "abc"}, opener=api)
    posts = [c for c in api.calls if c[0] == "POST"]
    assert n == len(posts) >= 1
    page = next(p for p in posts if "Checkout" in json.dumps(p[2]))[2]
    assert page["parent"] == {"page_id": "abc"} and any(b["type"] == "heading_2" for b in page["children"])


def test_the_export_commands(wired, ex):
    import os, subprocess, sys
    env = {**os.environ, "CAMARONES_ROOT": str(wired.root)}
    cli = lambda *a: subprocess.run([sys.executable, str(wired.kit_dir / "camarones.py"), *a], env=env,  # noqa: E731
                                    capture_output=True, text=True, encoding="utf-8")
    r = cli("export", "tour", "flows/checkout.md")
    assert r.returncode == 0 and "tour-checkout.html" in r.stdout
    assert cli("export", "confluence").returncode == 2
    assert cli("plugins", "enable", "confluence").returncode == 0
    r = cli("export", "confluence")
    assert r.returncode == 2 and "CONFLUENCE_URL" in r.stderr
