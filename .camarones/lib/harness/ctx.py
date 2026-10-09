"""Where a project lives: docs root, workspace and state folders, as a value instead of import-time globals, so one
process can address several trees (a unit's worktree, an A/B control) while plan state stays in the main cam-docs."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]          # .camarones/
CAM_DIR = "cam-docs"      # per-workspace folder (its own git repo) holding docs + agent config, next to the repos


def find_project_marker(start: Path) -> Path | None:
    """Walk up from `start` (like git does for .git/) looking for a project's .camarones/workspace.yaml, either
    directly or inside a sibling cam-docs/ folder (the workspace root that holds all repos). Lets one central kit
    (global install) serve many projects without CAMARONES_ROOT set by hand."""
    cur = start.resolve()
    for d in (cur, *cur.parents):
        # cam-docs first: a workspace folder that holds a cam-docs project is never a project of its own
        if (d / CAM_DIR / ".camarones" / "workspace.yaml").exists():
            return d / CAM_DIR
        if (d / ".camarones" / "workspace.yaml").exists():
            return d
    return None


def docs_root(path: Path) -> Path:
    """A registered/requested project path → its docs root: the workspace folder of a cam-docs project means
    its cam-docs/ (otherwise opening the workspace folder would bootstrap a second, legacy project there)."""
    path = path.resolve()
    return path / CAM_DIR if (path / CAM_DIR / ".camarones" / "workspace.yaml").exists() else path


def find_root() -> Path:
    """The docs root = <workspace>/cam-docs (legacy: the umbrella folder itself), overridable with CAMARONES_ROOT.
    Resolution order: CAMARONES_ROOT env var > a workspace.yaml found walking up from the cwd > KIT.parent
    (legacy: the kit copy lives inside the project it documents)."""
    env = os.environ.get("CAMARONES_ROOT")
    if env:
        return docs_root(Path(env))
    marker = find_project_marker(Path.cwd())
    return marker if marker else KIT.parent


@dataclass(frozen=True)
class Ctx:
    root: Path            # the docs tree being read and written (main cam-docs, or a unit's worktree)
    state_root: Path      # where plan, handoffs and run logs live; the main cam-docs even when root is a worktree

    @classmethod
    def for_root(cls, root: Path, state_root: Path | None = None) -> "Ctx":
        r = docs_root(Path(root))
        return cls(r, docs_root(Path(state_root)) if state_root else r)

    @classmethod
    def from_env(cls) -> "Ctx":
        return cls.for_root(find_root(), os.environ.get("CAMARONES_STATE_ROOT") or None)

    @property
    def cam_layout(self) -> bool:
        return self.root.name == CAM_DIR       # repos are root's siblings, not its children

    @property
    def workspace(self) -> Path:
        return self.root.parent if self.cam_layout else self.root

    @property
    def docs(self) -> Path:
        return self.root / "docs"

    @property
    def work(self) -> Path:
        return self.state_root / "docs" / ".work"

    @property
    def ws_file(self) -> Path:
        return self.root / ".camarones" / "workspace.yaml"

    @property
    def cache(self) -> Path:
        return self.root / ".camarones" / ".cache"

    @property
    def graphs(self) -> Path:
        return self.root / "graph"

    @property
    def runs(self) -> Path:
        return self.state_root / ".camarones" / ".cache" / "runs"
