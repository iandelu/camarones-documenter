"""Stories: the INVEST verdict by rules, the template-based split into subtasks and `analyze` (what the wizard shows on
every keystroke). Deterministic: the code graph, the board's index and templates, no model call."""
from __future__ import annotations

import json
import subprocess

import pytest

from test_codemap import node, write_graph

P = "src/main/java/demo/shop/"
ORDER = f"api:{P}orders/OrderService.java"
REPO = f"api:{P}orders/OrderRepository.java"
PAY = f"api:{P}payments/PaymentClient.java"
WEB = f"api:{P}web/OrderResource.java"
PAGE = "cam-docs:docs/flows/checkout.md"
K_ORDERS, K_PAY, K_WEB, K_DOCS = "change:api:orders", "change:api:payments", "change:api:web", f"docs:{PAGE}"


def graph(*links):
    return {"built_at_commit": "abc1234",
            "nodes": [node("order", "OrderService", P + "orders/OrderService.java", True),
                      node("repo", "OrderRepository", P + "orders/OrderRepository.java", True),
                      node("pay", "PaymentClient", P + "payments/PaymentClient.java", True),
                      node("web", "OrderResource", P + "web/OrderResource.java", True)],
            "links": [{"source": s, "target": t, "relation": "calls"} for s, t in links]}


ONE_WAY = graph(("web", "order"), ("order", "repo"), ("order", "pay"))


@pytest.fixture
def world(kit):
    """A board, a graph of `api` with the groups orders, payments and web, and a page citing orders and web."""
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)
    from lib.kanban import ops
    ops.init(log=lambda _: None)
    write_graph(kit, graph=ONE_WAY)
    (kit.root / "docs" / "flows").mkdir(parents=True, exist_ok=True)
    (kit.root / "docs" / "flows" / "checkout.md").write_text(
        f"---\ntitle: Checkout\nx-sources:\n  - {ORDER}#place\n  - {WEB}\n---\n# Checkout\n", encoding="utf-8")
    from lib import stories
    from lib.kanban import index
    return kit, ops, index, stories


def story(**kw):
    base = {"id": None, "as_": "responsable de pedidos", "want": "cobrar los pedidos con tarjeta",
            "so": "no perder ventas", "criteria": ["Dado un pedido, cuando pago, entonces veo el recibo"],
            "touches": [ORDER, PAY], "epic": None, "priority": None}
    return {**base, **kw}


def bnode(i, touches=(), *, status="Backlog", deps=(), parent=None, archived=False, priority=None):
    return {"id": i, "status": status, "priority": priority, "touches": list(touches), "repos": ["api"],
            "deps": list(deps), "archived": archived, "parent": parent}


GROUPS = {ORDER: "orders", REPO: "orders", PAY: "payments", WEB: "web", PAGE: "docs"}


def split(world, s, lang="es"):
    kit, ops, index, stories = world
    conn = index.connect()
    try:
        return stories.split(s, conn, lang=lang)
    finally:
        conn.close()


# ── INVEST ───────────────────────────────────────────────────────────────────────────────────────────────────────

def letters(world, s, board=(), lang="es"):
    return world[3].invest(s, list(board), groups=GROUPS, lang=lang)["letters"]


def test_invest_each_letter(world):
    good = letters(world, story())
    assert all(v["ok"] for v in good.values()), good
    assert set(good) == set("INVEST") and all(v["reason"] for v in good.values())

    # I: another open story shares a file; a Done one or one on other files does not count
    lt = letters(world, story(), [bnode("WI-2", [PAY]), bnode("WI-3", [ORDER], status="Done"), bnode("WI-4", [WEB])])
    assert lt["I"]["ok"] is False and lt["I"]["data"]["overlaps"] == [{"id": "WI-2", "files": [PAY]}]
    # I: it waits for an undone story
    board = [bnode("WI-1", [ORDER, PAY], deps=["WI-5"]), bnode("WI-5", [WEB])]
    lt = letters(world, story(id="WI-1"), board)
    assert lt["I"]["ok"] is False and lt["I"]["data"]["waits"] == ["WI-5"]
    board[1]["status"] = "Done"
    assert letters(world, story(id="WI-1"), board)["I"]["ok"] is True       # itself is not an overlap

    assert letters(world, story(want="ver un botón para cobrar los pedidos"))["N"]["ok"] is False
    assert letters(world, story(so=""))["V"]["ok"] is False
    assert letters(world, story(want="cobrar los pedidos", so="cobrar los pedidos"))["V"]["ok"] is False
    assert letters(world, story(touches=[]))["E"]["ok"] is False
    assert letters(world, story(criteria=[]))["E"]["ok"] is False

    lt = letters(world, story(criteria=["El sistema es rápido"]))
    assert lt["T"]["ok"] is False
    assert letters(world, story(criteria=["Exporta el PDF de la página"]))["T"]["ok"] is True   # observable verb
    assert letters(world, story(criteria=[]))["T"]["ok"] is False
    en = letters(world, story(as_="order owner", want="charge orders by card", so="sales are not lost",
                              criteria=["The owner sees the receipt"]), lang="en")
    assert en["T"]["ok"] is True and en["T"]["reason"] != good["T"]["reason"]
    assert letters(world, story(criteria=["Given an order, when I pay, then the receipt is sent"]), lang="en")["T"]["ok"]


def test_invest_small_counts_and_split_by_group(world):
    kit = world[0]
    s = letters(world, story(touches=[ORDER, REPO, PAY, PAGE]))["S"]
    assert s["ok"] is True and s["data"] == {"groups": 2, "files": 3, "repos": 1}
    ws = kit.docs.workspace()
    ws["stories"] = {"small": {"groups": 1}}
    kit.docs.save_workspace(ws)
    s = letters(world, story(touches=[ORDER, REPO, PAY, PAGE]))["S"]
    assert s["ok"] is False
    assert s["data"]["split_by_group"] == [[REPO, ORDER], [PAY]]
    assert s["data"]["files"] == 3


def test_verdict_boundaries(world):
    inv = world[3].invest
    assert inv(story(), [], groups=GROUPS, lang="es")["verdict"] == "good"
    assert inv(story(as_=""), [], groups=GROUPS, lang="es")["verdict"] == "poor"            # `empty`
    one = inv(story(criteria=["El sistema es rápido"]), [], groups=GROUPS, lang="es")
    assert [k for k, v in one["letters"].items() if not v["ok"]] == ["T"] and one["verdict"] == "improve"
    three = inv(story(want="ver un botón para cobrar pedidos", so="cobrar pedidos", criteria=["El sistema es rápido"]), [],
                groups=GROUPS, lang="es")
    assert sum(not v["ok"] for v in three["letters"].values()) == 3 and three["verdict"] == "poor"


# ── split ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_split_one_task_per_group_plus_docs(world):
    tasks = {t["key"]: t for t in split(world, story())}
    assert set(tasks) == {K_ORDERS, K_PAY, K_DOCS}
    o, p, d = tasks[K_ORDERS], tasks[K_PAY], tasks[K_DOCS]
    assert (o["kind"], o["group"], o["touches"]) == ("change", "orders", [ORDER])
    assert o["title"] == "orders: cobrar los pedidos con tarjeta"
    assert o["criteria"] == ["Tests de #1 escritos primero"]
    assert o["deps"] == [K_PAY] and p["deps"] == []                    # OrderService calls PaymentClient
    assert (d["kind"], d["group"], d["touches"], d["title"]) == ("docs", "docs", [PAGE], "Actualizar Checkout")
    assert d["deps"] == [K_ORDERS]
    assert all(t["edited"] is False and t["conflicts"] == [] for t in tasks.values())
    assert [t["key"] for t in split(world, story())] == [K_PAY, K_ORDERS, K_DOCS]          # by wave
    en = {t["key"]: t for t in split(world, story(criteria=["a", "b"]), lang="en")}
    assert en[K_DOCS]["title"] == "Update Checkout" and en[K_PAY]["criteria"] == ["Tests for #1, #2 written first"]


def test_split_merges_two_way_groups(world):
    write_graph(world[0], graph=graph(("order", "pay"), ("pay", "order")))
    tasks = [t for t in split(world, story()) if t["kind"] == "change"]
    assert len(tasks) == 1
    t = tasks[0]
    assert t["key"] == "change:api:orders+payments" and t["touches"] == [ORDER, PAY]
    assert "orders" in t["title"] and "payments" in t["title"] and t["deps"] == []


def test_split_orders_provider_first_and_docs_last(world):
    tasks = split(world, story(touches=[WEB, ORDER]))
    by = {t["key"]: t for t in tasks}
    assert by[K_WEB]["deps"] == [K_ORDERS]
    assert sorted(by[K_DOCS]["deps"]) == sorted([K_ORDERS, K_WEB])
    assert (by[K_ORDERS]["wave"], by[K_WEB]["wave"], by[K_DOCS]["wave"]) == (0, 1, 2)
    assert [t["key"] for t in tasks] == [K_ORDERS, K_WEB, K_DOCS]


def test_split_titles_are_cut_at_120_on_a_word(world):
    t = next(t for t in split(world, story(want="cobrar " + "pedidos muy largos " * 12)) if t["key"] == K_PAY)
    assert len(t["title"]) <= 120 and not t["title"].endswith(" ")
    assert ("payments: cobrar " + "pedidos muy largos " * 12).startswith(t["title"])


def test_split_conflicts_with_open_board_items(world):
    kit, ops, index, stories = world
    other = ops.add("task", "Pay refunds", touches=[PAY])["id"]
    ops.move(ops.add("task", "Old", touches=[ORDER])["id"], "Done")
    epic = ops.add("story", "Another story", touches=[ORDER])["id"]
    child = ops.add("task", "Repository", parent=epic, touches=[REPO])["id"]
    tasks = {t["key"]: t for t in split(world, story())}
    assert tasks[K_PAY]["conflicts"] == [{"id": other, "kind": "conflict", "files": [PAY]}]
    assert tasks[K_ORDERS]["conflicts"] == [{"id": child, "kind": "near", "files": [REPO]}]   # containers left out
    assert other not in tasks[K_PAY]["deps"]                         # only In Progress becomes a dependency


def test_in_progress_conflict_becomes_dependency(world):
    kit, ops, index, stories = world
    other = ops.add("task", "Pay refunds", touches=[PAY])["id"]
    ops.move(other, "In Progress")
    tasks = {t["key"]: t for t in split(world, story())}
    assert tasks[K_PAY]["deps"] == [other]
    assert tasks[K_PAY]["conflicts"] == [{"id": other, "kind": "conflict", "files": [PAY]}]
    assert (tasks[K_PAY]["wave"], tasks[K_ORDERS]["wave"], tasks[K_DOCS]["wave"]) == (0, 1, 2)


def test_project_template_override(world):
    kit = world[0]
    f = kit.root / ".camarones" / "board" / "split.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"change_title": "[{group}] {want}"}), encoding="utf-8")
    tasks = {t["key"]: t for t in split(world, story())}
    assert tasks[K_ORDERS]["title"] == "[orders] cobrar los pedidos con tarjeta"
    assert tasks[K_DOCS]["title"] == "Actualizar Checkout"            # the kit's template for the other keys
    assert tasks[K_ORDERS]["criteria"] == ["Tests de #1 escritos primero"]


# ── analyze ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_analyze_returns_everything_the_wizard_shows(world):
    kit, ops, index, stories = world
    other = ops.add("story", "Refunds", touches=[PAY])["id"]
    out = stories.analyze(story(), None, lang="es")
    assert set(out) == {"hints", "invest", "tasks", "waves", "conflicts", "cycle", "graphless"}
    assert out["hints"] == [] and out["cycle"] == [] and out["graphless"] == []
    assert out["conflicts"] == [{"id": other, "kind": "conflict", "files": [PAY]}]
    assert out["invest"]["letters"]["I"]["ok"] is False and out["invest"]["verdict"] == "improve"
    assert out["waves"] == [[K_PAY], [K_ORDERS], [K_DOCS]]
    assert [t["key"] for t in out["tasks"]] == [K_PAY, K_ORDERS, K_DOCS]


def test_analyze_with_edited_tasks_recomputes_and_flags_outside(world):
    kit, ops, index, stories = world
    tasks = [t for t in stories.analyze(story(), None, lang="es")["tasks"] if t["kind"] == "change"]
    for t in tasks:
        t["deps"] = []                                                 # stale: recomputed from the files
    pay = next(t for t in tasks if t["key"] == K_PAY)
    pay.update(touches=[PAY, REPO], edited=True, title="Pagos")
    out = stories.analyze(story(), tasks, lang="es")
    by = {t["key"]: t for t in out["tasks"]}
    assert set(by) == {K_ORDERS, K_PAY}                                # no split: the person's list
    assert by[K_PAY]["outside"] == [REPO] and by[K_PAY]["title"] == "Pagos"
    assert "outside" not in by[K_ORDERS]
    assert by[K_ORDERS]["deps"] == [K_PAY]                             # OrderService uses both of its files
    assert out["waves"] == [[K_PAY], [K_ORDERS]] and out["cycle"] == []


def test_analyze_reports_a_hand_made_cycle(world):
    kit, ops, index, stories = world
    tasks = [t for t in stories.analyze(story(), None, lang="es")["tasks"] if t["kind"] == "change"]
    pay = next(t for t in tasks if t["key"] == K_PAY)
    pay.update(touches=[PAY, WEB], edited=True)                        # web uses orders, orders uses payments
    out = stories.analyze(story(), tasks, lang="es")
    assert out["cycle"] == [K_ORDERS, K_PAY] and out["waves"] == []
    assert {t["key"] for t in out["tasks"]} == {K_ORDERS, K_PAY}


def test_analyze_without_graph_lists_graphless_repo(world):
    kit, ops, index, stories = world
    out = stories.analyze(story(touches=[ORDER, "web:src/app/main.js"]), None, lang="es")
    assert out["graphless"] == ["web"]
    by = {t["key"]: t for t in out["tasks"]}
    assert by["change:web:app"]["touches"] == ["web:src/app/main.js"]   # its folder is its group


def test_deterministic(world):
    kit, ops, index, stories = world
    ops.add("task", "Pay refunds", touches=[PAY])
    s = story(touches=[WEB, ORDER, PAY])
    assert stories.analyze(s, None, lang="es") == stories.analyze(s, None, lang="es")
    assert stories.analyze(s, None, lang="en") == stories.analyze(s, None, lang="en")
