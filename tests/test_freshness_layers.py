"""Freshness L2 and L3 (R30, H14). L2: an x-source may name a symbol (`repo:path#Class.method`); it is found again
wherever it moved, so only a change to its own body makes the page suspect. L3: a page may cite other pages or C4
elements; it becomes suspect when one of them does (pages) or changes (C4), and stale when one is gone."""
from __future__ import annotations

import pytest

SVC = "src/main/java/demo/OrderService.java"
JAVA = """package demo;

public class OrderService {
    // places an order
    public Order place(Request r) {
        validate(r);
        return repo.save(new Order(r));
    }

    void validate(Request r) {
        if (r == null) { throw new IllegalArgumentException("{"); }
    }
}
"""
PY = '''import os


class Billing:
    def charge(self, amount):
        return amount * 2

    def refund(self, amount):
        return -amount
'''


def page(kit, rel, sources):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"---\ntitle: {rel}\nx-sources:\n" + "".join(f"  - {s}\n" for s in sources) + "---\n# P\n\nText.\n",
                 encoding="utf-8")
    return f


def code(kit, rel, text, repo="api"):
    f = kit.ws / repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


@pytest.fixture
def fresh(kit):
    from lib.harness import freshness
    code(kit, SVC, JAVA)
    code(kit, "billing.py", PY, repo="worker")
    return freshness


def state(fresh, logical):
    return fresh.status(logical)["state"]


# ---------- L2: symbols ----------
def test_a_symbol_that_moved_stays_fresh(kit, fresh):
    page(kit, "flows/order.md", [f"api:{SVC}#OrderService.place"])
    fresh.stamp_all()
    code(kit, SVC, JAVA.replace("public class OrderService {\n",
                                "public class OrderService {\n    private final Repo repo;\n\n    Audit audit;\n\n"))
    assert state(fresh, "flows/order.md") == "fresh"


def test_a_change_elsewhere_in_the_file_does_not_count(kit, fresh):
    page(kit, "flows/order.md", [f"api:{SVC}#place"])
    fresh.stamp_all()
    code(kit, SVC, JAVA.replace('throw new IllegalArgumentException("{")', "return"))
    assert state(fresh, "flows/order.md") == "fresh"


def test_a_change_to_the_symbol_is_suspect_and_its_removal_stale(kit, fresh):
    page(kit, "flows/order.md", [f"api:{SVC}#place"])
    fresh.stamp_all()
    code(kit, SVC, JAVA.replace("validate(r);", "validate(r);\n        audit(r);"))
    assert state(fresh, "flows/order.md") == "suspect"
    code(kit, SVC, JAVA.replace("public Order place(Request r)", "public Order submit(Request r)"))
    assert state(fresh, "flows/order.md") == "stale"


def test_python_symbols(kit, fresh):
    page(kit, "data/billing.md", ["worker:billing.py#Billing.refund"])
    fresh.stamp_all()
    code(kit, "billing.py", PY.replace("        return amount * 2", "        return amount * 3"), repo="worker")
    assert state(fresh, "data/billing.md") == "fresh"
    code(kit, "billing.py", PY.replace("return -amount", "return -abs(amount)"), repo="worker")
    assert state(fresh, "data/billing.md") == "suspect"


def test_a_symbol_cited_before_l2_keeps_its_whole_file_fingerprint(kit, fresh):
    page(kit, "flows/order.md", [f"api:{SVC}#place"])
    whole = {"h": fresh._hash(fresh._norm(JAVA.splitlines())), "n": 0}
    data = fresh._load()
    data["pages"]["flows/order.md"] = {"sources": {f"api:{SVC}#place": whole},
                                       "body_sha": fresh._pages()["flows/order.md"][1]}
    from lib.common import save_json
    save_json(fresh.FILE, data)
    assert state(fresh, "flows/order.md") == "fresh"


def test_symbols_locate_in_c_family_files(fresh):
    from lib.harness import symbols
    lines = JAVA.splitlines()
    assert symbols.locate(lines, "place", ".java") == (4, 7)
    assert symbols.locate(lines, "OrderService.validate", ".java") == (9, 11)
    assert symbols.locate(lines, "save", ".java") is None                                 # a call, not a declaration


# ---------- L3: pages and C4 elements ----------
def test_a_page_built_on_a_suspect_page_is_suspect_too(kit, fresh):
    page(kit, "flows/order.md", [f"api:{SVC}#place"])
    page(kit, "overview/journeys.md", ["docs/flows/order.md"])
    page(kit, "overview/index-of-journeys.md", ["docs/overview/journeys.md"])
    fresh.stamp_all()
    assert state(fresh, "overview/index-of-journeys.md") == "fresh"
    code(kit, SVC, JAVA.replace("validate(r);", "validate(r);\n        audit(r);"))
    s = fresh.status("overview/journeys.md")
    assert s["state"] == "suspect" and s["changed"] == ["docs/flows/order.md"]
    assert state(fresh, "overview/index-of-journeys.md") == "suspect"


def test_rewriting_the_cited_page_does_not_make_dependants_suspect(kit, fresh):
    f = page(kit, "flows/order.md", [f"api:{SVC}#place"])
    page(kit, "overview/journeys.md", ["docs/flows/order.md"])
    fresh.stamp_all()
    f.write_text(f.read_text(encoding="utf-8") + "\nMore detail.\n", encoding="utf-8")
    assert state(fresh, "overview/journeys.md") == "fresh"


def test_a_cited_page_that_is_gone_makes_it_stale(kit, fresh):
    f = page(kit, "flows/order.md", [f"api:{SVC}#place"])
    page(kit, "overview/journeys.md", ["docs/flows/order.md"])
    fresh.stamp_all()
    f.unlink()
    assert state(fresh, "overview/journeys.md") == "stale"


def test_cycles_settle(kit, fresh):
    page(kit, "flows/a.md", ["docs/flows/b.md", f"api:{SVC}#place"])
    page(kit, "flows/b.md", ["docs/flows/a.md"])
    fresh.stamp_all()
    code(kit, SVC, JAVA.replace("validate(r);", "validate(r);\n        audit(r);"))
    assert state(fresh, "flows/a.md") == state(fresh, "flows/b.md") == "suspect"


C4 = """model {
  shop = system 'Shop' {
    orders = service 'Orders' {
      description 'Takes orders'
    }
    billing = service 'Billing'
  }
}
"""


def test_a_c4_element_that_changes_or_goes(kit, fresh):
    arch = kit.root / "docs" / "architecture"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "model.c4").write_text(C4, encoding="utf-8")
    page(kit, "domain/contexts.md", ["c4:shop.orders"])
    fresh.stamp_all()
    (arch / "model.c4").write_text(C4.replace("billing = service 'Billing'", "billing = service 'Payments'"),
                                   encoding="utf-8")
    assert state(fresh, "domain/contexts.md") == "fresh"
    (arch / "model.c4").write_text(C4.replace("Takes orders", "Takes and ships orders"), encoding="utf-8")
    assert state(fresh, "domain/contexts.md") == "suspect"
    (arch / "model.c4").write_text(C4.replace("orders = service", "checkout = service"), encoding="utf-8")
    assert state(fresh, "domain/contexts.md") == "stale"


def test_code_paths_name_symbols_and_pages(fresh):
    assert fresh.code_paths([f"api:{SVC}#OrderService.place", "docs/flows/a.md", "c4:shop.orders"]) == [
        f"api/{SVC}#OrderService.place", "docs/flows/a.md", "c4:shop.orders"]


def test_anchors_into_other_files_stay_whole_file(kit, fresh):
    page(kit, "guides/run.md", ["api:README.md#install"])
    fresh.stamp_all()
    assert state(fresh, "guides/run.md") == "fresh"
    assert fresh.kind("api:README.md#install") == "code"
