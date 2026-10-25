"""Onboarding: what a folder picked in the desktop app is, before any project exists. `inspect` reads the disk (and
`git remote`/`rev-parse` through docs.detect_repos) and never writes; it must work on any folder, so it takes
everything from its argument and none from this process's project globals."""
from __future__ import annotations

from pathlib import Path

import yaml

from .common import CAM_DIR, find_project_marker
from . import docs, projects

# a file that says "there is code here"; *.csproj is matched by suffix (its name is the project's)
MANIFESTS = ("pom.xml", "build.gradle", "build.gradle.kts", "package.json", "pyproject.toml", "go.mod", "Cargo.toml",
             "pubspec.yaml", "composer.json", "Gemfile")


def kind_of(ws: dict) -> str:
    """`legacy` (document existing code) or `greenfield` (a project that starts from an idea). Absent = `legacy`, so
    every 3.x/4.x project reads as before."""
    return ws["project"].get("kind") or "legacy"


def _read_ws(docs_root: Path) -> dict:
    try:
        ws = yaml.safe_load((docs_root / ".camarones" / "workspace.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        ws = None
    ws = ws if isinstance(ws, dict) else {}
    if not isinstance(ws.get("project"), dict):
        ws["project"] = {}
    return ws


def _project_root(f: Path) -> Path | None:
    """The docs root `f` belongs to: `f` itself, its cam-docs/, a folder above it (f is inside the docs tree or, in the
    3.x layout, a repo in it) or, for a repo, the cam-docs/ next to it. A project further away is not this folder's."""
    m = find_project_marker(f)
    if m is None:
        return None
    if m in (f, f / CAM_DIR) or m in f.parents or ((f / ".git").exists() and m == f.parent / CAM_DIR):
        return m
    return None


def _has_manifest(d: Path) -> bool:
    try:
        return any((d / m).exists() for m in MANIFESTS) or any(d.glob("*.csproj"))
    except OSError:
        return False


def _has_code(f: Path) -> bool:
    """A manifest at the top or one folder down (a monorepo's `src/`, `app/`); deeper is not looked at."""
    try:
        return _has_manifest(f) or any(_has_manifest(d) for d in f.iterdir() if d.is_dir())
    except OSError:
        return False


def inspect(folder: Path) -> dict:
    """What `folder` is, first match wins: project · repo · umbrella · code · empty. Returns `case`, `kind`,
    `workspace` (the folder that holds the repos), `docs_root`, `name` (the workspace folder's), `repos` (docs.detect_repos
    rows), `siblings` (repo case: the other repos next to it) and `warning` (`no-git` for code without a repository)."""
    f, warning, siblings = Path(folder).resolve(), "", []
    root = _project_root(f)
    if root:
        case, kind = "project", kind_of(_read_ws(root))
        workspace = root.parent if root.name == CAM_DIR else root     # 3.x layout: the docs root is the workspace
    elif (f / ".git").exists():
        case, kind, workspace = "repo", "legacy", f.parent
    elif projects.has_repos(f):
        case, kind, workspace = "umbrella", "legacy", f
    elif _has_code(f):
        case, kind, workspace, warning = "code", "legacy", f, "no-git"
    else:
        case, kind, workspace = "empty", "greenfield", f
    repos = docs.detect_repos(workspace) if workspace.is_dir() else []
    if case == "repo":
        siblings = [r for r in repos if r["name"] != f.name]
        repos = [r for r in repos if r["name"] == f.name]
    return {"case": case, "kind": kind, "workspace": str(workspace), "docs_root": str(root or workspace / CAM_DIR),
            "name": workspace.name, "repos": repos, "siblings": siblings, "warning": warning}
