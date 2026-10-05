"""Code map: graphify's graph (thousands of symbols) folded into what a person can read — a few module/package groups
with the dependencies between them, and per file its main class and the files it uses or is used by. No AI, cached."""
from __future__ import annotations

import json, re
from collections import Counter, defaultdict
from pathlib import PurePosixPath

from .common import CACHE, GRAPHS
from . import docs

CACHE_DIR = CACHE / "codemap"
FORMAT = 3
MIN_GROUPS, MAX_GROUPS, NEIGHBOURS, CORE = 6, 24, 12, 10
OTHER = "(other)"
CODE_EXT = {".java", ".kt", ".kts", ".scala", ".groovy", ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".go", ".cs",
            ".rb", ".php", ".rs", ".swift", ".dart", ".vue", ".svelte"}
DEP_RELATIONS = {"calls", "imports", "imports_from", "references", "inherits", "implements", "indirect_call"}
SOURCE_ROOTS = {"main", "java", "kotlin", "scala", "groovy", "python", "typescript", "javascript", "app", "lib"}
TEST_PART = {"test", "tests", "__tests__", "spec", "specs", "testfixtures", "it"}
TEST_NAME = re.compile(r"(Test|Tests|IT|Spec)\.\w+$|[._-](test|spec)\.\w+$|^test_", re.I)


def is_test(path: PurePosixPath) -> bool:
    return any(p.lower() in TEST_PART for p in path.parts[:-1]) or bool(TEST_NAME.search(path.name))


def split(path: PurePosixPath) -> tuple[str, list[str]]:
    """(module, package parts): `svc-core/src/main/java/a/b/X.java` → ("svc-core", ["a", "b"])."""
    parts = list(path.parts[:-1])
    if "src" in parts:
        i = parts.index("src")
        module, rest = "/".join(parts[:i]), parts[i + 1:]
        while rest and rest[0] in SOURCE_ROOTS:
            rest = rest[1:]
        return module, rest
    return "", parts


def graph_file(repo: str):
    return GRAPHS / repo / "graph.json"


def available() -> list[str]:
    return [n for n in docs.repo_names() if graph_file(n).is_file()]


def build(repo: str) -> dict:
    g = json.loads(graph_file(repo).read_text(encoding="utf-8"))
    by_file: dict[str, list[dict]] = defaultdict(list)
    for n in g.get("nodes", []):
        sf = n.get("source_file") or ""
        p = PurePosixPath(sf)
        if sf and p.suffix in CODE_EXT and not is_test(p):
            by_file[sf].append(n)
    paths = sorted(by_file)
    owner = {n["id"]: f for f, ns in by_file.items() for n in ns}

    def label(f: str) -> str:
        stem = PurePosixPath(f).stem
        classes = [n["label"] for n in by_file[f] if n.get("_callable_class")]
        return stem if stem in classes else (classes[0] if classes else stem)

    split_of = {f: split(PurePosixPath(f)) for f in paths}
    common_of: dict[str, int] = {}               # per module: a scripts/ folder must not cancel src's com/acme prefix
    for module in {m for m, _ in split_of.values()}:
        pkgs = [pk for m, pk in split_of.values() if m == module]
        c = 0
        while all(len(pk) > c + 1 for pk in pkgs) and len({pk[c] for pk in pkgs}) == 1:
            c += 1
        common_of[module] = c
    split_of = {f: (m, pk[common_of[m]:]) for f, (m, pk) in split_of.items()}
    pkgs = [pk for _, pk in split_of.values()]
    common = 0

    modules = sorted({m for m, _ in split_of.values() if m})
    shared = ""
    if len(modules) > 1:                       # casino-lobby-services-core, …-logic → core, logic
        shared = modules[0][:len(next(iter(sorted(modules, key=len))))]
        for m in modules:
            while not m.startswith(shared):
                shared = shared[:-1]
        shared = shared[:max(shared.rfind("-"), shared.rfind("/")) + 1]

    def key(f: str, depth: int) -> str:
        module, pk = split_of[f]
        module = module[len(shared):] if shared and module.startswith(shared) else module
        return "/".join([module] if module else []) + ("/" if module and pk[common:common + depth] else "") \
            + "/".join(pk[common:common + depth]) or module or PurePosixPath(f).parent.name or "."

    deepest = max((len(pk) - common for pk in pkgs), default=0)
    depth = 0
    while depth < deepest and len({key(f, depth) for f in paths}) < MIN_GROUPS:
        depth += 1
    sizes = Counter(key(f, depth) for f in paths)
    kept = {lab for lab, _ in sizes.most_common(MAX_GROUPS - 1)} if len(sizes) > MAX_GROUPS else set(sizes)
    group_of = {f: key(f, depth) if key(f, depth) in kept else OTHER for f in paths}
    group_labels = sorted(set(group_of.values()), key=lambda lab: (lab == OTHER, lab))
    gid = {lab: i for i, lab in enumerate(group_labels)}
    fid = {f: i for i, f in enumerate(paths)}

    edges: Counter = Counter()
    for link in g.get("links", []):
        a, b = owner.get(link.get("source")), owner.get(link.get("target"))
        if a and b and a != b and link.get("relation") in DEP_RELATIONS:
            edges[(fid[a], fid[b])] += 1
    out_e, in_e = defaultdict(list), defaultdict(list)
    for (a, b), w in edges.items():
        out_e[a].append([b, w])
        in_e[b].append([a, w])
    files = []
    for f in paths:
        i = fid[f]
        top = lambda xs: sorted(xs, key=lambda x: (-x[1], paths[x[0]]))[:NEIGHBOURS]
        sub = "/".join(split_of[f][1][common + depth:]) if group_of[f] != OTHER else ""
        files.append({"label": label(f), "path": f, "group": gid[group_of[f]], "sub": sub, "out": top(out_e[i]), "in": top(in_e[i]),
                      "deg": [sum(w for _, w in in_e[i]), sum(w for _, w in out_e[i])]})
    glinks: Counter = Counter()
    for (a, b), w in edges.items():
        ga, gb = files[a]["group"], files[b]["group"]
        if ga != gb:
            glinks[(ga, gb)] += w
    groups = [{"id": i, "label": lab, "files": sum(1 for f in files if f["group"] == i)} for i, lab in enumerate(group_labels)]
    core = sorted(range(len(files)), key=lambda i: (-files[i]["deg"][0], -sum(files[i]["deg"]), files[i]["label"]))
    return {"repo": repo, "format": FORMAT,
            "stats": {"files": len(files), "groups": len(groups), "commit": g.get("built_at_commit", "")},
            "groups": groups, "links": [{"s": a, "t": b, "w": w} for (a, b), w in sorted(glinks.items())],
            "files": files, "core": [i for i in core if files[i]["deg"][0]][:CORE]}


def load(repo: str) -> dict | None:
    """The map of one repo, rebuilt only when graphify's graph changed."""
    src = graph_file(repo)
    if not src.is_file():
        return None
    st = src.stat()
    stamp = f"{FORMAT}:{st.st_mtime_ns}:{st.st_size}"
    cached = CACHE_DIR / f"{repo}.json"
    if cached.is_file():
        try:
            data = json.loads(cached.read_text(encoding="utf-8"))
            if data.get("stamp") == stamp:
                return data["map"]
        except (OSError, ValueError, KeyError):
            pass
    m = build(repo)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps({"stamp": stamp, "map": m}, ensure_ascii=False), encoding="utf-8")
    return m
