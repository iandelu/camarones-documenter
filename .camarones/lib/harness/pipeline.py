"""Pipelines as data (R7): lib/pipelines/<name>.yaml lists the nodes of a documentation plan and units.yaml the unit
types they use. `expand` turns a pipeline into concrete units for the project's repos; `validate` reports problems by
their YAML path. Conditions are named and implemented in Python, never an expression language."""
from __future__ import annotations

import functools
from pathlib import Path

import yaml

DIR = Path(__file__).resolve().parent.parent / "pipelines"
FAN_OUT = ("repos",)
CONDITIONS = ("team-interviews",)


@functools.lru_cache(maxsize=1)
def types() -> dict[str, dict]:
    return yaml.safe_load((DIR / "units.yaml").read_text(encoding="utf-8"))


def load(name: str) -> dict:
    return yaml.safe_load((DIR / f"{name}.yaml").read_text(encoding="utf-8"))


def _members(node: dict) -> list[dict]:
    """A fan-out node repeats its `nodes`, or itself when it has none."""
    return node.get("nodes") or [{k: v for k, v in node.items() if k != "for_each"}]


def _active(node: dict, predicates: dict[str, bool]) -> bool:
    if "when" in node and not predicates.get(node["when"], False):
        return False
    return not ("unless" in node and predicates.get(node["unless"], False))


def _instance(node: dict, repo: str | None) -> dict:
    fill = (lambda s: s.replace("{repo}", repo)) if repo else (lambda s: s)
    return {"id": fill(node["id"]), "type": node["type"], "needs": [fill(n) for n in node.get("needs") or []],
            "repo": repo}


def expand(spec: dict, repos: list[str], predicates: dict[str, bool]) -> list[dict]:
    out = []
    for node in spec["nodes"]:
        if not _active(node, predicates):
            continue
        if node.get("for_each"):
            out += [_instance(m, r) for r in repos for m in _members(node) if _active(m, predicates)]
        else:
            out.append(_instance(node, None))
    ids = [n["id"] for n in out]
    for n in out:
        n["needs"] = [i for need in n["needs"]
                      for i in ([x for x in ids if x.startswith(need[:-1])] if need.endswith("*") else [need])]
    return out


def _flat(spec: dict) -> list[tuple[str, dict]]:
    """(YAML path, node) for every node, fan-out members included."""
    out = []
    for i, node in enumerate(spec.get("nodes") or []):
        if node.get("for_each") and "nodes" in node:
            out += [(f"nodes[{i}].nodes[{j}]", m) for j, m in enumerate(node["nodes"])]
        else:
            out.append((f"nodes[{i}]", node))
    return out


def validate(spec: dict) -> list[str]:
    errors, known = [], types()
    for i, node in enumerate(spec.get("nodes") or []):
        if node.get("for_each") and node["for_each"] not in FAN_OUT:
            errors.append(f"nodes[{i}].for_each: can only fan out over {', '.join(repr(f) for f in FAN_OUT)}")
    flat = _flat(spec)
    ids = {n.get("id") for _, n in flat}
    for path, n in flat:
        if not n.get("id") or not n.get("type"):
            errors.append(f"{path}: needs an id and a type")
            continue
        if n["type"] not in known:
            errors.append(f"{path}.type: unknown unit type '{n['type']}'")
        for key in ("when", "unless"):
            if key in n and n[key] not in CONDITIONS:
                errors.append(f"{path}.{key}: unknown condition '{n[key]}'")
        for need in n.get("needs") or []:
            if not _target(need, ids):
                errors.append(f"{path}.needs: unknown node '{need}'")
    cycle = _cycle({n["id"]: [t for need in n.get("needs") or [] for t in _target(need, ids)]
                    for _, n in flat if n.get("id")})
    if cycle:
        errors.append(f"nodes: dependency cycle {' → '.join(cycle)}")
    return errors


def _target(need: str, ids: set) -> list[str]:
    if need.endswith("*"):
        return [i for i in ids if i and i.startswith(need[:-1])]
    return [need] if need in ids else []


def _cycle(graph: dict[str, list[str]]) -> list[str]:
    state: dict[str, int] = {}

    def visit(node: str, path: list[str]) -> list[str]:
        state[node] = 1
        for nxt in graph.get(node, []):
            if state.get(nxt) == 1:
                return path + [node, nxt]
            if not state.get(nxt):
                found = visit(nxt, path + [node])
                if found:
                    return found
        state[node] = 2
        return []
    for n in graph:
        if not state.get(n):
            found = visit(n, [])
            if found:
                return found[found.index(found[-1]):]
    return []
