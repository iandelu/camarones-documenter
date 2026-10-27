"""Dependencies, conflicts and waves for the board's items (stories and tasks), as plain data.

What each piece is for: `footprint` and `overlap` say which files two items fight over (an item that declares no
files counts as touching its whole repo, or everything, when an agent asks); `order` turns "file B uses file A" edges
and the pages a docs task cites into task dependencies; `sccs` finds the groups of items that wait on each other;
`conflicts` lists the open items sharing a file (or only a group of files) with one item; `waves` groups items that
can run in parallel without touching the same files; `blocked_by` and `ready` are the start gate.

Pure and deterministic: no file or network I/O, the same input gives the same output, and every list comes back
sorted (ids by `state.id_key`, priorities P0 first and unset last)."""
from __future__ import annotations

from typing import TypedDict

from . import PRIORITIES
from .state import id_key

ALL = "*"                  # a footprint that overlaps everything
_NO_PRIORITY = len(PRIORITIES)


class _Required(TypedDict):
    id: str
    status: str
    priority: str | None
    touches: list[str]     # "<repo>:<posix path>"
    repos: list[str]
    deps: list[str]
    archived: bool


class Node(_Required, total=False):
    parent: str | None     # the item this one belongs to; absent = unknown (callers that do not track it)


def containers(nodes: list[Node]) -> set[str]:
    """Ids of the items that are somebody's parent (open or archived children alike). A container is a grouping: its
    files are those of its children, so it never blocks, waits for a file clash or counts as work to start."""
    ids = {n["id"] for n in nodes}
    return {p for p in ((n.get("parent") or "").strip().upper() for n in nodes) if p in ids}


class CycleError(ValueError):
    def __init__(self, cycle: list[str]):
        super().__init__("dependency cycle: " + " -> ".join(cycle))
        self.cycle = cycle


def norm_touch(ref: str, *, fold: bool) -> str:
    """`repo:path` with `/` separators and no leading `./`; `..` is refused. `fold` lower-cases the path, for keys."""
    repo, sep, path = ref.strip().partition(":")
    repo = repo.strip()
    if not sep or not repo:
        raise ValueError(f"touch needs 'repo:path': {ref!r}")
    path = path.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    if ".." in path.split("/"):
        raise ValueError(f"touch may not leave its repo: {ref!r}")
    return f"{repo}:{path.lower() if fold else path}"


def _repo(touch: str) -> str:
    return touch.partition(":")[0]


def _is_done(node: Node) -> bool:
    return node["status"] == "Done" or bool(node.get("archived"))


def _rank(node: Node) -> int:
    p = node.get("priority")
    return PRIORITIES.index(p) if p in PRIORITIES else _NO_PRIORITY


def _sort_key(node: Node) -> tuple[int, tuple[str, int, str]]:
    return (_rank(node), id_key(node["id"]))


def footprint(node: Node, *, agent: bool) -> set[str]:
    """The files an item touches; an agent treats an item with none as touching its repos (or everything)."""
    touches = set(node["touches"])
    if touches or not agent:
        return touches
    return {f"{r}:*" for r in node["repos"]} or {ALL}


def overlap(a: set[str], b: set[str]) -> set[str]:
    """Entries the two footprints share. `ALL` meets everything; `repo:*` meets every entry of that repo."""
    shared: set[str] = set()
    for x in a:
        for y in b:
            if x == y:
                shared.add(x)
            elif x == ALL:
                shared.add(y)
            elif y == ALL:
                shared.add(x)
            elif _repo(x) == _repo(y):
                if x.endswith(":*"):
                    shared.add(y)
                elif y.endswith(":*"):
                    shared.add(x)
    return shared


def order(tasks: dict[str, list[str]], edges: set[tuple[str, str]], cites: dict[str, set[str]]) -> dict[str, list[str]]:
    """Task dependencies. `edges` are (file, file it uses): the task owning the first depends on the owners of the
    second. A task that only touches `cam-docs:` pages depends on the owners of the code its pages cite."""
    owners: dict[str, set[str]] = {}
    for tid, files in tasks.items():
        for f in files:
            owners.setdefault(f, set()).add(tid)
    deps: dict[str, set[str]] = {tid: set() for tid in tasks}
    for src, dst in edges:
        for b in owners.get(src, ()):
            deps[b] |= owners.get(dst, set())
    for tid, files in tasks.items():
        if files and all(f.startswith("cam-docs:") for f in files):
            for page in files:
                for code in cites.get(page, ()):
                    deps[tid] |= owners.get(code, set())
    return {tid: sorted(d - {tid}, key=id_key) for tid, d in sorted(deps.items(), key=lambda kv: id_key(kv[0]))}


def sccs(graph: dict[str, list[str]]) -> list[list[str]]:
    """Strongly connected components with two or more members (Tarjan, iterative), each sorted, the list sorted."""
    nodes = sorted(set(graph) | {w for ws in graph.values() for w in ws}, key=id_key)
    succ = {v: sorted(set(graph.get(v, ())), key=id_key) for v in nodes}
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    found: list[list[str]] = []
    counter = 0
    for root in nodes:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(succ[root]))]
        while work:
            v, it = work[-1]
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on_stack.add(w)
                    work.append((w, iter(succ[w])))
                    break
                if w in on_stack:
                    low[v] = min(low[v], index[w])
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[v])
                if low[v] == index[v]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        comp.append(w)
                        if w == v:
                            break
                    if len(comp) > 1:
                        found.append(sorted(comp, key=id_key))
    return sorted(found, key=lambda c: id_key(c[0]))


def conflicts(node: Node, others: list[Node], *, groups: dict[str, str] | None = None) -> list[dict]:
    """Open items sharing a file with `node` (`conflict`) or, given `groups` (file -> group), only a group (`near`)."""
    mine = set(node["touches"])
    my_groups = {groups[t] for t in mine if t in groups} if groups else set()
    found = []
    for other in sorted(others, key=lambda o: id_key(o["id"])):
        if other["id"] == node["id"] or _is_done(other):
            continue
        theirs = set(other["touches"])
        shared = overlap(mine, theirs)
        if shared:
            found.append({"id": other["id"], "kind": "conflict", "files": sorted(shared)})
        elif groups:
            close = sorted(t for t in theirs if groups.get(t) in my_groups)
            if close:
                found.append({"id": other["id"], "kind": "near", "files": close})
    return found


def waves(nodes: list[Node], *, agent: bool = True) -> list[list[str]]:
    """Groups of items that can run in parallel. Dependencies among `nodes` give topological levels; level by level,
    each item (by priority, then id) goes into the first wave after every wave holding its dependencies in which no
    item clashes with it, or a new wave. Clashes use `footprint(agent=agent)`: for an agent an item without declared
    files fills its repos; for people it touches nothing. Dependencies outside `nodes` are ignored, and so are
    containers (their children are the work). Raises CycleError."""
    grouping = containers(nodes)
    by_id = {n["id"]: n for n in nodes if n["id"] not in grouping}
    deps = {i: sorted({d for d in n["deps"] if d in by_id and d != i}, key=id_key) for i, n in by_id.items()}
    cycles = sccs(deps)
    if cycles:
        raise CycleError(cycles[0])
    level: dict[str, int] = {}
    pending = dict(deps)
    while pending:                                     # acyclic: every pass settles at least one item
        for i in sorted(pending, key=id_key):
            if all(d in level for d in deps[i]):
                level[i] = 1 + max((level[d] for d in deps[i]), default=-1)
        pending = {i: d for i, d in pending.items() if i not in level}
    placed: list[list[str]] = []
    prints: list[list[set[str]]] = []                  # footprints of the items in each wave
    wave_of: dict[str, int] = {}
    for i in sorted(by_id, key=lambda i: (level[i], *_sort_key(by_id[i]))):
        fp = footprint(by_id[i], agent=agent)
        w = max((wave_of[d] + 1 for d in deps[i]), default=0)
        while w < len(placed) and any(overlap(fp, other) for other in prints[w]):
            w += 1
        if w == len(placed):
            placed.append([])
            prints.append([])
        placed[w].append(i)
        prints[w].append(fp)
        wave_of[i] = w
    return [sorted(w, key=lambda i: _sort_key(by_id[i])) for w in placed]


def blocked_by(node: Node, board: list[Node], *, agent: bool, grouping: set[str] | None = None,
               by_id: dict[str, Node] | None = None) -> list[dict]:
    """Why `node` cannot start now: dependencies not Done (`dependency`, or `missing` when the id is unknown) and In
    Progress items sharing files with it (`conflict`). A container (an item with children) touches nothing itself: it
    is never a conflict and has none, but it still waits for its dependencies. A caller asking for many nodes of the
    same board passes `grouping` (`containers(board)`) and `by_id` (the board by id) once."""
    by_id = {n["id"]: n for n in board} if by_id is None else by_id
    grouping = containers(board) if grouping is None else grouping
    reasons: list[dict] = []
    for d in sorted(set(node["deps"]) - {node["id"]}, key=id_key):      # an item never waits for itself
        dep = by_id.get(d)
        if dep is None:
            reasons.append({"id": d, "kind": "missing"})
        elif not _is_done(dep):
            reasons.append({"id": d, "kind": "dependency"})
    if node["id"] in grouping:
        return reasons
    mine = footprint(node, agent=agent)
    for other in sorted(board, key=lambda o: id_key(o["id"])):
        if (other["id"] == node["id"] or other["id"] in grouping or other["status"] != "In Progress"
                or other.get("archived")):
            continue
        shared = overlap(mine, footprint(other, agent=agent))
        if shared:
            reasons.append({"id": other["id"], "kind": "conflict", "files": sorted(shared)})
    return reasons


def ready(board: list[Node], *, agent: bool = True, among: set[str] | None = None, n: int | None = None,
          waiting: list[dict] | None = None) -> list[str]:
    """Backlog/Ready items that can start now and never collide with each other: the first wave of the items the start
    gate lets through (by priority, then id), at most `n`. Containers (items with children) are never candidates;
    `among` limits the candidates to those ids (the gate still looks at the whole board). When `waiting` is a list,
    every other candidate is appended to it, by id, as `{"id", "blocked_by"}`: the gate's reasons, or
    `[{"kind": "wave", "wave": k}]` for one the gate lets through that clashes with an item handed out first (it fits
    in wave `k`, 0 being the one returned)."""
    grouping = containers(board)
    by_id = {x["id"]: x for x in board}
    free: list[Node] = []
    held: list[dict] = []
    for x in sorted(board, key=lambda o: id_key(o["id"])):
        if (x["status"] not in ("Backlog", "Ready") or x.get("archived") or x["id"] in grouping
                or (among is not None and x["id"] not in among)):
            continue
        why = blocked_by(x, board, agent=agent, grouping=grouping, by_id=by_id)
        if why:
            held.append({"id": x["id"], "blocked_by": why})
        else:
            free.append({**x, "deps": []})      # its dependencies are Done: only file clashes separate the waves
    placed = waves(free, agent=agent)
    held += [{"id": i, "blocked_by": [{"kind": "wave", "wave": k}]} for k, wave in enumerate(placed[1:], 1)
             for i in wave]
    if waiting is not None:
        waiting.extend(sorted(held, key=lambda w: id_key(w["id"])))
    first = placed[0] if placed else []
    return first if n is None else first[:max(n, 0)]
