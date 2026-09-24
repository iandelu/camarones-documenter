"""Central registry of cam-docs projects. A global kit install serves many projects; this is how
`camarones` finds, creates and switches between them instead of requiring CAMARONES_ROOT set by hand.
Registry lives at ~/.camarones/projects.json — outside any project, next to the global kit copy."""
from __future__ import annotations

import json, re
from pathlib import Path

from .common import CAM_DIR, HOME, find_project_marker

REGISTRY_DIR = HOME / ".camarones"
REGISTRY_FILE = REGISTRY_DIR / "projects.json"


def find_marker(start: Path) -> Path | None:
    return find_project_marker(start)


def load() -> list[dict]:
    try:
        return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(rows: list[dict]) -> None:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    REGISTRY_FILE.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def register(path: Path, name: str | None = None) -> None:
    """Add/move a project to the top of the registry (also serves as the 'touch' / last-used bump)."""
    path = path.resolve()
    rows = [r for r in load() if Path(r["path"]).resolve() != path]
    rows.insert(0, {"name": name or path.name, "path": str(path)})
    save(rows[:50])


def touch(path: Path) -> None:
    register(path)


def list_registered() -> list[dict]:
    """Registered projects that still exist on disk (stale entries are skipped, never deleted silently)."""
    return [r for r in load() if Path(r["path"]).is_dir()]


def create(name: str, at: Path | None = None) -> Path:
    """Make <at>/<name>/cam-docs/ (a new workspace folder for the repos, with its docs folder) and register it.
    The wizard's first-run flow (env.init_templates) does the actual bootstrap once it's opened."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "project"
    base = at or Path.cwd()
    workspace = base if base.name == slug or has_repos(base) else base / slug
    return adopt(workspace, slug)


def adopt(workspace: Path, name: str | None = None) -> Path:
    """Use `workspace` (a folder with — or for — the repos) as a project: its docs root is workspace/cam-docs."""
    dest = workspace / CAM_DIR
    if (dest / ".camarones" / "workspace.yaml").exists():
        register(dest, name=name)
        return dest
    if dest.exists() and any(dest.iterdir()) and not (dest / ".git").exists():
        raise ValueError(f"{dest} ya existe y no está vacía — elige otra carpeta.")
    dest.mkdir(parents=True, exist_ok=True)
    register(dest, name=name or workspace.name)
    return dest


def has_repos(folder: Path) -> bool:
    """True if `folder` already looks like an umbrella folder full of repos ('drop the kit next to your
    repos' case) — the signal used to offer adopting it as-is instead of nesting a new project inside it."""
    return folder.is_dir() and any((p / ".git").exists() for p in folder.iterdir() if p.is_dir())


def pick(allow_new: bool = True, here: Path | None = None) -> Path | None:
    """Interactive project picker (questionary). Returns None if the user cancelled (Esc/Ctrl-C).
    `here`: offer adopting this folder as-is (e.g. the cwd) when it isn't already a registered project —
    covers running `camarones` straight from an existing repos folder instead of a cama-docs-* one."""
    import questionary
    rows = list_registered()
    choices = [questionary.Choice(f"{r['name']}  ({r['path']})", value=Path(r["path"])) for r in rows]
    offer_here = here is not None and not any(Path(r["path"]).resolve() in (here.resolve(), (here / CAM_DIR).resolve())
                                              for r in rows)
    if offer_here:
        label = f"usar esta carpeta ({here}/{CAM_DIR})" + ("  — repos detectados" if has_repos(here) else "")
        choices.append(questionary.Choice(label, value=here))
    if allow_new:
        choices.append(questionary.Choice("+ nuevo proyecto (<nombre>/cam-docs)", value="__new__"))
    if not choices:
        name = questionary.text("Ningún proyecto registrado todavía. Nombre del proyecto (ej. enjoy):").ask()
        return create(name) if name else None
    picked = questionary.select("🦐 ¿Qué proyecto quieres abrir?", choices=choices).ask()
    if picked is None:
        return None
    if picked == "__new__":
        name = questionary.text("Nombre del nuevo proyecto (ej. enjoy):").ask()
        return create(name) if name else None
    if offer_here and picked == here:
        return adopt(here)
    touch(picked)
    return picked
