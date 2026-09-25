"""CLI check quality gate: links, glossary terms, and optional tools (mermaid-cli, gitleaks) degrading to one WARN."""
from __future__ import annotations

import pytest

FM = "---\ntitle: {t}\ndescription: d\ntype: guide\n---\n"


def page(kit, rel, body, title="T"):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(FM.format(t=title) + body, encoding="utf-8")
    return f


@pytest.fixture
def no_tools(kit, monkeypatch):
    monkeypatch.setattr(kit.quality, "which", lambda name: None)
    monkeypatch.setattr(kit.quality.binaries, "bin_path", lambda name: None)


def test_broken_internal_links_are_errors(kit):
    page(kit, "guides/a.md", "See [b](b.md), [c](../c.md#top), [web](https://x.io/y.md) and [anchor](#x).\n"
                             "```\n[in code](nowhere.md)\n```\nInline `[code](nope.md)` is not a link.\n")
    page(kit, "c.md", "# C\n")
    errors, warns = kit.quality.check_links(kit.docs.collect())
    assert errors == ["docs/guides/a.md:6: broken link → b.md"] and warns == []


def test_links_resolve_like_the_portal(kit):
    r = kit.quality.resolve
    assert r("guides/a.md", "../c.md") == "c.md"
    assert r("guides/a.md", "./sub/d.md") == "guides/sub/d.md"
    assert r("a.md", "../../x.md") == "x.md"


def test_glossary_terms_warn_and_fail_only_when_strict(kit):
    page(kit, "domain/glossary.md", "| Term | Meaning | Avoid |\n|---|---|---|\n| Pet Owner | person | Client, Customer |\n",
         title="Glossary")
    page(kit, "flows/visit.md", "A Client books a visit.\nThe Pet Owner pays.\n`Client` in code is fine.\n")
    rows = kit.docs.collect()
    errors, warns = kit.quality.check_terms(rows)
    assert errors == [] and warns == ['docs/flows/visit.md:6: "Client" → use "Pet Owner" (glossary)']
    errors, _ = kit.quality.check_terms(rows, strict=True)
    assert len(errors) == 1


def test_missing_mermaid_cli_is_one_warning(kit, no_tools):
    page(kit, "arch.md", "```mermaid\ngraph TD; A-->B\n```\n")
    errors, warns = kit.quality.check_mermaid(kit.docs.collect())
    assert errors == [] and len(warns) == 1 and "mmdc" in warns[0]


def test_missing_gitleaks_skips_the_secret_scan(kit, no_tools):
    page(kit, "a.md", "token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n")
    errors, warns = kit.quality.check_secrets()
    assert errors == [] and "gitleaks not installed" in warns[0]
    kit.quality.assert_no_secrets()                                       # warns on stderr, never raises


def test_check_aggregates_all_gates(kit, no_tools):
    (kit.root / "docs").mkdir(parents=True)
    (kit.root / "docs" / "bare.md").write_text("# no frontmatter\n[x](missing.md)\n", encoding="utf-8")
    errors, warns = kit.docs.check()
    assert "docs/bare.md: missing frontmatter" in errors
    assert any("broken link" in e for e in errors)
    assert any("gitleaks" in w for w in warns)
