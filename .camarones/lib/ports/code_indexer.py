"""CodeIndexer: what the app asks of the code indexer (graphify). Where a repo's code graph file is, and an AST-only
build of that graph into cam-docs/graph/<repo>."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class CodeIndexer(Protocol):
    def repo_graph(self, name: str) -> Path: ...

    def graph_repo(self, name: str) -> bool: ...
