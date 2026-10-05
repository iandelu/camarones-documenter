"""Diagrams the docs must carry: check warns about the missing ones and the plan has a unit that adds them."""
from __future__ import annotations


def page(kit, rel, fm_type, body):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"---\ntitle: {rel}\ntype: {fm_type}\n---\n# {rel}\n\n{body}\n", encoding="utf-8")


def warns(kit):
    return kit.quality.check_diagrams(kit.docs.collect())[1]


SEQ = "```mermaid\nsequenceDiagram\n  a->>b: hi\n```"
STATE = "```mermaid\nstateDiagram-v2\n  [*] --> placed\n```"
LIFECYCLE = "An order has a status. The status moves from placed to paid; each state change is audited."


def test_a_flow_needs_a_sequence_diagram(kit):
    page(kit, "flows/checkout.md", "business-flow", "Steps without a picture.")
    page(kit, "flows/refund.md", "business-flow", SEQ)
    page(kit, "flows/index.md", "business-flow", "- [Checkout](checkout.md)")      # the catalogue is a list
    w = warns(kit)
    assert any("flows/checkout.md" in x and "sequenceDiagram" in x for x in w)
    assert not any("flows/refund.md" in x or "flows/index.md" in x for x in w)


def test_a_lifecycle_needs_a_state_diagram(kit):
    page(kit, "domain/orders.md", "domain", LIFECYCLE + "\n\n```mermaid\nflowchart LR\n  a --> b\n```")
    page(kit, "domain/payments.md", "domain", LIFECYCLE + "\n\n" + STATE)
    w = warns(kit)
    assert any("domain/orders.md" in x and "stateDiagram-v2" in x for x in w)
    assert not any("domain/payments.md" in x for x in w)


def test_pages_that_explain_structure_need_some_diagram(kit):
    page(kit, "data/redis.md", "data-model", "Keys and TTLs.")
    page(kit, "domain/contexts.md", "domain", "Three contexts.")
    page(kit, "overview/system.md", "overview", "What it is.")
    page(kit, "overview/tooling.md", "overview", "Tools found by radar.")         # a scan result, not an explanation
    page(kit, "deployment/environments.md", "deployment", "```likec4-view\ndeploy_prod\n```")
    w = warns(kit)
    for p in ("data/redis.md", "domain/contexts.md", "overview/system.md"):
        assert any(p in x for x in w), p
    assert not any("overview/tooling.md" in x or "deployment/environments.md" in x for x in w)


def test_working_notes_are_not_judged(kit):
    page(kit, "interview/discovery/api.md", "interview", LIFECYCLE)
    assert warns(kit) == []


def test_check_reports_the_gaps_as_warnings_only(kit):
    page(kit, "flows/checkout.md", "business-flow", "Steps.")
    errors, w = kit.docs.check()
    assert not any("sequenceDiagram" in e for e in errors)
    assert any("sequenceDiagram" in x for x in w)


def test_the_plan_has_a_diagrams_unit_after_the_content_it_draws(kit):
    data = kit.plan.sync()
    u = next(x for x in data["units"] if x["id"] == "diagrams")
    assert {"domain", "data", "flows-catalog"} <= set(u["deps"])
    kit.plan.ensure("flow:checkout", "flow")
    u = next(x for x in kit.plan.sync()["units"] if x["id"] == "diagrams")
    assert "flow:checkout" in u["deps"]


def test_quick_profile_has_no_diagrams_unit(kit):
    kit.env.set_profile("quick")
    assert "diagrams" not in [u["id"] for u in kit.plan.sync()["units"] if u["status"] != "dropped"]


def test_the_wiki_prompt_asks_for_diagrams(kit):
    p = kit.env.wiki_prompt("api", "init")
    assert "sequenceDiagram" in p and "stateDiagram-v2" in p
