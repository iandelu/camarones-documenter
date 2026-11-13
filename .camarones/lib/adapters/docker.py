"""The ContainerRuntime port (lib/ports/container_runtime.py) on Docker: whether the daemon answers and the build
context an image of the portal is made from."""
from __future__ import annotations

import shutil
from pathlib import Path

from lib.common import CACHE, KIT, run, which


def image_context() -> Path:
    """Self-contained docker build context: Dockerfile + nginx.conf + site/ (used locally and by CI)."""
    site, ctx = CACHE / "site", CACHE / "portal-image"
    if not (site / "index.html").exists():
        raise RuntimeError("the portal is not built yet — build it first (Portal → Build / `portal`)")
    shutil.rmtree(ctx, ignore_errors=True)
    shutil.copytree(site, ctx / "site")
    shutil.copyfile(KIT / "portal" / "Dockerfile", ctx / "Dockerfile")
    shutil.copyfile(KIT / "nginx.conf", ctx / "nginx.conf")
    return ctx


def docker_ready() -> tuple[bool, str]:
    if not which("docker"):
        return False, "docker not found — install Docker Desktop (or use 'Serve without Docker')"
    if run(["docker", "info"], check=False, quiet=True).returncode != 0:
        return False, "Docker is installed but not running — open Docker Desktop and try again (or use 'Serve without Docker')"
    return True, ""
