"""Central registry of cama-docs-* projects. A global kit install serves many projects; this is how
`camarones` finds, creates and switches between them instead of requiring CAMARONES_ROOT set by hand.
Registry lives at ~/.camarones/projects.json — outside any project, next to the global kit copy."""
from __future__ import annotations

import json, re
from pathlib import Path

from .common import HOME, find_project_marker

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
    """Make an empty cama-docs-<slug>/ folder and register it. The wizard's own first-run flow
    (env.init_templates, called from wizard.py on first open) does the actual bootstrap (git init,
    docs/ templates) once it's opened — this only has to create the folder and remember it."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "project"
    dest = (at or Path.cwd()) / f"cama-docs-{slug}"
    if dest.exists() and any(dest.iterdir()):
        raise ValueError(f"{dest} ya existe y no está vacía — elige otro nombre o carpeta.")
    dest.mkdir(parents=True, exist_ok=True)
    register(dest, name=slug)
    return dest


def pick(allow_new: bool = True) -> Path | None:
    """Interactive project picker (questionary). Returns None if the user cancelled (Esc/Ctrl-C)."""
    import questionary
    rows = list_registered()
    choices = [questionary.Choice(f"{r['name']}  ({r['path']})", value=Path(r["path"])) for r in rows]
    if allow_new:
        choices.append(questionary.Choice("+ nuevo proyecto (cama-docs-<nombre>)", value="__new__"))
    if not choices:
        name = questionary.text("Ningún proyecto registrado todavía. Nombre del proyecto (ej. enjoy):").ask()
        return create(name) if name else None
    picked = questionary.select("🦐 ¿Qué proyecto quieres abrir?", choices=choices).ask()
    if picked is None:
        return None
    if picked == "__new__":
        name = questionary.text("Nombre del nuevo proyecto (ej. enjoy):").ask()
        return create(name) if name else None
    touch(picked)
    return picked
