"""The portal's viewers: the code graphs, the C4 explorer and which of them are stale. The wiki graphs they sit beside
are exported by the wiki (app.wiki.wiki_graph)."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from lib import docs
from lib.app import components, services
from lib.common import CACHE, GRAPHS, out, repo_dir, run, ws_rel
from lib.ports import Log


def graph(rebuild: bool = True, log: Log = print) -> Path | None:
    graphs = []
    for n in docs.repo_names():
        if not repo_dir(n).is_dir():
            continue
        if rebuild or not services.current().code.repo_graph(n).exists():
            services.current().code.graph_repo(n)
        if services.current().code.repo_graph(n).exists():
            graphs.append(str(services.current().code.repo_graph(n)))
    if not graphs:
        log("✔ no code graphs yet")
        return None
    gdir = CACHE / "graph"
    gdir.mkdir(parents=True, exist_ok=True)
    merged = gdir / "graph.json"
    if len(graphs) > 1:
        run(["graphify", "merge-graphs", *graphs, "--out", str(merged)], quiet=True)
    else:
        shutil.copyfile(graphs[0], merged)
    run(["graphify", "export", "html", "--graph", str(merged)], quiet=True, check=False, cwd=gdir,
        env={"GRAPHIFY_OUT": str(gdir)})
    log(f"✔ code graph: {len(graphs)} repo(s) → {ws_rel('.camarones/.cache/graph/graph.html')} (cross-repo edges are INFERRED)")
    return gdir / "graph.html"


VIEWERS = CACHE / "viewers"


def build_c4(dest: Path | None = None, log: Log = print) -> bool:
    dest = dest or VIEWERS / "architecture"
    if not (services.current().diagrams.arch_dir() / "likec4.config.json").exists():
        log("⚠ no C4 model yet (docs/architecture/likec4.config.json) — unit arch-system writes it")
        return False
    log("building the interactive C4 explorer (LikeC4)…")
    shutil.rmtree(dest, ignore_errors=True)
    r = run(["likec4", "build", ".", "-o", str(dest), "--base", "/architecture/", "--title", docs.workspace()["project"]["name"]],
            cwd=services.current().diagrams.arch_dir(), check=False, quiet=True)
    ok = r.returncode == 0 and (dest / "index.html").exists()
    log("✔ C4 explorer" if ok else "⚠ C4 explorer skipped: the model has errors (run arch-validate)")
    return ok


def code_graphs() -> dict[str, Path]:
    """Viewer HTML per repo, plus 'all' for the merged graph."""
    found = {n: GRAPHS / n / "graph.html" for n in docs.repo_names() if (GRAPHS / n / "graph.html").is_file()}
    if (CACHE / "graph" / "graph.html").is_file():
        found = {"all": CACHE / "graph" / "graph.html", **found}
    return found


def build_graphs(log: Log = print) -> bool:
    if "graphify" not in components.components():
        log("⚠ graphify is not installed (setup)")
        return False
    for n in docs.repo_names():
        if repo_dir(n).is_dir():
            log(f"{n}: code graph…")
            if not services.current().code.graph_repo(n):
                log(f"⚠ {n}: graphify failed")
    return graph(rebuild=False, log=log) is not None


def newest(paths) -> float:
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


def repo_changed_at(repo: str) -> float:
    t = out(["git", "log", "-1", "--format=%ct"], cwd=repo_dir(repo))
    return float(t) if t else 0.0


def viewers() -> dict:
    c4_at = newest([VIEWERS / "architecture" / "index.html"])
    model_at = newest(services.current().diagrams.arch_dir().rglob("*.c4")) if services.current().diagrams.arch_dir().is_dir() else 0.0     # fragments in repos/, flows/ too
    graphs = {n: {"at": newest([f]), "stale": n != "all" and repo_changed_at(n) > newest([f])}
              for n, f in code_graphs().items()}
    model = bool(model_at) and any(re.search(r"^\s*model\s*\{", f.read_text(encoding="utf-8", errors="replace"), re.M)
                                   for f in services.current().diagrams.arch_dir().rglob("*.c4"))     # the kit's spec.c4 alone is not a model
    return {"c4": {"exists": bool(c4_at), "at": c4_at, "stale": bool(c4_at) and model_at > c4_at, "model": model},
            "graphs": graphs, "graphify": "graphify" in components.components(), "likec4": "likec4" in components.components()}
