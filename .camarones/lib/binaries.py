"""Pinned single-binary tools from GitHub releases (gitleaks), installed once per machine under ~/.camarones/bin —
never into cam-docs/ or a service repo. stdlib only, SHA-256 verified. Never raises: None means "not available"."""
from __future__ import annotations

import hashlib, io, platform, tarfile, urllib.request, zipfile
from pathlib import Path
from typing import Callable

from .common import HOME, IS_WIN, VERSIONS, which

BIN_DIR = HOME / ".camarones" / "bin"

RELEASES = {
    "gitleaks": {
        "url": "https://github.com/gitleaks/gitleaks/releases/download/v{v}/gitleaks_{v}_{os}_{arch}.{ext}",
        "sha256": {   # from the release's gitleaks_<v>_checksums.txt — re-pin together with VERSIONS["gitleaks"]
            "darwin_arm64": "b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5",
            "darwin_x64": "dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709",
            "linux_arm64": "e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080",
            "linux_x64": "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
            "windows_arm64": "b95f5e4f5c425cedca7ee203d9afd29597e692c4924a12ed42f970537c72cc0f",
            "windows_x64": "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
        },
    },
}


def _exe(name: str) -> str:
    return name + (".exe" if IS_WIN else "")


def pinned_path(name: str) -> Path:
    return BIN_DIR / f"{name}-{VERSIONS[name]}" / _exe(name)


def bin_path(name: str) -> Path | None:
    """The pinned copy, else one already on PATH."""
    if pinned_path(name).is_file():
        return pinned_path(name)
    found = which(name)
    return Path(found) if found else None


def _target() -> tuple[str, str, str]:
    os_ = {"Windows": "windows", "Darwin": "darwin", "Linux": "linux"}.get(platform.system(), "")
    m = platform.machine().lower()
    arch = "x64" if m in ("x86_64", "amd64") else "arm64" if m in ("arm64", "aarch64") else m
    return os_, arch, "zip" if os_ == "windows" else "tar.gz"


def _member(data: bytes, ext: str, exe: str) -> bytes:
    """Only the named top-level executable is read out of the archive, so no archive path is ever written to disk."""
    if ext == "zip":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return z.read(exe)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as t:
        f = t.extractfile(exe)
        if f is None:
            raise KeyError(exe)
        return f.read()


def ensure(name: str, log: Callable[[str], None] = print) -> Path | None:
    exe = pinned_path(name)
    if exe.is_file():
        return exe
    v, rel = VERSIONS[name], RELEASES[name]
    os_, arch, ext = _target()
    want = rel["sha256"].get(f"{os_}_{arch}")
    if not want:
        log(f"⚠ {name}: no pinned build for {platform.system()} {platform.machine()}")
        return bin_path(name)
    try:
        with urllib.request.urlopen(rel["url"].format(v=v, os=os_, arch=arch, ext=ext), timeout=120) as r:
            data = r.read()
        if hashlib.sha256(data).hexdigest() != want:
            log(f"⚠ {name}: checksum mismatch — not installed")
            return bin_path(name)
        body = _member(data, ext, _exe(name))
        exe.parent.mkdir(parents=True, exist_ok=True)
        tmp = exe.with_name(exe.name + ".part")
        tmp.write_bytes(body)
        tmp.chmod(0o755)
        tmp.replace(exe)
        return exe
    except (OSError, KeyError, tarfile.TarError, zipfile.BadZipFile) as e:
        log(f"⚠ {name}: download failed ({e})")
        return bin_path(name)
