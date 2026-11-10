"""`camaron check`'s "sources no longer exist" gate: an `x-sources` entry `c4:<element>` (allowed by CONVENTIONS and
PLAYBOOK) names an element of the C4 model in docs/architecture/*.c4, not a file in a repo called `c4`."""
from __future__ import annotations

C4 = """model {
  shop = system 'Shop' {
    orders = service 'Orders' {
      description 'Takes orders'
    }
  }
}
"""


def page(kit, rel, sources):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"---\ntitle: {rel}\nx-sources:\n" + "".join(f"  - {s}\n" for s in sources) + "---\n# P\n\nText.\n",
                 encoding="utf-8")


def model(kit):
    arch = kit.root / "docs" / "architecture"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "model.c4").write_text(C4, encoding="utf-8")


def orphans(kit, rel):
    return next(r for r in kit.docs.collect() if r["file"] == f"docs/{rel}")["orphan_sources"]


def test_an_existing_c4_element_is_not_an_orphan(kit):
    model(kit)
    page(kit, "domain/contexts.md", ["c4:shop.orders", "c4:shop"])
    assert orphans(kit, "domain/contexts.md") == []
    errors, _ = kit.docs.check()
    assert not any("sources no longer exist" in e for e in errors)


def test_a_missing_c4_element_is_an_orphan(kit):
    model(kit)
    page(kit, "domain/contexts.md", ["c4:shop.orders", "c4:shop.billing"])
    assert orphans(kit, "domain/contexts.md") == ["c4:shop.billing"]
    errors, _ = kit.docs.check()
    assert any("sources no longer exist" in e and "c4:shop.billing" in e for e in errors)


def test_a_c4_source_without_a_model_is_an_orphan(kit):
    page(kit, "domain/contexts.md", ["c4:shop.orders"])
    assert orphans(kit, "domain/contexts.md") == ["c4:shop.orders"]


def test_a_repo_file_source_still_resolves(kit):
    page(kit, "a.md", ["api:pom.xml", "api:nope/Missing.java"])
    assert orphans(kit, "a.md") == ["api:nope/Missing.java"]
