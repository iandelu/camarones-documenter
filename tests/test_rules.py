"""X8: business rules as `:::rule ID` blocks with `enforced:` and `test:` anchors (`repo:path#Symbol`). `check` finds
each symbol again (lib/harness/symbols.py), the portal renders the block, and agents get it flattened."""
from __future__ import annotations

RULE = """# Ordering rules

> **TL;DR:** What an order must satisfy.

:::rule ORD-1 Non-empty orders
enforced: api:src/OrderService.java#OrderService.place
test: api:src/OrderServiceTest.java#OrderServiceTest.rejectsEmptyCart
An order needs at least one line.
:::
"""


def code(kit):
    src = kit.ws / "api" / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "OrderService.java").write_text(
        "public class OrderService {\n  public void place(Order o) {\n    if (o.lines().isEmpty()) throw new X();\n  }\n}\n",
        encoding="utf-8")
    (src / "OrderServiceTest.java").write_text(
        "class OrderServiceTest {\n  @Test void rejectsEmptyCart() {\n    assertThrows();\n  }\n}\n", encoding="utf-8")


def page(kit, rel, text):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("---\ntitle: Rules\ndescription: Ordering rules.\n---\n" + text, encoding="utf-8")


def test_rules_are_parsed(kit):
    (r,) = kit.docs.rules(RULE)
    assert r == {"id": "ORD-1", "title": "Non-empty orders", "text": "An order needs at least one line.",
                 "enforced": ["api:src/OrderService.java#OrderService.place"],
                 "test": ["api:src/OrderServiceTest.java#OrderServiceTest.rejectsEmptyCart"]}


def test_rules_are_flattened_for_agents(kit):
    flat = kit.docs.flatten_directives(RULE)
    assert ":::" not in flat
    assert "**Rule ORD-1 — Non-empty orders**" in flat and "An order needs at least one line." in flat
    assert "Enforced by: `api:src/OrderService.java#OrderService.place`" in flat
    assert "Tested by: `api:src/OrderServiceTest.java#OrderServiceTest.rejectsEmptyCart`" in flat


def test_check_finds_each_symbol_again(kit):
    code(kit)
    page(kit, "domain/rules.md", RULE)
    errors, warns = kit.quality.check_rules(kit.docs.collect())
    assert errors == [] and warns == []
    (kit.ws / "api" / "src" / "OrderService.java").write_text("public class OrderService {\n  void submit() {}\n}\n",
                                                              encoding="utf-8")
    errors, _ = kit.quality.check_rules(kit.docs.collect())
    assert any("ORD-1" in e and "OrderService.place" in e for e in errors), errors


def test_check_flags_duplicates_and_loose_rules(kit):
    code(kit)
    page(kit, "domain/rules.md", RULE)
    page(kit, "flows/checkout.md", "# Checkout\n\n:::rule ORD-1\nenforced: api:src/OrderService.java#OrderService.place\n"
                                   "Same id.\n:::\n\n:::rule ORD-2\nNobody enforces this.\n:::\n\n"
                                   ":::rule ORD-3\nenforced: OrderService.place\nNo file.\n:::\n")
    errors, warns = kit.quality.check_rules(kit.docs.collect())
    assert any("ORD-1" in e and "domain/rules.md" in e for e in errors)                  # duplicate id
    assert any("ORD-2" in w and "enforced" in w for w in warns)
    assert any("ORD-3" in w and "#" in w for w in warns)                                # repo:path#Symbol expected


def test_rules_run_with_check(kit):
    assert kit.quality.check_rules in kit.quality.CHECKS
