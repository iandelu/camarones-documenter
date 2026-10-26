"""Saving a story with its subtasks in one locked pass, listing stories and loading one back (`lib/stories_save.py`)."""
from __future__ import annotations

import subprocess

import pytest

SRC = "src/main/java/demo/"
ORDERS, PAY, WEB = (f"api:{SRC}{n}.java" for n in ("Orders", "Pay", "Web"))
PAGE = "cam-docs:docs/flows/checkout.md"
K1, K2 = "change:api:orders", "change:api:pay"
CLAUSES = {"as_": "responsable de pedidos", "want": "cobrar los pedidos con tarjeta", "so": "no perder ventas"}
CRITERION = "Dado un pedido, cuando pago, entonces veo el recibo"


@pytest.fixture
def world(kit):
    """A board, real files in the `api` repo and a doc page; returns (kit, ops, stories_save, stories)."""
    subprocess.run(["git", "init", "-q", str(kit.root)], check=True)
    from lib.kanban import ops
    ops.init(log=lambda _: None)
    for name in ("Orders", "Pay", "Web"):
        (kit.ws / "api" / SRC / f"{name}.java").write_text(f"class {name} {{}}\n", encoding="utf-8")
    (kit.root / "docs" / "flows").mkdir(parents=True, exist_ok=True)
    (kit.root / "docs" / "flows" / "checkout.md").write_text("---\ntitle: Checkout\n---\n# Checkout\n", encoding="utf-8")
    from lib import stories, stories_save
    return kit, ops, stories_save, stories


def story(**kw):
    base = {"id": None, **CLAUSES, "criteria": [CRITERION], "touches": [ORDERS, PAY], "epic": None, "priority": None}
    return {**base, **kw}


def task(key, title, touches, deps=(), criteria=()):
    return {"key": key, "kind": "change", "title": title, "group": key.rpartition(":")[2], "touches": list(touches),
            "criteria": list(criteria), "deps": list(deps), "conflicts": [], "wave": 0, "edited": True, "added": [],
            "dropped": []}


def two_tasks():
    return [task(K1, "Orders: cobrar", [ORDERS], criteria=["Tests for #1 written first"]),
            task(K2, "Pay: cobrar", [PAY], deps=[K1])]


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / "backlog").rglob("*") if p.is_file()}


def read(kit, item_id):
    from lib.kanban.items import parse_item
    f = next((kit.root / "backlog" / "tasks").glob(f"{item_id.lower()} - *.md"))
    return parse_item(f.read_text(encoding="utf-8"), f)


def save(world, s, tasks=(), **kw):
    kw.setdefault("title", None)
    kw.setdefault("base_sha", None)
    kw.setdefault("lang", "es")
    return world[2].save(s, tasks=list(tasks), **kw)


def test_save_new_story_and_tasks(world):
    kit = world[0]
    out = save(world, story(touches=[ORDERS, PAY, PAGE]), two_tasks())
    sid, t1, t2 = out["story"]["id"], out["tasks"][0]["id"], out["tasks"][1]["id"]
    assert (sid, t1, t2) == ("WI-1", "WI-2", "WI-3")
    assert out["story"]["title"] == "Cobrar los pedidos con tarjeta"
    s = read(kit, sid)
    assert s.fm["type"] == "story" and s.fm["subtasks"] == [t1, t2]
    assert s.fm["x-touches"] == sorted([ORDERS, PAY, PAGE])
    assert s.body.lstrip().startswith("## Description")
    assert "Como responsable de pedidos,\nquiero cobrar los pedidos con tarjeta,\npara no perder ventas." in s.body
    assert f"- [ ] #1 {CRITERION}" in s.body
    a, b = read(kit, t1), read(kit, t2)
    assert a.fm["type"] == "task" and a.fm["parent_task_id"] == sid and a.fm["x-touches"] == [ORDERS]
    assert b.fm["dependencies"] == [t1] and b.fm["x-touches"] == [PAY] and b.fm["parent_task_id"] == sid
    assert "- [ ] #1 Tests for #1 written first" in a.body
    assert out["tasks"][1]["dependencies"] == [t1]
    cards = kit.root / "backlog" / "board.yaml"
    from lib.kanban.state import load_board
    order = load_board(cards.read_text(encoding="utf-8"))
    assert [i for i, _ in sorted(order.items(), key=lambda kv: kv[1]["ordinal"])] == [sid, t1, t2]


def test_save_writes_a_dependent_task_after_what_it_needs(world):
    tasks = list(reversed(two_tasks()))
    out = save(world, story(), tasks)
    assert [r["title"] for r in out["tasks"]] == ["Pay: cobrar", "Orders: cobrar"]      # the caller's order
    ids = {r["title"]: r["id"] for r in out["tasks"]}
    assert ids["Orders: cobrar"] < ids["Pay: cobrar"]                                  # written first
    assert out["tasks"][0]["dependencies"] == [ids["Orders: cobrar"]]


def test_save_keeps_dependencies_on_existing_items(world):
    ops = world[1]
    other = ops.add("task", "Prerequisite")
    tasks = [task(K1, "Orders: cobrar", [ORDERS], deps=[other["id"].lower()])]
    out = save(world, story(), tasks)
    assert out["tasks"][0]["dependencies"] == [other["id"]]


def test_save_existing_story_keeps_title_criteria_and_notes(world):
    kit, ops, mod, _ = world
    row = ops.add("story", "Mi título a mano", touches=[ORDERS],
                  description="Como a,\nquiero b,\npara c.\n\nLínea 1\nLínea 2", criteria=["Viejo criterio"])
    sid = row["id"]
    loaded = mod.item(sid)
    assert (loaded["as_"], loaded["want"], loaded["so"]) == ("a", "b", "c")
    assert loaded["rest"] == "Línea 1\nLínea 2" and loaded["criteria"] == ["Viejo criterio"]
    out = save(world, story(id=sid, criteria=["Viejo criterio", CRITERION]), two_tasks(), base_sha=loaded["sha"])
    assert out["story"]["title"] == "Mi título a mano"
    s = read(kit, sid)
    assert s.fm["subtasks"] == [r["id"] for r in out["tasks"]]
    assert s.fm["x-touches"] == sorted([ORDERS, PAY])
    from lib.kanban.items import checklist, description
    assert description(s.body) == ("Como responsable de pedidos,\nquiero cobrar los pedidos con tarjeta,\n"
                                   "para no perder ventas.\n\nLínea 1\nLínea 2")
    assert [(c["n"], c["text"]) for c in checklist(s.body, "AC")] == [(1, "Viejo criterio"), (2, CRITERION)]
    again = mod.item(sid)
    assert again["as_"] == "responsable de pedidos" and again["rest"] == "Línea 1\nLínea 2"
    assert [r["id"] for r in again["subtasks"]] == [r["id"] for r in out["tasks"]]


def test_save_existing_story_can_retitle_and_does_not_repeat_criteria(world):
    kit, ops, mod, _ = world
    sid = ops.add("story", "Antes", description="Como a,\nquiero b,\npara c.", criteria=[CRITERION])["id"]
    sha = mod.item(sid)["sha"]
    out = save(world, story(id=sid), title="  Después  ", base_sha=sha)
    assert out["story"]["title"] == "Después" and out["tasks"] == []
    from lib.kanban.items import checklist
    assert [c["n"] for c in checklist(read(kit, sid).body, "AC")] == [1]


def test_save_story_without_clauses_puts_them_above_old_text(world):
    kit, ops, mod, _ = world
    sid = ops.add("story", "Nota suelta", description="Algo que alguien escribió sin plantilla")["id"]
    loaded = mod.item(sid)
    assert loaded["want"] == "" and loaded["rest"] == "Algo que alguien escribió sin plantilla"
    save(world, story(id=sid), base_sha=loaded["sha"])
    from lib.kanban.items import description
    assert description(read(kit, sid).body) == (
        "Como responsable de pedidos,\nquiero cobrar los pedidos con tarjeta,\npara no perder ventas.\n\n"
        "Algo que alguien escribió sin plantilla")


def test_save_without_notes_leaves_no_trailing_blank_line(world):
    kit = world[0]
    sid = save(world, story())["story"]["id"]
    assert "para no perder ventas.\n<!-- SECTION:DESCRIPTION:END -->" in read(kit, sid).body


def test_concurrent_change_is_a_conflict(world):
    kit, ops, mod, _ = world
    sid = ops.add("story", "Historia", description="Como a,\nquiero b,\npara c.")["id"]
    old = mod.item(sid)["sha"]
    ops.update_item(sid, description="Como otra persona,\nquiero otra cosa,\npara otro fin.")
    before = tree(kit.root)
    with pytest.raises(mod.StoryConflict) as e:
        save(world, story(id=sid), two_tasks(), base_sha=old)
    assert str(e.value) == f"{sid} changed while you were editing it: reload it"
    assert isinstance(e.value, ops.BoardError)
    assert tree(kit.root) == before
    # the same clauses as the ones on disk are not a conflict, whatever the base
    same = {"as_": "otra persona", "want": "otra cosa", "so": "otro fin"}
    save(world, story(id=sid, **same), base_sha=old)
    # a story that is being saved as an existing one needs a base
    with pytest.raises(mod.StoryConflict):
        save(world, story(id=sid), base_sha=None)


def test_invalid_task_writes_nothing(world):
    kit, _, mod, _ = world
    before = tree(kit.root)
    bad = [task(K1, "Orders: cobrar", [ORDERS]), task(K2, "   ", [PAY])]
    with pytest.raises(mod.BoardError):
        save(world, story(), bad)
    assert tree(kit.root) == before
    for tasks in ([task(K1, "Igual", [ORDERS]), task(K2, "igual", [PAY])],         # titles are unique
                  [task(K1, "x" * 121, [ORDERS])],                                 # at most 120 characters
                  [task(K1, "Uno", [ORDERS]), task(K1, "Dos", [PAY])]):           # one task per key
        with pytest.raises(mod.BoardError):
            save(world, story(), tasks)
    assert tree(kit.root) == before


def test_invalid_story_writes_nothing(world):
    kit, ops, mod, _ = world
    task_ = ops.add("task", "A task")["id"]
    before = tree(kit.root)
    for bad in (story(want=""), story(as_="  "), story(so=""), story(epic="WI-99"), story(epic=task_),
                story(priority="P9"), story(touches=[f"nope:{SRC}Orders.java"]), story(touches=["api"])):
        with pytest.raises(mod.BoardError):
            save(world, bad, two_tasks())
    with pytest.raises(mod.BoardError):
        save(world, story(id="WI-99"))
    with pytest.raises(mod.BoardError):
        save(world, story(id=task_))                                                # not a story
    with pytest.raises(mod.BoardError):
        save(world, story(), two_tasks(), docs=["NOPE-0000"])
    with pytest.raises(mod.BoardError):
        save(world, story(), title="   ")
    assert tree(kit.root) == before


def test_epic_must_be_an_epic(world):
    kit, ops, mod, _ = world
    epic = ops.add("epic", "Pagos")["id"]
    sid = save(world, story(epic=epic.lower()))["story"]["id"]
    assert read(kit, sid).fm["parent_task_id"] == epic
    other = ops.add("epic", "Otra")["id"]
    with pytest.raises(mod.BoardError):
        save(world, story(id=sid, epic=other), base_sha=mod.item(sid)["sha"])        # not moved here
    save(world, story(id=sid, epic=epic), base_sha=mod.item(sid)["sha"])
    assert mod.item(sid)["epic"] == epic


def test_dependency_problems_write_nothing(world):
    kit, _, mod, _ = world
    before = tree(kit.root)
    cases = {
        "cycle": [task(K1, "Uno", [ORDERS], deps=[K2]), task(K2, "Dos", [PAY], deps=[K1])],
        "self": [task(K1, "Uno", [ORDERS], deps=[K1])],
        "key not being saved": [task(K1, "Uno", [ORDERS], deps=["docs:cam-docs:docs/x.md"])],
        "unknown item": [task(K1, "Uno", [ORDERS], deps=["WI-77"])],
    }
    for name, tasks in cases.items():
        with pytest.raises(mod.BoardError):
            save(world, story(), tasks)
        assert tree(kit.root) == before, name


def test_new_file_touch_needs_existing_folder(world):
    kit, _, mod, _ = world
    before = tree(kit.root)
    with pytest.raises(mod.BoardError):
        save(world, story(touches=["api:src/new/File.java"]), [task(K1, "Uno", ["api:src/new/File.java"])])
    assert tree(kit.root) == before
    (kit.ws / "api" / "src" / "new").mkdir()
    out = save(world, story(touches=["api:src/new/File.java"]), [task(K1, "Uno", ["api:src/new/File.java"])])
    assert out["tasks"][0]["touches"] == ["api:src/new/File.java"]
    assert not (kit.ws / "api" / "src" / "new" / "File.java").exists()              # nothing is created in the repo


def test_touches_must_be_files_inside_their_repo(world):
    kit, _, mod, _ = world
    (kit.ws / "api" / "src" / "main").mkdir(parents=True, exist_ok=True)
    before = tree(kit.root)
    for bad in ("api:src/main", "api:src/main/", "api:../web/package.json", "api:/etc/passwd", "api:C:/x.txt",
                "api:", f"api:{SRC}"):                                                   # folders and escapes
        with pytest.raises(mod.BoardError):
            save(world, story(touches=[bad]))
        with pytest.raises(mod.BoardError):
            save(world, story(), [task(K1, "Uno", [bad])])
    assert tree(kit.root) == before


def test_a_group_label_is_not_a_touch(world):
    kit, _, mod, _ = world
    from lib.kanban import index
    from test_codemap import node, write_graph
    write_graph(kit, graph={"built_at_commit": "abc",
                            "nodes": [node("o", "Orders", f"{SRC}Orders.java", True)], "links": []})
    label = index.groups(index.connect(), [ORDERS])[ORDERS]
    assert label
    with pytest.raises(mod.BoardError):
        save(world, story(touches=[f"api:{label}"]))


def test_save_a_page_touch_and_link_docs(world):
    kit = world[0]
    out = save(world, story(touches=[ORDERS, PAGE]), [task("docs:" + PAGE, "Update Checkout", [PAGE])],
               docs=["flows/checkout.md"])
    s = read(kit, out["story"]["id"])
    assert PAGE in s.fm["x-touches"] and s.fm["documentation"] and out["tasks"][0]["touches"] == [PAGE]
    assert out["tasks"][0]["repos"] == []                                            # the docs repo is not a code repo


def test_list_stories_progress_and_conflicts(world):
    kit, ops, mod, _ = world
    first = save(world, story(touches=[ORDERS, PAY]), two_tasks())
    sid = first["story"]["id"]
    ops.move(first["tasks"][0]["id"], "Done")
    clash = ops.add("story", "Otra", touches=[PAY, WEB], description="Como a,\nquiero b,\npara c.")["id"]
    apart = ops.add("story", "Aparte", touches=[WEB.replace("Web", "Other")], description="Como a,\nquiero b,\npara c.")["id"]
    done = ops.add("story", "Hecha", touches=[ORDERS], description="Como a,\nquiero b,\npara c.")["id"]
    ops.move(done, "Done")
    ops.add("epic", "No es historia", )
    rows = {r["id"]: r for r in mod.list_stories()}
    assert set(rows) == {sid, clash, apart, done}
    assert set(rows[sid]) == {"id", "title", "verdict", "progress", "conflicts"}
    assert rows[sid]["title"] == "Cobrar los pedidos con tarjeta"
    assert rows[sid]["progress"] == {"done": 1, "total": 2}
    assert rows[clash]["progress"] == {"done": 0, "total": 0}
    assert rows[sid]["conflicts"] == [clash] and rows[clash]["conflicts"] == [sid]
    assert rows[apart]["conflicts"] == [] and rows[done]["conflicts"] == []         # Done stories do not clash
    assert rows[sid]["verdict"] in ("good", "improve", "poor")
    assert rows[clash]["verdict"] == "poor" or rows[clash]["verdict"] == "improve"
    ops.archive(done)
    assert done not in {r["id"] for r in mod.list_stories()}


def test_list_stories_without_stories(world):
    assert world[2].list_stories() == []


def test_item_returns_what_the_screen_needs(world):
    kit, ops, mod, _ = world
    epic = ops.add("epic", "Pagos")["id"]
    out = save(world, story(epic=epic, priority="P1", touches=[ORDERS, PAY]), two_tasks(), docs=["flows/checkout.md"])
    sid = out["story"]["id"]
    got = mod.item(sid.lower())
    assert set(got) == {"id", "title", "as_", "want", "so", "rest", "criteria", "touches", "epic", "priority", "docs",
                        "subtasks", "sha"}
    assert got["id"] == sid and got["epic"] == epic and got["priority"] == "P1" and got["rest"] == ""
    assert (got["as_"], got["want"], got["so"]) == tuple(CLAUSES.values())
    assert got["criteria"] == [CRITERION] and got["touches"] == sorted([ORDERS, PAY]) and len(got["docs"]) == 1
    assert [(r["id"], r["wave"]) for r in got["subtasks"]] == [(out["tasks"][0]["id"], 0), (out["tasks"][1]["id"], 1)]
    assert got["subtasks"][1]["dependencies"] == [out["tasks"][0]["id"]]
    from lib import stories
    assert got["sha"] == stories.fingerprint(*CLAUSES.values())
    with pytest.raises(mod.BoardError):
        mod.item("WI-99")
    with pytest.raises(mod.BoardError):
        mod.item(out["tasks"][0]["id"])                                              # a task, not a story
