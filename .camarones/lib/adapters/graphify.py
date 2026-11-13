"""The CodeIndexer port (lib/ports/code_indexer.py) on graphify: where a repo's code graph lives and the AST-only build
of it into cam-docs/graph/<repo>."""
from __future__ import annotations

from pathlib import Path

from lib.common import GRAPHS, repo_dir, run


def repo_graph(name: str) -> Path:
    own = GRAPHS / name / "graph.json"
    legacy = repo_dir(name) / "graphify-out" / "graph.json"
    return legacy if not own.exists() and legacy.exists() else own


def graph_repo(name: str) -> bool:
    """AST-only graph of one repo, written to cam-docs/graph/<repo> (GRAPHIFY_OUT) instead of the repo."""
    (GRAPHS / name).mkdir(parents=True, exist_ok=True)
    r = run(["graphify", "update", ".", "--force"], cwd=repo_dir(name), check=False, quiet=True,
            env={"GRAPHIFY_OUT": str(GRAPHS / name)})
    return r.returncode == 0
