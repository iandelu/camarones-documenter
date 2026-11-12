"""Import graph of the kit's own modules, read with `ast` so imports inside functions count."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

ROOT_PACKAGE = "lib"


def modules(kit_dir: Path) -> dict[str, Path]:
    lib = kit_dir / "lib"
    found: dict[str, Path] = {}
    for path in sorted(lib.rglob("*.py")):
        parts = list(path.relative_to(lib).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        if parts:
            found[".".join(parts)] = path
    found["camarones"] = kit_dir / "camarones.py"
    return found


def _strip_root(dotted: str) -> str:
    if dotted == ROOT_PACKAGE:
        return ""
    prefix = ROOT_PACKAGE + "."
    return dotted[len(prefix):] if dotted.startswith(prefix) else dotted


def _from_target(importer: str, is_package: bool, node: ast.ImportFrom) -> str:
    mod = node.module or ""
    if node.level == 0:
        return _strip_root(mod)
    parts = importer.split(".") if importer else []
    package = parts if is_package else parts[:-1]
    base = package[: len(package) - (node.level - 1)]
    return ".".join(base + ([mod] if mod else []))


def edges(mods: dict[str, Path]) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for name, path in mods.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        resolved: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.level or _is_kit(node.module)):
                target = _from_target(name, path.name == "__init__.py", node)
                for alias in node.names:
                    sub = f"{target}.{alias.name}" if target else alias.name
                    resolved.add(sub if sub in mods else target)
            elif isinstance(node, ast.Import):
                resolved.update(_strip_root(a.name) for a in node.names if _is_kit(a.name))
        found.update((name, t) for t in resolved if t in mods and t != name)
    return found


def _is_kit(dotted: str | None) -> bool:
    return dotted == ROOT_PACKAGE or (dotted or "").startswith(ROOT_PACKAGE + ".")


def largest_cycle(nodes: Iterable[str], edges: set[tuple[str, str]]) -> int:
    graph: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in sorted(edges):
        if a in graph and b in graph:
            graph[a].append(b)
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    best = 0
    counter = 0
    for root in graph:
        if root in index:
            continue
        work = [(root, iter(graph[root]))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, children = work[-1]
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter
                    counter += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(graph[child])))
                    break
                if child in on_stack:
                    low[node] = min(low[node], index[child])
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    size = 0
                    while True:
                        member = stack.pop()
                        on_stack.discard(member)
                        size += 1
                        if member == node:
                            break
                    best = max(best, size if size > 1 else 0)
    return best


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())
