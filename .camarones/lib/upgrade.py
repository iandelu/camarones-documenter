"""Kit upgrades: find a newer Camarones Documenter next to the project (unzipped folder or zip) and install it in place.

Looked up when the wizard opens:
  * <project>/camarones-documenter*/ or camarones-kit*/ (the zip unzipped into its own folder)
  * camarones-documenter*.zip / camarones-kit*.zip in the project folder, its parent folder or ~/Downloads
The project's config (.camarones/workspace.yaml) and caches (.camarones/.cache/) are kept; docs/ is never touched.
"""
from __future__ import annotations

import os, re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

from .common import ROOT, HOME, KIT, CACHE, VERSIONS, IS_WIN

VER_RE = re.compile(r'"kit":\s*"([\d.]+)"')
PATTERNS = ("camarones-documenter*", "camarones-kit*")
STAGE = ROOT / "camarones-documenter-upgrade"


def vtuple(v: str | None) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "0")[:3])


def current() -> str:
    return VERSIONS["kit"]


def _dir_version(d: Path) -> tuple[str | None, Path | None]:
    for kit in (d, *[c for c in d.iterdir() if c.is_dir()]) if d.is_dir() else ():
        f = kit / ".camarones" / "lib" / "common.py"
        if f.exists():
            m = VER_RE.search(f.read_text(encoding="utf-8", errors="replace"))
            return (m.group(1) if m else "0"), kit
    return None, None


def _zip_version(z: Path) -> tuple[str | None, str | None]:
    try:
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                if n.replace("\\", "/").endswith(".camarones/lib/common.py"):
                    m = VER_RE.search(zf.read(n).decode("utf-8", "replace"))
                    return (m.group(1) if m else "0"), n[: -len(".camarones/lib/common.py")]
    except (zipfile.BadZipFile, OSError):
        pass
    return None, None


def candidates() -> list[dict]:
    found: list[dict] = []
    for pat in PATTERNS:
        for d in ROOT.glob(pat):
            if d.is_dir() and d.resolve() != KIT.parent.resolve():
                v, kit = _dir_version(d)
                if v:
                    found.append({"kind": "dir", "path": d, "kit": kit, "version": v})
    for base in dict.fromkeys([ROOT, ROOT.parent, HOME / "Downloads"]):
        if not base.is_dir():
            continue
        for pat in PATTERNS:
            for z in base.glob(pat + ".zip"):
                v, prefix = _zip_version(z)
                if v:
                    found.append({"kind": "zip", "path": z, "prefix": prefix, "version": v})
    return sorted(found, key=lambda c: (vtuple(c["version"]), c["path"].stat().st_mtime), reverse=True)


def newest() -> dict | None:
    c = candidates()
    return c[0] if c and vtuple(c[0]["version"]) > vtuple(current()) else None


def stage(c: dict) -> Path:
    """Put the new kit in <project>/camarones-documenter-upgrade/ (the folder layout install_from_kit_folder expects)."""
    shutil.rmtree(STAGE, ignore_errors=True)
    if c["kind"] == "dir":
        if c["kit"].parent.resolve() == ROOT.resolve():
            return c["kit"]
        shutil.copytree(c["kit"], STAGE)
        return STAGE
    tmp = Path(tempfile.mkdtemp(prefix="camarones-"))
    with zipfile.ZipFile(c["path"]) as zf:
        zf.extractall(tmp)
    src = tmp / c["prefix"] if c["prefix"] else tmp
    shutil.move(str(src), str(STAGE))
    shutil.rmtree(tmp, ignore_errors=True)
    return STAGE


LEGACY = ["docker-compose.yml", "Dockerfile", "nginx.conf", "workspace.yaml", "build"]


def cleanup_legacy(log=print) -> list[str]:
    """Files older kits left in the project root → .camarones/.cache/legacy/ (moved, never deleted)."""
    moved = []
    for name in LEGACY:
        p = ROOT / name
        if not p.exists():
            continue
        if p.is_file():
            txt = p.read_text(encoding="utf-8", errors="replace")
            if name == "workspace.yaml" and (KIT / "workspace.yaml").exists():
                pass                                  # already migrated to .camarones/workspace.yaml
            elif not any(k in txt for k in ("camarones", "docs-portal", "build/site", "docs-kit")):
                continue
        elif not ((p / "site").exists() or (p / "portal").exists()):
            continue
        dst = CACHE / "legacy" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True) if dst.is_dir() else dst.unlink()
        shutil.move(str(p), str(dst))
        moved.append(name)
        log(f"  moved old {name} → .camarones/.cache/legacy/")
    return moved


def relaunch(script: Path) -> None:
    """Start the (new) kit in a fresh process. os.execv breaks paths with spaces on Windows, so use a child there."""
    args = [sys.executable, str(script), *sys.argv[1:]]
    if IS_WIN:
        sys.exit(subprocess.run(args).returncode)
    os.execv(sys.executable, args)
