"""Apple's /usr/bin/git is a shim: each call asks xcrun where the developer tools are, then runs their git. That lookup
costs about 60 ms, and a run of the suite starts some ten thousand git processes. The suite puts that same git first on
PATH instead, through a mirror of its prefix: git finds its helpers and templates next to the path it was started from,
so a plain link to the binary would lose them, while <mirror>/bin/git with links to the prefix's other folders keeps
them. The kit itself runs whatever git the machine has; this changes only the test processes."""
from __future__ import annotations

import atexit, os, shutil, subprocess, sys, tempfile
from pathlib import Path

IS_MAC = sys.platform == "darwin"
SHIM = Path("/usr/bin/git")


def real_git() -> Path | None:
    """The git the shim would run, when the first git on PATH is the shim."""
    found = shutil.which("git")
    if not IS_MAC or not found or Path(found).resolve() != SHIM:
        return None
    r = subprocess.run(["xcrun", "--find", "git"], capture_output=True, text=True)
    real = Path(r.stdout.strip()) if r.returncode == 0 else None
    return real if real and real.is_file() else None


def mirror(git: Path, base: Path) -> Path:
    """<base>/bin/git → `git`, and <base>/<folder> → each other folder of git's prefix. Returns <base>/bin."""
    prefix = git.parent.parent
    (base / "bin").mkdir(parents=True)
    (base / "bin" / "git").symlink_to(git)
    for entry in prefix.iterdir():
        if entry.name != "bin":
            (base / entry.name).symlink_to(entry)
    return base / "bin"


def install(base: Path | None = None) -> None:
    """Puts the mirror first on this process's PATH, which the xdist workers and every child process inherit."""
    git = real_git()
    if git is None:
        return
    if base is None:
        base = Path(tempfile.mkdtemp(prefix="camaron-git-")) / "git"
        atexit.register(shutil.rmtree, base.parent, True)
    os.environ["PATH"] = os.pathsep.join([str(mirror(git, base)), os.environ.get("PATH", "")])
