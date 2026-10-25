"""Onboarding: what a folder picked in the desktop app is, before any project exists, and the first-run state the CLI
wizard and the app share (step lists, position in `firstrun.json`, the name step, `start`). `inspect` reads the disk
(and `git remote`/`rev-parse` through docs.detect_repos) and never writes; it must work on any folder, so it takes
everything from its argument and none from this process's project globals. Never imports `wizard` at module level."""
from __future__ import annotations

from pathlib import Path

import yaml

from .common import CAM_DIR, find_project_marker, save_json
from .harness.ctx import Ctx
from . import docs, projects

STEPS = ("name", "repos", "tools", "setup", "stack", "arch", "intro")   # first-run steps, saved by id
LEGACY_STEPS = ("name", "repos", "tools", "setup", "arch", "intro")     # firstrun.json before 3.3 kept only the index
JOIN_STEPS = ("tools", "setup", "intro")   # joining a team's cam-docs: the rest is shared and already decided
GREENFIELD_STEPS = ("name", "repos", "tools", "setup", "intro")   # nothing to read yet: no stack scan, no C4 draft
WS_HEADER = "# Camarón workspace: which repos form this project. Edit freely, then run sync.\n"

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


def _has_repos(f: Path) -> bool:
    try:
        return projects.has_repos(f)
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
    elif _has_repos(f):
        case, kind, workspace = "umbrella", "legacy", f
    elif _has_code(f):
        case, kind, workspace, warning = "code", "legacy", f, "no-git"
    else:
        case, kind, workspace = "empty", "greenfield", f
    try:
        repos = docs.detect_repos(workspace) if workspace.is_dir() else []
    except OSError:                         # unreadable folder: no repos to show, not a crash
        repos = []
    if case == "repo":
        siblings = [r for r in repos if r["name"] != f.name]
        repos = [r for r in repos if r["name"] == f.name]
    return {"case": case, "kind": kind, "workspace": str(workspace), "docs_root": str(root or workspace / CAM_DIR),
            "name": workspace.name, "repos": repos, "siblings": siblings, "warning": warning}


# ---------- first-run state: one implementation for the CLI wizard and the app ----------
def write_workspace(ws_file: Path, ws: dict) -> None:
    ws_file.parent.mkdir(parents=True, exist_ok=True)   # global install: .camarones/ may not exist yet
    ws_file.write_text(WS_HEADER + yaml.safe_dump(ws, sort_keys=False, allow_unicode=True), encoding="utf-8",
                       newline="\n")


def name_project(ws: dict, name: str, fallback: str) -> dict:
    """The name step's whole effect on `ws`: name, id (a slug of it), canonical language and translations defaults."""
    p = ws.setdefault("project", {})
    p["name"] = (name or "").strip() or fallback
    p["id"] = "".join(c if c.isalnum() else "-" for c in p["name"].lower()).strip("-")
    p.setdefault("canonical_language", "en")
    p["translations"] = p.get("translations") or ["es"]
    return ws


def firstrun_file(root: Path) -> Path:
    return Ctx.for_root(root).cache / "firstrun.json"


def steps(mode: str, kind: str) -> tuple[str, ...]:
    """The first-run steps for a mode (`new` | `join`) and a project kind; an unknown kind reads as `legacy`."""
    if mode == "join":
        return JOIN_STEPS
    return GREENFIELD_STEPS if kind == "greenfield" else STEPS


def first_run_mode(state: dict, shared_ready: bool, local_ready: bool) -> str:
    """"done" (straight to the menu), "new" (full first run, or resume one) or "join": plan + workspace.yaml came with
    the team's cam-docs but this machine has no first-run state, so only its tools and repos still need setting up.
    A project that already has both on this machine is an install from before v2.4: nothing to redo."""
    if state.get("done"):
        return "done"
    if state.get("mode") == "join":
        return "join"
    if state or not shared_ready:
        return "new"
    return "done" if local_ready else "join"


def save_position(root: Path, step: str, mode: str) -> None:
    """Where the first run stands, so closing the window or switching between the CLI and the app never loses it."""
    save_json(firstrun_file(root), {"step": STEPS.index(step), "name": step, "done": False,
                                    **({"mode": mode} if mode == "join" else {})})


def finish(root: Path, steps_count: int) -> None:
    save_json(firstrun_file(root), {"step": steps_count, "done": True})


def start(folder: Path, name: str | None = None) -> Path:
    """Make the picked folder a project, ready for the wizard's `repos` step; returns its docs root. Idempotent: on a
    folder that already is a project it only registers it and writes nothing else."""
    f = Path(folder)
    if not f.is_dir():
        raise ValueError(f"not a folder: {f}")
    info = inspect(f)
    root = Path(info["docs_root"])
    if info["case"] == "project":
        projects.register(root, name=(name or "").strip() or _read_ws(root)["project"].get("name") or info["name"])
        return root
    label = (name or "").strip() or info["name"]
    root = projects.adopt(Path(info["workspace"]), label)        # registers it too
    ws = name_project({"project": {}, "repos": info["repos"]}, label, info["name"])
    ws["project"]["kind"] = info["kind"]
    write_workspace(Ctx.for_root(root).ws_file, ws)             # this process's module globals point at another project
    save_position(root, "repos", "new")
    return root
