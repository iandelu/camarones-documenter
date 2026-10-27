"""The evidence pack of an ADR (`lib/adr_pack.py`): what the project already knows about the files a decision touches —
code-graph neighbours, doc pages, other ADRs, commits, C4 elements, libraries, open questions — gathered without a model.
A source that is missing or broken leaves its part empty; it never stops the pack."""
from __future__ import annotations

import importlib
import json

import pytest
from fixtures.builder import git
from test_codemap import JAVA
from test_kanban_index import ORDER, PAY, world  # noqa: F401  (a fixture is found in the module that imports it)

ORDER_FILE = JAVA + "orders/OrderService.java"
PAY_FILE = JAVA + "payments/PaymentClient.java"
ADR_0001 = (f"---\ntype: decision\ntitle: 0001 — Orders in one service\nx-sources:\n  - {ORDER}#place\n---\n"
            "# 0001 — Orders in one service\n\n## Status\n\nAccepted (2026-01-02)\n\n## Decision\n\nKeep it together.\n")
MODEL = """model {
  shop = system 'Shop' {
    orders = service 'Orders' {
      technology 'Java · Spring Boot'
      metadata { repo 'api' }
    }
    cart = service 'Cart' {
      metadata { repo 'web' }
    }
  }
}
"""


def commit(kit, repo, rel, message):
    f = kit.ws / repo / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"{message}\n", encoding="utf-8", newline="\n")
    git(kit.ws / repo, "add", "-A")
    git(kit.ws / repo, "commit", "-q", "-m", message)


def write_doc(kit, rel, text):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8", newline="\n")
    return f


@pytest.fixture
def pack_world(world):  # noqa: F811
    kit = world[0]
    commit(kit, "api", ORDER_FILE, "feat(orders): place an order")
    write_doc(kit, "decisions/0001-orders.md", ADR_0001)
    return kit, importlib.import_module("lib.adr_pack"), {"id": "0002", "touches": [ORDER]}


@pytest.fixture
def adr(kit):
    return importlib.import_module("lib.adr")


def test_the_pack_gathers_what_the_project_knows(pack_world):
    kit, adr_pack, state = pack_world
    p = adr_pack.build(state)
    assert p["touches"] == [ORDER]
    assert PAY in p["neighbours"]
    assert [x["page"] for x in p["pages"]] == ["orders.md"] and p["pages"][0]["title"] == "Orders"
    assert [x["id"] for x in p["adrs"]] == ["0001"]                   # cites OrderService too
    assert p["commits"] and all("OrderService.java" in "".join(c["files"]) for c in p["commits"])
    assert adr_pack.summary(p)["pages"] == 1
    md = adr_pack.render(p)
    assert "## Doc pages" in md and "Orders" in md and len(md) <= adr_pack.LIMIT + 20


def test_each_part_says_what_it_is(pack_world):
    kit, adr_pack, state = pack_world
    p = adr_pack.build(state)
    assert p["pages"] == [{"page": "orders.md", "title": "Orders", "description": "", "trust": "draft"}]
    assert p["adrs"] == [{"id": "0001", "title": "Orders in one service", "status": "accepted",
                          "path": "decisions/0001-orders.md"}]
    assert p["commits"] == [{"repo": "api", "subject": "feat(orders): place an order", "author": "Test",
                             "files": [ORDER_FILE]}]
    assert adr_pack.summary(p) == {"files": 1, "neighbours": len(p["neighbours"]), "pages": 1, "adrs": 1, "commits": 1,
                                   "c4": 0, "libraries": 0, "questions": 0}
    md = adr_pack.render(p)
    for heading in ("## Files", "## Neighbouring files", "## Doc pages", "## Decisions", "## Commits"):
        assert heading in md, heading
    assert "## C4 elements" not in md and "## Libraries" not in md and "## Open questions" not in md
    assert f"`{ORDER}`" in md and "`orders.md`" in md and "0001" in md and "feat(orders): place an order" in md


def test_a_fresh_project_gets_an_empty_pack(kit):
    adr_pack = importlib.import_module("lib.adr_pack")
    p = adr_pack.build({"id": "0001", "touches": ["api:src/main/java/demo/Api.java"]})
    assert p["neighbours"] == [] and p["pages"] == [] and p["c4"] == [] and p["libraries"] == [] and p["questions"] == []
    assert p["adrs"] == [] and [c["subject"] for c in p["commits"]] == ["initial"]    # git history is all there is
    assert "api:src/main/java/demo/Api.java" in adr_pack.render(p)


def test_a_state_with_no_touches_gets_an_empty_pack(kit):
    adr_pack = importlib.import_module("lib.adr_pack")
    p = adr_pack.build({"id": "0001"})
    assert p["touches"] == [] and adr_pack.summary(p) == dict.fromkeys(
        ("files", "neighbours", "pages", "adrs", "commits", "c4", "libraries", "questions"), 0)
    assert adr_pack.render(p) == ""


def test_a_source_that_fails_leaves_its_part_empty(pack_world, monkeypatch):
    kit, adr_pack, state = pack_world
    boom = RuntimeError("broken")
    for module, name in (("lib.c4edit", "index"), ("lib.inventory", "load"), ("lib.history", "commits")):
        monkeypatch.setattr(importlib.import_module(module), name, lambda *a, **k: (_ for _ in ()).throw(boom))
    p = adr_pack.build(state)
    assert p["c4"] == [] and p["libraries"] == [] and p["commits"] == []
    assert PAY in p["neighbours"] and [x["page"] for x in p["pages"]] == ["orders.md"]


def test_an_index_that_cannot_be_read_leaves_its_parts_empty(pack_world, monkeypatch):
    kit, adr_pack, state = pack_world
    index = importlib.import_module("lib.kanban.index")
    monkeypatch.setattr(index, "connect", lambda: (_ for _ in ()).throw(OSError("locked")))
    p = adr_pack.build(state)
    assert p["neighbours"] == [] and p["pages"] == [] and p["adrs"] == [] and p["commits"]


def test_one_query_that_fails_does_not_take_the_other_down(pack_world, monkeypatch):
    kit, adr_pack, state = pack_world
    index = importlib.import_module("lib.kanban.index")
    monkeypatch.setattr(index, "neighbours", lambda *a: (_ for _ in ()).throw(ValueError("odd")))
    p = adr_pack.build(state)
    assert p["neighbours"] == [] and [x["page"] for x in p["pages"]] == ["orders.md"]


def test_pages_leave_out_decisions_wherever_they_are(pack_world):
    kit, adr_pack, state = pack_world
    write_doc(kit, "notes/choice.md", f"---\ntype: decision\ntitle: Choice\nx-sources:\n  - {ORDER}\n---\n# Choice\n")
    write_doc(kit, "flows/checkout.md", f"---\ntitle: Checkout\ndescription: How a cart becomes an order\nx-sources:\n  - {ORDER}\n---\n# Checkout\n")
    p = adr_pack.build(state)
    assert [x["page"] for x in p["pages"]] == ["flows/checkout.md", "orders.md"]
    assert p["pages"][0]["description"] == "How a cart becomes an order"
    assert [x["id"] for x in p["adrs"]] == ["0001"]


def test_the_adr_itself_is_not_its_own_evidence(pack_world):
    kit, adr_pack, state = pack_world
    assert adr_pack.build({**state, "id": "0001"})["adrs"] == []


def test_commits_are_those_touching_the_files_newest_first(pack_world):
    kit, adr_pack, state = pack_world
    commit(kit, "api", PAY_FILE, "feat(pay): charge a card")
    commit(kit, "api", ORDER_FILE, "fix(orders): empty cart")
    commit(kit, "web", "src/cart.tsx", "feat(cart): add")
    p = adr_pack.build(state)
    assert [c["subject"] for c in p["commits"]] == ["fix(orders): empty cart", "feat(orders): place an order"]
    both = adr_pack.build({**state, "touches": [ORDER, PAY]})
    assert [c["subject"] for c in both["commits"]] == ["fix(orders): empty cart", "feat(pay): charge a card",
                                                       "feat(orders): place an order"]
    assert both["commits"][1]["files"] == [PAY_FILE]                  # only the touched files of each commit
    assert adr_pack.build({**state, "touches": ["web:src/cart.tsx"]})["commits"][0]["repo"] == "web"


def test_a_folder_that_is_not_a_repo_has_no_history(pack_world):
    kit, adr_pack, state = pack_world
    assert adr_pack.build({**state, "touches": ["nowhere:a.java", "cam-docs:docs/orders.md"]})["commits"] == []


def test_open_questions_that_name_a_touched_file(pack_world):
    kit, adr_pack, state = pack_world
    write_doc(kit, "interview/open-questions.md",
              "# Open questions\n\n- [ ] (2026-01-01, docs-gap) Why does OrderService.java retry twice? — asked 3×\n"
              "- [x] OrderService is settled\n- [ ] Who owns PaymentClient?\n"
              f"- [ ] Is {ORDER} thread safe?\n- [ ] Unrelated question\n")
    p = adr_pack.build(state)
    assert p["questions"] == ["(2026-01-01, docs-gap) Why does OrderService.java retry twice? — asked 3×",
                              f"Is {ORDER} thread safe?"]
    assert "## Open questions" in adr_pack.render(p)


def know_the_stack(kit):
    write_doc(kit, "architecture/model.c4", MODEL)
    rows = [{"repo": "api", "ecosystem": "Maven", "name": "zip4j", "version": "2", "declared": "2", "scope": "runtime",
             "category": "other", "language": "Java", "source": "api:api-core/pom.xml"},
            {"repo": "api", "ecosystem": "Maven", "name": "redis", "version": "7", "declared": "7", "scope": "runtime",
             "category": "cache", "language": "Java", "source": "api:api-core/pom.xml"},
            {"repo": "api", "ecosystem": "Maven", "name": "junit", "version": "5", "declared": "5", "scope": "test",
             "category": "testing", "language": "Java", "source": "api:api-core/pom.xml"},
            {"repo": "web", "ecosystem": "npm", "name": "react", "version": "18", "declared": "18", "scope": "runtime",
             "category": "framework", "language": "TypeScript", "source": "web:package.json"}]
    inventory = importlib.import_module("lib.inventory")
    inventory.DATA.parent.mkdir(parents=True, exist_ok=True)
    inventory.DATA.write_text(json.dumps({"libraries": rows}), encoding="utf-8")


def test_the_c4_elements_and_libraries_of_the_touched_repos(pack_world):
    kit, adr_pack, state = pack_world
    know_the_stack(kit)
    p = adr_pack.build(state)
    assert p["c4"] == [{"fqn": "shop.orders", "title": "Orders", "technology": "Java · Spring Boot", "repo": "api"}]
    assert p["libraries"] == [                                  # runtime only, the kinds a decision is about first
        {"repo": "api", "name": "redis", "version": "7", "category": "cache", "manifest": "api-core/pom.xml"},
        {"repo": "api", "name": "zip4j", "version": "2", "category": "other", "manifest": "api-core/pom.xml"}]
    md = adr_pack.render(p)
    assert "## C4 elements" in md and "shop.orders" in md and "## Libraries" in md and "redis" in md and "junit" not in md


def test_every_list_is_capped(pack_world, monkeypatch):
    kit, adr_pack, state = pack_world
    for i in range(3):
        write_doc(kit, f"extra/p{i}.md", f"---\ntitle: P{i}\nx-sources:\n  - {ORDER}\n---\n# P{i}\n")
        write_doc(kit, f"decisions/000{i + 3}-d.md", ADR_0001.replace("0001", f"000{i + 3}"))
    commit(kit, "api", ORDER_FILE, "second")
    for name in ("PAGES", "ADRS", "COMMITS", "NEIGHBOURS"):
        monkeypatch.setattr(adr_pack, name, 1)
    know_the_stack(kit)
    monkeypatch.setattr(adr_pack, "C4", 1)
    monkeypatch.setattr(adr_pack, "LIBRARIES", 1)
    p = adr_pack.build({**state, "touches": [ORDER, PAY, "web:src/App.jsx"]})
    assert len(p["pages"]) == len(p["adrs"]) == len(p["c4"]) == len(p["libraries"]) == 1 and len(p["commits"]) == 1
    assert p["libraries"][0]["name"] == "redis"
    assert len(adr_pack.build({**state, "touches": [PAY]})["neighbours"]) == 1


def test_the_markdown_is_cut_at_the_limit(pack_world, monkeypatch):
    kit, adr_pack, state = pack_world
    p = adr_pack.build(state)
    p["commits"] = [{"repo": "api", "subject": f"commit number {i} " + "x" * 60, "author": "A", "files": [ORDER_FILE]}
                    for i in range(adr_pack.COMMITS)]
    monkeypatch.setattr(adr_pack, "LIMIT", 600)
    md = adr_pack.render(p)
    assert md.endswith("\n…(cut)") and len(md) <= 600 + 20 and md.startswith("## Files")
    assert "…(cut)" not in adr_pack.render({**p, "commits": []})


def test_affected_are_the_pages_citing_the_touches(pack_world, adr):
    kit, adr_pack, state = pack_world
    write_doc(kit, "notes/choice.md", f"---\ntype: decision\ntitle: Choice\nx-sources:\n  - {ORDER}\n---\n# Choice\n")
    a = adr.new({"title": "More orders", "kind": "new", "touches": [ORDER]})
    assert a["id"] == "0002" and adr.get("0002")["affected"] == ["orders.md"]
    assert adr.get("0001")["affected"] == []                          # a legacy ADR has no state to read touches from
    b = adr.new({"title": "Nothing touched", "kind": "new"})
    assert adr.get(b["id"])["affected"] == []


def test_affected_is_empty_when_the_index_cannot_be_read(pack_world, adr, monkeypatch):
    kit, adr_pack, state = pack_world
    adr.new({"title": "More orders", "kind": "new", "touches": [ORDER]})
    index = importlib.import_module("lib.kanban.index")
    monkeypatch.setattr(index, "connect", lambda: (_ for _ in ()).throw(OSError("locked")))
    assert adr.get("0002")["affected"] == []


def test_pack_moves_the_phase_and_is_cached(adr, kit):
    a = adr.new({"title": "A", "kind": "new", "touches": ["api:pom.xml"]})
    assert adr.read_pack(a["id"]) is None
    out = adr.pack(a["id"])
    assert out["summary"]["files"] == 1 and adr.get(a["id"])["state"]["phase"] == "evidence"
    assert adr.read_pack(a["id"])["markdown"] == out["markdown"]
    assert adr.read_pack(a["id"])["summary"] == out["summary"]
    folder = kit.root / ".camarones" / ".cache" / "adr" / a["id"]
    assert json.loads((folder / "pack.json").read_text(encoding="utf-8"))["touches"] == ["api:pom.xml"]
    assert (folder / "pack.md").read_text(encoding="utf-8") == out["markdown"]


def test_pack_never_moves_a_review_backwards_and_can_refresh(adr, kit):
    a = adr.write_without_ai(adr.new({"title": "A", "kind": "new", "touches": ["api:pom.xml"]})["id"])
    adr.pack(a["id"])
    assert adr.get(a["id"])["state"]["phase"] == "review"
    again = adr.pack(a["id"])
    assert again["summary"]["files"] == 1
    b = adr.new({"title": "B", "kind": "new", "touches": ["api:pom.xml"]})
    adr.pack(b["id"])
    adr.pack(b["id"])
    assert adr.get(b["id"])["state"]["phase"] == "evidence"


def test_pack_follows_a_renumbered_adr_in_the_cache(adr, kit):
    a = adr.new({"title": "A", "kind": "new", "touches": ["api:pom.xml"]})
    adr.pack(a["id"])
    (kit.root / "docs" / "decisions").mkdir(parents=True, exist_ok=True)
    (kit.root / "docs" / "decisions" / f"{a['id']}-taken.md").write_text("# taken\n\n## Status\n\nAccepted\n", encoding="utf-8")
    moved = adr.write_without_ai(a["id"])
    assert moved["id"] != a["id"] and adr.read_pack(moved["id"])["summary"]["files"] == 1


def test_pack_refuses_what_it_cannot_find_or_a_legacy_adr(adr, kit):
    with pytest.raises(KeyError):
        adr.pack("0009")
    with pytest.raises(KeyError):
        adr.pack("nope")
    with pytest.raises(KeyError):
        adr.read_pack("nope")
    assert adr.read_pack("0009") is None
    (kit.root / "docs" / "decisions").mkdir(parents=True, exist_ok=True)
    (kit.root / "docs" / "decisions" / "0003-old.md").write_text("# 0003 — Old\n\n## Status\n\nAccepted\n", encoding="utf-8")
    with pytest.raises(adr.AdrError, match="start its review first"):
        adr.pack("0003")
