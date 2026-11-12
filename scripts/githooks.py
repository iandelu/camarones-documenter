"""Installs this repo's git hooks (.githooks/) into the hooks folder git runs for every worktree of the clone.

  uv run scripts/githooks.py     once per clone, and again after a hook in .githooks/ changes

commit-msg drops AI co-author trailers; pre-push refuses commits that still carry one.
"""
from __future__ import annotations

import shutil, subprocess, sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / ".githooks"


def hooks_dir(cwd: Path) -> Path:
    out = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=cwd, check=True, capture_output=True,
                         text=True, encoding="utf-8").stdout.strip()
    return (cwd / out).resolve()


def install(cwd: Path) -> list[Path]:
    target = hooks_dir(cwd)
    target.mkdir(parents=True, exist_ok=True)
    done = []
    for hook in sorted(p for p in SOURCE.iterdir() if p.is_file()):
        dest = target / hook.name
        shutil.copyfile(hook, dest)
        dest.chmod(0o755)
        done.append(dest)
    return done


def main() -> int:
    for path in install(Path.cwd()):
        print(f"installed {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
