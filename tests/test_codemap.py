"""The code map: graphify's node-per-symbol graph folded into something a person can read (modules → files)."""
from __future__ import annotations

import json


def node(nid, label, path="", cls=False):
    return {"id": nid, "label": label, "source_file": path, "file_type": "code", "_callable_class": cls,
            "source_location": "L1"}


JAVA = "api-core/src/main/java/demo/shop/"
GRAPH = {
    "built_at_commit": "abc1234",
    "nodes": [
        node("order", "OrderService", JAVA + "orders/OrderService.java", True),
        node("order_place", ".place", JAVA + "orders/OrderService.java"),
        node("repo", "OrderRepository", JAVA + "orders/OrderRepository.java", True),
        node("pay", "PaymentClient", JAVA + "payments/PaymentClient.java", True),
        node("pay_dto", "PaymentDto", JAVA + "payments/dto/PaymentDto.java", True),
        node("web", "OrderResource", "api-web/src/main/java/demo/shop/web/OrderResource.java", True),
        node("test", "OrderServiceTest", "api-core/src/test/java/demo/shop/orders/OrderServiceTest.java", True),
        node("ext", "Logger", ""),
        node("pom", "pom", "api-core/pom.xml"),
    ],
    "links": [
        {"source": "web", "target": "order", "relation": "calls"},
        {"source": "order_place", "target": "repo", "relation": "calls"},
        {"source": "order_place", "target": "pay", "relation": "calls"},
        {"source": "order", "target": "pay", "relation": "imports"},
        {"source": "pay", "target": "pay_dto", "relation": "references"},
        {"source": "order", "target": "order_place", "relation": "method"},        # structure, not a dependency
        {"source": "test", "target": "order", "relation": "calls"},                # tests are left out
        {"source": "order", "target": "ext", "relation": "references"},             # third-party left out
    ],
}


def write_graph(kit, repo="api", graph=GRAPH):
    d = kit.root / "graph" / repo
    d.mkdir(parents=True, exist_ok=True)
    (d / "graph.json").write_text(json.dumps(graph), encoding="utf-8")


def test_files_fold_into_modules_and_packages(kit):
    write_graph(kit)
    m = kit.codemap.build("api")
    files = {f["label"]: f for f in m["files"]}
    assert set(files) == {"OrderService", "OrderRepository", "PaymentClient", "PaymentDto", "OrderResource"}
    groups = {g["id"]: g for g in m["groups"]}
    assert {groups[files[n]["group"]]["label"] for n in files} == {"core/orders", "core/payments",
                                                                  "core/payments/dto", "web/web"}
    assert m["stats"] == {"files": 5, "groups": 4, "commit": "abc1234"}


def test_files_keep_their_package_inside_the_group_for_drilling_down(kit):
    nodes = [node(f"c{i}", f"C{i}", f"svc/src/main/java/demo/logic/{'builder' if i % 2 else 'cache'}/C{i}.java", True)
             for i in range(10)] + [node(p, p.title(), f"svc/src/main/java/demo/{p}/{p.title()}.java", True)
                                    for p in ("web", "api", "dto", "util", "config", "model")]
    write_graph(kit, graph={"nodes": nodes, "links": []})
    m = kit.codemap.build("api")
    assert {f["sub"] for f in m["files"] if "/logic/" in f["path"]} == {"builder", "cache"}


def test_dependencies_are_counted_between_files_and_between_groups(kit):
    write_graph(kit)
    m = kit.codemap.build("api")
    fid = {f["label"]: i for i, f in enumerate(m["files"])}
    order = m["files"][fid["OrderService"]]
    assert sorted(m["files"][t]["label"] for t, _ in order["out"]) == ["OrderRepository", "PaymentClient"]
    assert dict((m["files"][t]["label"], w) for t, w in order["out"])["PaymentClient"] == 2     # a call and an import
    assert [m["files"][s]["label"] for s, _ in order["in"]] == ["OrderResource"]
    gl = {(m["groups"][l["s"]]["label"], m["groups"][l["t"]]["label"]): l["w"] for l in m["links"]}
    assert gl == {("web/web", "core/orders"): 1, ("core/orders", "core/payments"): 2,
                  ("core/payments", "core/payments/dto"): 1}


def test_the_most_used_files_are_the_core(kit):
    write_graph(kit)
    m = kit.codemap.build("api")
    assert [m["files"][i]["label"] for i in m["core"][:2]] == ["PaymentClient", "OrderService"]


def test_big_repos_are_cut_to_a_readable_number_of_groups(kit):
    nodes = [node(f"c{i}", f"C{i}", f"svc/src/main/java/demo/p{i % 40}/q{i}/C{i}.java", True) for i in range(200)]
    write_graph(kit, graph={"nodes": nodes, "links": []})
    m = kit.codemap.build("api")
    assert 2 <= len(m["groups"]) <= kit.codemap.MAX_GROUPS


def test_the_map_is_cached_until_the_graph_changes(kit):
    write_graph(kit)
    first = kit.codemap.load("api")
    assert kit.codemap.load("api") == first and (kit.codemap.CACHE_DIR / "api.json").is_file()
    write_graph(kit, graph={"nodes": [node("x", "X", "a/src/main/java/X.java", True)], "links": []})
    import os, time
    os.utime(kit.root / "graph" / "api" / "graph.json", (time.time() + 5, time.time() + 5))
    assert kit.codemap.load("api")["stats"]["files"] == 1


def test_no_graph_no_map(kit):
    assert kit.codemap.load("api") is None
    assert kit.codemap.available() == []
    write_graph(kit)
    assert kit.codemap.available() == ["api"]
