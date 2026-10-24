"""Kit dev: the bench of a checkout of this kit, from the desktop app — the sandbox (scripts/sandbox.py), pytest, the
portal's npm test / build, the desktop helpers' tests and the check that app-build matches its source. Only in a kit
checkout (tests/ and scripts/sandbox.py next to .camarones/), only these commands, built as argument lists."""
from __future__ import annotations

import os, shlex
from pathlib import Path

from .common import KIT, uv, which

REPO = KIT.parent
INTERACTIVE = {"wizard", "app", "arch", "up", "mcp", "switch", "new", "join"}   # these need a terminal or a window


def available() -> bool:
    """A checkout someone develops the kit in: its tests and sandbox script are there, and it is not the global install
    (also a full clone, but the global launcher sets CAMARONES_GLOBAL — see upgrade.central_repo)."""
    return (not os.environ.get("CAMARONES_GLOBAL") and (REPO / "tests").is_dir()
            and (REPO / "scripts" / "sandbox.py").is_file())


def info() -> dict:
    sandbox = Path(os.environ.get("CAMARONES_SANDBOX") or Path.home() / "projects" / "camarones-sandbox")
    return {"available": available(), "repo": str(REPO), "sandbox": str(sandbox), "sandbox_exists": sandbox.is_dir(),
            "has_node_modules": (REPO / ".camarones" / "portal" / "app" / "node_modules").is_dir()}


def _tool(name: str) -> str:
    exe = which(name)
    if not exe:
        raise ValueError(f"{name} is not on PATH")
    return exe


def _test_path(p: str) -> str:
    f = (REPO / str(p)).resolve()
    if (REPO / "tests").resolve() not in (f, *f.parents) or not f.exists():
        raise ValueError(f"{p}: a file or folder under tests/")
    return f.relative_to(REPO.resolve()).as_posix()


def command(task: str, b: dict) -> tuple[list[str], Path]:
    if not available():
        raise PermissionError("Kit dev is only for a checkout of the kit")
    sandbox = [uv(), "run", "--quiet", str(REPO / "scripts" / "sandbox.py")]
    app = REPO / ".camarones" / "portal" / "app"
    if task in ("sandbox-reset", "sandbox-traces"):
        return sandbox + [task.split("-", 1)[1]], REPO
    if task == "sandbox-cli":
        from .catalog import COMMANDS
        args = shlex.split(str(b.get("line") or ""), posix=True)
        if not args or args[0] not in COMMANDS or args[0] in INTERACTIVE:
            raise ValueError("a kit command for the sandbox (the interactive ones: open the wizard instead)")
        return sandbox + ["cli", *args], REPO
    if task == "pytest":
        k = str(b.get("k") or "").strip()
        if k.startswith("-"):
            raise ValueError("-k: an expression, not an option")
        paths = [_test_path(p) for p in b.get("paths") or []]
        return [uv(), "run", "pytest", "-q", *(["-k", k] if k else []), *paths], REPO
    if task in ("portal-ci", "portal-test", "portal-build"):
        return [_tool("npm"), *{"portal-ci": ["ci"], "portal-test": ["test"], "portal-build": ["run", "build"]}[task]], app
    if task == "desktop-test":
        return [_tool("node"), "--test"], REPO / ".camarones" / "desktop"
    if task == "build-diff":
        return [_tool("git"), "status", "--porcelain", "--", ".camarones/portal/app-build"], REPO
    raise ValueError(f"unknown task {task}")


def open_wizard() -> bool:
    """`sandbox.py open`: the wizard is interactive, so it gets its own terminal window."""
    from . import env
    if not available():
        raise PermissionError("Kit dev is only for a checkout of the kit")
    return env.open_new_terminal([uv(), "run", "--quiet", str(REPO / "scripts" / "sandbox.py"), "open"], REPO)
