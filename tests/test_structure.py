"""Pages written for agents first (R24, ai-first-docs P1–P5): the answer under the H1, sections that stand alone, the
skeleton's sections, word budgets. A WARN by default, an ERROR with --strict; interviews, guides, wikis and pages a
person owns keep their own shape."""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import KIT_DIR

SKELETONS = sorted(p for p in (KIT_DIR / "templates" / "skeletons").glob("*.md") if p.name != "README.md")

GOOD = """---
type: business-flow
title: Checkout
description: How an order goes from the cart to a paid invoice, and what happens when the payment fails.
x-sources:
  - api:README.md
---
# Checkout

> **TL;DR:** The cart calls the payments service; a failed payment leaves the order pending.

## Summary
The flow in one paragraph.

## Sequence
```mermaid
sequenceDiagram
  A->>B: pay
```

## Steps
1. Pay.

## Failure handling
Retries once.

## Data touched
The orders table.
"""


def write(kit, rel, text):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return f


def issues(kit, rel, text):
    write(kit, rel, text)
    errors, warns = kit.quality.check_structure(kit.docs.collect())
    assert errors == []
    return [w.split(": ", 1)[1] for w in warns if w.startswith(f"docs/{rel}:")]


@pytest.mark.parametrize("skeleton", SKELETONS, ids=lambda p: p.stem)
def test_every_skeleton_passes_its_own_check(kit, skeleton):
    fm, _ = kit.docs.split_fm(skeleton.read_text(encoding="utf-8"))
    rel = (fm.get("x-skeleton-for") or f"x/{skeleton.stem}.md").replace("*", "api")
    assert issues(kit, rel, skeleton.read_text(encoding="utf-8")) == []


def test_a_page_that_follows_the_rules_is_clean(kit):
    assert issues(kit, "flows/checkout.md", GOOD) == []


@pytest.mark.parametrize("change, expected", [
    (("type: business-flow", "type: flowchart"), "type 'flowchart' is not one of"),
    (("title: Checkout\n", ""), "no title"),
    (("description: How an order goes from the cart to a paid invoice, and what happens when the payment fails.",
      "description: Checkout."), "description should say in 40–300 characters"),
    (("> **TL;DR:** The cart", "The cart"), "no `> **TL;DR:** …`"),
    (("## Failure handling", "#### Failure handling"), "skips a level (h2 → h4)"),
    (("## Data touched\nThe orders table.\n", ""), "missing sections from the business-flow skeleton: data touched"),
    (("## Steps\n1. Pay.", "## Steps\nAs mentioned above, pay."), "vague reference 'As mentioned above'"),
    (("## Summary\n", "# Summary\n"), "2 H1 headings"),
])
def test_each_rule(kit, change, expected):
    found = issues(kit, "flows/checkout.md", GOOD.replace(*change))
    assert any(expected in i for i in found), found


def test_headings_inside_code_do_not_count(kit):
    text = GOOD.replace("## Steps\n1. Pay.", "## Steps\n```bash\n# a shell comment, not an H1\n```")
    assert issues(kit, "flows/checkout.md", text) == []


def test_word_budgets_count_prose_only(kit):
    words = " ".join(["word"] * 420)
    table = "\n".join(f"| {words} |" for _ in range(3))
    assert issues(kit, "flows/checkout.md", GOOD.replace("Retries once.", table)) == []
    found = issues(kit, "flows/checkout.md", GOOD.replace("Retries once.", words))
    assert any("section 'Failure handling' has 420 words" in i for i in found)
    big = "\n\n".join(f"## Part {n}\n{' '.join(['word'] * 390)}" for n in range(5))
    assert any("words of prose (budget 1500)" in i for i in issues(kit, "flows/checkout.md", GOOD + big))


def test_the_skeleton_is_matched_by_path_before_type(kit):
    brief = (KIT_DIR / "templates" / "skeletons" / "repo-brief.md").read_text(encoding="utf-8")
    other = brief.replace("## Build, test and run", "## Something else")
    assert any("repo-brief skeleton" in i for i in issues(kit, "repos/api/brief.md", other))
    assert not any("skeleton" in i for i in issues(kit, "overview/stack.md", other))      # same type, other path


def test_the_project_copy_of_a_skeleton_wins(kit):
    sk = kit.root / ".camarones" / "skeletons" / "business-flow.md"
    sk.parent.mkdir(parents=True, exist_ok=True)
    sk.write_text("---\ntype: business-flow\n---\n# Flow\n\n## Summary\n\n## Owners\n", encoding="utf-8")
    found = issues(kit, "flows/checkout.md", GOOD)
    assert any("missing sections from the business-flow skeleton: owners" in i for i in found)


@pytest.mark.parametrize("rel, text", [
    ("interview/repo-api.md", "---\ntype: interview\ntitle: x\n---\nno structure\n"),
    ("guides/how.md", "---\ntype: guide\ntitle: x\n---\nno structure\n"),
    ("overview/mine.md", "---\ntype: overview\ntitle: x\nx-owner: human\n---\nno structure\n"),
])
def test_skipped_pages(kit, rel, text):
    assert issues(kit, rel, text) == []


def test_strict_turns_the_warnings_into_errors(kit):
    write(kit, "flows/checkout.md", GOOD.replace("> **TL;DR:** The cart", "The cart"))
    errors, warns = kit.quality.check_structure(kit.docs.collect(), strict=True)
    assert warns == [] and any("TL;DR" in e for e in errors)


def test_check_runs_it(kit):
    write(kit, "flows/checkout.md", GOOD.replace("> **TL;DR:** The cart", "The cart"))
    _, warns = kit.docs.check()
    assert any("flows/checkout.md" in w and "TL;DR" in w for w in warns)


def test_skeletons_reach_the_project_and_an_edited_copy_is_kept(kit):
    kit.env.sync_kit_docs()
    dst = kit.root / ".camarones" / "skeletons"
    assert sorted(p.name for p in dst.glob("*.md")) == sorted([p.name for p in SKELETONS] + ["README.md"])
    (dst / "decision.md").write_text("ours\n", encoding="utf-8")
    kit.env.sync_kit_docs()
    assert (dst / "decision.md").read_text(encoding="utf-8") == "ours\n"
    assert ".camarones/skeletons" in kit.env.CHECKPOINT_PATHS


def test_init_templates_does_not_copy_skeletons_into_the_docs(kit):
    kit.env.init_templates(log=lambda _: None)
    assert not (kit.root / "skeletons").exists() and not (kit.root / "docs" / "skeletons").exists()


@pytest.mark.parametrize("module", ["radar", "quickarch"])
def test_pages_the_kit_writes_without_ai_have_a_tldr(module):
    src = (KIT_DIR / "lib" / f"{module}.py").read_text(encoding="utf-8")
    assert "> **TL;DR:**" in src


def test_unit_prompts_carry_the_writing_rules(kit):
    kit.plan.sync()
    text = kit.plan.prompt("discovery:api", "en")
    assert ".camarones/skeletons" in text and "TL;DR" in text and "no structure WARN" in text


def test_a_fresh_project_has_no_structure_warnings(kit):
    from conftest import wire_project
    wire_project(kit)
    (kit.root / "docs" / "overview.md").unlink()                  # the fixture's own bare page
    _, warns = kit.quality.check_structure(kit.docs.collect())
    assert warns == []
