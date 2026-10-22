"""Pipelines as data (R7, R8): lib/pipelines/<name>.yaml lists the nodes of a documentation plan and units.yaml the
unit types they use. A project can extend a kit pipeline in cam-docs/.camarones/pipeline.yaml (`compose`). `expand`
turns a pipeline into concrete units for the project's repos; `validate` reports problems by their YAML path.
Conditions are named and implemented in Python, never an expression language."""
from __future__ import annotations

import copy
import functools
from pathlib import Path

import yaml

from .routing import TIERS

DIR = Path(__file__).resolve().parent.parent / "pipelines"
KIT_PIPELINES = ("full", "quick")
FAN_OUT = ("repos",)
CONDITIONS = ("team-interviews",)
SETTINGS = ("tier", "runner", "allow_local", "isolation", "uses", "approval")
ISOLATION = ("none", "worktree")
OPS = {"disable": (), "needs": ("add", "remove"), "set": SETTINGS}


@functools.lru_cache(maxsize=1)
def types() -> dict[str, dict]:
    return yaml.safe_load((DIR / "units.yaml").read_text(encoding="utf-8"))


def load(name: str) -> dict:
    return yaml.safe_load((DIR / f"{name}.yaml").read_text(encoding="utf-8"))


def kit_types() -> set[str]:
    """Unit types some kit pipeline plans; the rest (flow, review-fixes…) are only added while working."""
    return {n["type"] for name in KIT_PIPELINES for _, n in _flat(load(name))}


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
            "soft": [fill(n) for n in node.get("soft") or []], "repo": repo, "disabled": bool(node.get("disabled")),
            "settings": {k: node[k] for k in SETTINGS if k in node}}


def expand(spec: dict, repos: list[str], predicates: dict[str, bool]) -> list[dict]:
    """Concrete units in pipeline order. Disabled nodes are kept with disabled=True (the plan drops them) and left
    out of `x:*` wildcards."""
    out = []
    for node in spec["nodes"]:
        if not _active(node, predicates):
            continue
        if node.get("for_each"):
            out += [_instance(m, r) for r in repos for m in _members(node) if _active(m, predicates)]
        else:
            out.append(_instance(node, None))
    ids = [n["id"] for n in out if not n["disabled"]]
    for n in out:
        for key in ("needs", "soft"):
            n[key] = [i for need in n[key]
                      for i in ([x for x in ids if x.startswith(need[:-1])] if need.endswith("*") else [need])]
    return out


def _matches(pattern, node_id) -> bool:
    if not isinstance(pattern, str) or not node_id:
        return False
    return pattern == node_id or (pattern.endswith("*") and node_id.startswith(pattern[:-1]))


def compose(override: dict, default: str) -> tuple[dict, list[str]]:
    """A project's pipeline.yaml on top of a kit pipeline: `extends: kit:<name>`, extra `nodes`, and `patch` entries
    (disable · needs add/remove · set tier/runner/allow_local). Returns the merged spec and its problems."""
    base = override.get("extends", f"kit:{default}")
    name = base[4:] if isinstance(base, str) and base.startswith("kit:") else None
    if name not in KIT_PIPELINES:
        return load(default), [f"extends: unknown pipeline '{base}' (use {' or '.join('kit:' + k for k in KIT_PIPELINES)})"]
    spec = copy.deepcopy(load(name))
    errors, flat, base_count = [], [n for _, n in _flat(spec)], len(spec["nodes"])
    for i, p in enumerate(override.get("patch") or []):
        path, op = f"patch[{i}]", (p or {}).get("op")
        if op not in OPS:
            errors.append(f"{path}.op: unknown op '{op}' (use {', '.join(OPS)})")
            continue
        targets = [n for n in flat if _matches(p.get("node"), n.get("id"))]
        extra = sorted(set(p) - {"op", "node", *OPS[op]})
        if not targets:
            errors.append(f"{path}.node: unknown node '{p.get('node')}'")
        elif extra:
            errors.append(f"{path}: '{extra[0]}' does not apply to {op} (use {', '.join(OPS[op]) or 'op and node only'})")
        for n in targets if not extra else []:
            if op == "disable":
                n["disabled"] = True
            elif op == "needs":
                kept = [x for x in n.get("needs") or [] if x not in (p.get("remove") or [])]
                n["needs"] = kept + [x for x in p.get("add") or [] if x not in kept]
                if n.get("soft"):           # an interview removed when it was a hard need: no link at all
                    n["soft"] = [x for x in n["soft"] if x not in (p.get("remove") or []) + n["needs"]]
            else:
                n.update({k: p[k] for k in SETTINGS if k in p})
    spec["nodes"] += override.get("nodes") or []
    spec["name"] = f"{name}+project"
    for e in validate(spec):
        head, _, rest = e.partition("]")
        if head.startswith("nodes[") and head[6:].isdigit():
            k = int(head[6:])
            e = f"nodes[{k - base_count}]{rest}" if k >= base_count else f"kit:{name} nodes[{k}]{rest}"
        errors.append(e)
    return spec, errors


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
        if "tier" in n and n["tier"] not in TIERS:
            errors.append(f"{path}.tier: unknown tier '{n['tier']}' (use {', '.join(TIERS)})")
        if "approval" in n and not isinstance(n["approval"], bool):
            errors.append(f"{path}.approval: must be true or false")
        if "isolation" in n and n["isolation"] not in ISOLATION:
            errors.append(f"{path}.isolation: unknown isolation '{n['isolation']}' (use {', '.join(ISOLATION)})")
        for key in ("needs", "soft"):
            for need in n.get(key) or []:
                if not _target(need, ids):
                    errors.append(f"{path}.{key}: unknown node '{need}'")
        if "uses" in n:
            problem = _uses(str(n["uses"]))
            if problem:
                errors.append(f"{path}.uses: {problem}")
    cycle = _cycle({n["id"]: [t for need in n.get("needs") or [] for t in _target(need, ids)]
                    for _, n in flat if n.get("id")})
    if cycle:
        errors.append(f"nodes: dependency cycle {' → '.join(cycle)}")
    return errors


def _uses(spec: str) -> str | None:
    """`<plugin>@<major>` (or just `<plugin>`): the vendored plugin exists, is active and has that major version."""
    from . import plugins
    name, _, major = spec.partition("@")
    p = next((x for x in plugins.discover() if x.name == name), None)
    if not p:
        return f"no plugin '{name}'"
    if not p.active:
        return f"{name} is {p.status}"
    version = str(p.manifest.get("version", ""))
    if major and version.split(".")[0] != major:
        return f"{name} is {version}, the node needs {major}.x"
    return None


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
