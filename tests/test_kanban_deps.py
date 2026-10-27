from __future__ import annotations

import random

import pytest


def node(id, status="Backlog", priority=None, touches=(), repos=(), deps=(), archived=False):
    return {"id": id, "status": status, "priority": priority, "touches": list(touches), "repos": list(repos),
            "deps": list(deps), "archived": archived}


def test_norm_touch(kit):
    from lib.kanban.deps import norm_touch
    assert norm_touch(" api:.\\src\\A.java ", fold=False) == "api:src/A.java"
    assert norm_touch("api:./src/A.java", fold=True) == "api:src/a.java"
    assert norm_touch("API:src/A.java", fold=True) == "API:src/a.java"   # only the path is folded
    with pytest.raises(ValueError):
        norm_touch("api:../x", fold=False)
    with pytest.raises(ValueError):
        norm_touch("api:a\\..\\b", fold=False)
    with pytest.raises(ValueError):
        norm_touch("no-repo-part", fold=False)


def test_order_provider_first(kit):
    from lib.kanban.deps import order
    tasks = {"T1": ["api:a.py"], "T2": ["api:b.py"]}
    assert order(tasks, {("api:b.py", "api:a.py")}, {}) == {"T1": [], "T2": ["T1"]}


def test_order_ignores_self_loops_and_sorts_by_id_key(kit):
    from lib.kanban.deps import order
    tasks = {"WI-10": ["api:a.py"], "WI-2": ["api:b.py"], "WI-3": ["api:c.py", "api:d.py"]}
    edges = {("api:c.py", "api:d.py"), ("api:c.py", "api:a.py"), ("api:c.py", "api:b.py")}
    assert order(tasks, edges, {}) == {"WI-10": [], "WI-2": [], "WI-3": ["WI-2", "WI-10"]}


def test_docs_after_code(kit):
    from lib.kanban.deps import order
    tasks = {"T1": ["api:a.py"], "T2": ["cam-docs:docs/x.md"], "T3": ["api:z.py", "cam-docs:docs/y.md"]}
    cites = {"cam-docs:docs/x.md": {"api:a.py"}, "cam-docs:docs/y.md": {"api:a.py"}}
    got = order(tasks, set(), cites)
    assert got["T2"] == ["T1"]
    assert got["T3"] == []          # not a docs-only task: pages it touches add no dependency
    assert got["T1"] == []


def test_sccs_finds_two_way_groups(kit):
    from lib.kanban.deps import sccs
    assert sccs({"A": ["B"], "B": ["A"], "C": []}) == [["A", "B"]]
    assert sccs({"A": ["A"], "B": []}) == []
    chain = {f"WI-{i}": [f"WI-{i + 1}"] for i in range(1, 5000)}
    chain["WI-5000"] = ["WI-1"]
    assert sccs(chain) == [sorted(chain, key=lambda s: int(s[3:]))]       # iterative: no recursion limit
    two = {"WI-9": ["WI-10"], "WI-10": ["WI-9"], "WI-2": ["WI-3"], "WI-3": ["WI-2", "WI-9"]}
    assert sccs(two) == [["WI-2", "WI-3"], ["WI-9", "WI-10"]]


def test_conflict_and_near(kit):
    from lib.kanban.deps import conflicts
    me = node("WI-1", touches=["api:a.py", "api:b.py"])
    shared = node("WI-2", status="In Progress", touches=["api:b.py", "api:z.py"])
    same_group = node("WI-3", touches=["api:c.py"])
    other_group = node("WI-4", touches=["web:q.js"])
    done = node("WI-5", status="Done", touches=["api:a.py"])
    archived = node("WI-6", status="Backlog", touches=["api:a.py"], archived=True)
    groups = {"api:a.py": "g1", "api:b.py": "g1", "api:c.py": "g1", "api:z.py": "g2", "web:q.js": "g3"}
    others = [other_group, same_group, shared, done, archived, me]
    assert conflicts(me, others) == [{"id": "WI-2", "kind": "conflict", "files": ["api:b.py"]}]
    assert conflicts(me, others, groups=groups) == [
        {"id": "WI-2", "kind": "conflict", "files": ["api:b.py"]},
        {"id": "WI-3", "kind": "near", "files": ["api:c.py"]},
    ]


def test_unknown_footprint_is_whole_repo_for_agents(kit):
    from lib.kanban.deps import ALL, footprint, overlap
    unknown = node("WI-1", repos=["api"])
    assert footprint(unknown, agent=True) == {"api:*"}
    assert footprint(unknown, agent=False) == set()
    assert footprint(node("WI-2"), agent=True) == {ALL}
    assert footprint(node("WI-3", touches=["api:a.py"], repos=["web"]), agent=True) == {"api:a.py"}
    assert overlap(footprint(unknown, agent=True), {"api:src/A.java"}) == {"api:src/A.java"}
    assert overlap(footprint(unknown, agent=True), {"web:a.js"}) == set()
    assert overlap(footprint(unknown, agent=False), {"api:src/A.java"}) == set()
    assert overlap({ALL}, {"web:a.js", "api:b.py"}) == {"web:a.js", "api:b.py"}
    assert overlap({"api:a.py"}, {"api:a.py", "api:b.py"}) == {"api:a.py"}
    assert overlap(set(), {ALL}) == set()


GOLDEN = [
    node("WI-2", priority="P0", touches=["api:a.py"]),
    node("WI-3", priority="P2", touches=["api:b.py"], deps=["WI-2"]),
    node("WI-4", priority=None, touches=["api:c.py"], deps=["WI-3"]),
    node("WI-5", priority="P1", touches=["api:a.py"]),
    node("WI-6", priority="P0", touches=["web:x.js"], deps=["WI-5", "WI-99"]),   # WI-99 is outside the set
    node("WI-7", priority="P2", touches=["api:d.py"]),
]


def test_waves_golden(kit):
    from lib.kanban.deps import waves
    # Level 0 by (priority, id): WI-2 -> wave 0; WI-5 shares a.py with WI-2 -> wave 1; WI-7 -> wave 0.
    # Level 1: WI-6 (P0) after WI-5 -> wave 2; WI-3 (P2) after WI-2 -> first fit is wave 1.
    # Level 2: WI-4 after WI-3 (wave 1) -> wave 2 has no clash. Each wave lists by (priority, id).
    expected = [["WI-2", "WI-7"], ["WI-5", "WI-3"], ["WI-6", "WI-4"]]
    assert waves(GOLDEN) == expected
    assert waves(GOLDEN) == expected
    for seed in range(5):
        shuffled = list(GOLDEN)
        random.Random(seed).shuffle(shuffled)
        assert waves(shuffled) == expected


def test_waves_unknown_footprint_is_conservative(kit):
    from lib.kanban.deps import waves
    nodes = [node("WI-1", touches=["api:a.py"]), node("WI-2", repos=["api"]), node("WI-3", touches=["web:b.js"])]
    assert waves(nodes) == [["WI-1", "WI-3"], ["WI-2"]]
    assert waves([node("WI-1"), node("WI-2", touches=["web:b.js"])]) == [["WI-1"], ["WI-2"]]
    assert waves([]) == []


def test_waves_cycle_raises(kit):
    from lib.kanban.deps import CycleError, waves
    nodes = [node("WI-2", deps=["WI-1"]), node("WI-1", deps=["WI-2"]), node("WI-3")]
    with pytest.raises(CycleError) as err:
        waves(nodes)
    assert err.value.cycle == ["WI-1", "WI-2"]
    assert isinstance(err.value, ValueError)


def test_blocked_by_and_ready(kit):
    from lib.kanban.deps import blocked_by, ready
    board = [
        node("WI-1", status="Done", touches=["api:a.py"]),
        node("WI-2", status="Backlog", archived=True, touches=["api:old.py"]),
        node("WI-3", status="In Progress", touches=["api:b.py", "api:c.py"]),
        node("WI-4", status="Ready", priority="P2", touches=["api:a.py"], deps=["WI-1", "WI-2"]),   # deps satisfied
        node("WI-5", status="Ready", priority="P1", touches=["api:b.py"]),                          # clashes with WI-3
        node("WI-6", status="Backlog", priority="P0", touches=["web:x.js"], deps=["WI-3"]),         # dep not Done
        node("WI-7", status="Backlog", priority="P1", touches=["web:x.js"], deps=["WI-404"]),       # unknown dep
        node("WI-8", status="Ready", priority="P0", touches=["web:x.js"]),
        node("WI-9", status="Ready", priority="P3", touches=["web:y.js"]),
        node("WI-10", status="Ready", priority="P3", touches=["api:e.py"]),
        node("WI-11", status="In Review", touches=["api:f.py"]),
    ]
    by = {n["id"]: n for n in board}
    assert blocked_by(by["WI-4"], board, agent=True) == []
    assert blocked_by(by["WI-5"], board, agent=True) == [{"id": "WI-3", "kind": "conflict", "files": ["api:b.py"]}]
    assert blocked_by(by["WI-6"], board, agent=True) == [{"id": "WI-3", "kind": "dependency"}]
    assert blocked_by(by["WI-7"], board, agent=True) == [{"id": "WI-404", "kind": "missing"}]
    # a node with an unknown footprint is blocked by any In Progress item of its repo, for agents only
    wide = node("WI-12", status="Ready", repos=["api"])
    assert blocked_by(wide, board, agent=True) == [{"id": "WI-3", "kind": "conflict", "files": ["api:b.py", "api:c.py"]}]
    assert blocked_by(wide, board, agent=False) == []
    # WI-5, WI-6 and WI-7 are blocked; the rest touch different files, so they share wave 0 and go by priority
    assert ready(board) == ["WI-8", "WI-4", "WI-9", "WI-10"]


def test_ready_orders_by_wave_then_priority_then_id(kit):
    from lib.kanban.deps import ready
    board = [
        node("WI-1", status="Ready", priority="P3", touches=["api:a.py"]),
        node("WI-2", status="Ready", priority="P0", touches=["api:a.py"]),       # clashes with WI-1: later wave
        node("WI-3", status="Backlog", priority="P2", touches=["web:b.js"]),
        node("WI-4", status="Ready", priority=None, touches=["web:c.js"]),
        node("WI-5", status="Ready", priority="P2", touches=["web:d.js"]),
    ]
    # priority order places WI-2 before WI-1 -> WI-2 wave 0, WI-1 wave 1: only wave 0 is handed out
    waiting = []
    assert ready(board, waiting=waiting) == ["WI-2", "WI-3", "WI-5", "WI-4"]
    assert waiting == [{"id": "WI-1", "blocked_by": [{"kind": "wave", "wave": 1}]}]
    assert ready(board, n=2) == ["WI-2", "WI-3"]
    assert ready(board, n=0) == []


def test_ready_never_hands_out_two_tasks_on_the_same_file(kit):
    from lib.kanban.deps import ready
    board = [node("WI-1", touches=["api:a.py"]), node("WI-2", touches=["api:a.py"]),
             node("WI-3", touches=["api:a.py"]), node("WI-4", status="In Progress", touches=["web:x.js"]),
             node("WI-5", touches=["web:x.js"])]
    waiting = []
    assert ready(board, waiting=waiting) == ["WI-1"]
    assert waiting == [{"id": "WI-2", "blocked_by": [{"kind": "wave", "wave": 1}]},
                       {"id": "WI-3", "blocked_by": [{"kind": "wave", "wave": 2}]},
                       {"id": "WI-5", "blocked_by": [{"id": "WI-4", "kind": "conflict", "files": ["web:x.js"]}]}]
    waiting = []
    assert ready(board, among={"WI-2", "WI-3"}, waiting=waiting) == ["WI-2"]     # judged among the scope only
    assert [w["id"] for w in waiting] == ["WI-3"]


def test_ready_people_view_uses_people_footprints(kit):
    from lib.kanban.deps import ready, waves
    board = [node("WI-1", repos=["api"]), node("WI-2", repos=["api"]), node("WI-3", touches=["api:a.py"])]
    assert ready(board) == ["WI-1"]                                    # agents: no files = the whole repo
    assert ready(board, agent=False) == ["WI-1", "WI-2", "WI-3"]       # people: no files = nothing declared
    assert waves(board, agent=False) == [["WI-1", "WI-2", "WI-3"]]
    assert waves(board) == [["WI-1"], ["WI-2"], ["WI-3"]]


def test_a_node_listing_itself_is_never_blocked_by_itself(kit):
    from lib.kanban.deps import blocked_by, ready
    me = node("WI-1", status="Ready", touches=["api:a.py"], deps=["WI-1"])
    assert blocked_by(me, [me], agent=True) == []
    assert ready([me]) == ["WI-1"]


def test_containers_are_the_items_with_children(kit):
    from lib.kanban.deps import containers
    nodes = [node("WI-1"), {**node("WI-2"), "parent": "WI-1"}, {**node("WI-3", archived=True), "parent": "wi-4"},
             node("WI-4"), node("WI-5")]
    assert containers(nodes) == {"WI-1", "WI-4"}          # an archived child still counts; ids compare upper-cased
    assert containers([node("WI-1")]) == set()


def test_containers_never_block_never_wait_for_conflicts_and_are_never_candidates(kit):
    from lib.kanban.deps import blocked_by, ready, waves
    board = [node("WI-1", status="In Progress", touches=["api:a.py"]),                      # a story, running
             {**node("WI-2", status="Ready", touches=["api:a.py"]), "parent": "WI-1"},
             {**node("WI-3", status="Ready", repos=["api"]), "parent": "WI-1"},
             node("WI-4", status="Ready", repos=["api"], deps=["WI-9"]),
             node("WI-9", status="Backlog", touches=["web:z.js"])]
    by = {n["id"]: n for n in board}
    assert blocked_by(by["WI-2"], board, agent=True) == []
    assert blocked_by(by["WI-3"], board, agent=True) == []
    assert blocked_by(by["WI-4"], board, agent=True) == [{"id": "WI-9", "kind": "dependency"}]
    assert blocked_by(by["WI-1"], board, agent=True) == []              # a container touches nothing itself...
    board[0]["deps"] = ["WI-9"]
    assert blocked_by(by["WI-1"], board, agent=True) == [{"id": "WI-9", "kind": "dependency"}]   # ...but waits as any
    assert ready(board) == ["WI-2", "WI-9"]                             # the container is not a candidate
    waiting = []
    ready(board, waiting=waiting)
    assert waiting == [{"id": "WI-3", "blocked_by": [{"kind": "wave", "wave": 1}]},
                       {"id": "WI-4", "blocked_by": [{"id": "WI-9", "kind": "dependency"}]}]
    assert waves(board) == [["WI-2", "WI-9"], ["WI-3"], ["WI-4"]]                  # none holds only the container
