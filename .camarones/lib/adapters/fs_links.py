"""The FileLinks port (lib/ports/file_links.py) on the file system: symlinks, Windows junctions, a repo's local git
excludes and the merges of the person's own workspace folders with the kit's entries."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from lib.common import CAM_DIR, IS_WIN, ROOT, WORKSPACE, repo_dir, run
from lib.ports import Log

LINKS = (".claude", ".codex", ".agents", ".mcp.json", "AGENTS.md", "CLAUDE.md", ".tours")   # workspace root → cam-docs


def _append_lines(f: Path, lines: list[str]) -> None:
    have = set(f.read_text(encoding="utf-8").splitlines()) if f.exists() else set()
    new = [l for l in lines if l not in have]
    if new:
        with f.open("a", encoding="utf-8") as fh:
            if have and not f.read_text(encoding="utf-8").endswith("\n"):
                fh.write("\n")
            fh.write("\n".join(new) + "\n")


def git_exclude(repo: Path, pattern: str) -> None:
    """Ignore a path in `repo` locally (.git/info/exclude is never committed, so the repo's history stays clean)."""
    if (repo / ".git").is_dir():
        f = repo / ".git" / "info" / "exclude"
        f.parent.mkdir(parents=True, exist_ok=True)
        _append_lines(f, [pattern])


def _linked(p: Path) -> bool:
    """A symlink or a Windows junction (Python < 3.12 cannot tell a junction: it resolves somewhere else)."""
    return _is_link(p) or (p.is_dir() and Path(os.path.realpath(p)) != Path(os.path.realpath(p.parent)) / p.name)


def _unlink(p: Path) -> None:
    try:
        p.unlink()
    except OSError:
        os.rmdir(p)                                 # a Windows junction (the target is never followed)


def link(dst: Path, target: Path, log: Log = print) -> bool:
    """dst → target symlink (relative). An existing real file/dir is never replaced. Windows without symlink
    rights: directories become junctions, files are left alone (the warning says what to do)."""
    if _linked(dst):
        if os.path.realpath(dst) == os.path.realpath(target):
            return True
        _unlink(dst)
    elif dst.exists():
        log(f"⚠ {dst.name} already exists in {dst.parent} — not linked (move it into {CAM_DIR}/ or run migrate)")
        return False
    try:
        dst.symlink_to(os.path.relpath(target, dst.parent), target_is_directory=target.is_dir())
        return True
    except OSError:
        if IS_WIN and target.is_dir():
            return run(["cmd", "/c", "mklink", "/J", str(dst), str(target)], check=False, quiet=True).returncode == 0
        log(f"⚠ could not link {dst} → {target} (enable Developer Mode on Windows)")
        return False


LOCAL_ONLY = {"settings.local.json", ".DS_Store", "Thumbs.db", "desktop.ini"}   # a machine's own, never the kit's
KIT_IMPORT = f"<!-- camarones: the docs kit's rules ({CAM_DIR}/AGENTS.md); uninstall takes these two lines out -->\n@AGENTS.md\n"


def _points_at(p: Path, target: Path) -> bool:
    return _linked(p) and os.path.realpath(p) == os.path.realpath(target)


def _inside(n: str) -> list[tuple[Path, Path]]:
    """(where in the person's own <workspace>/<n>, the kit's entry of cam-docs/<n> it should lead to)."""
    src = ROOT / n
    return [(WORKSPACE / n / c.name, c) for c in sorted(src.iterdir()) if c.name not in LOCAL_ONLY] if src.is_dir() else []


def workspace_off(n: str) -> str | None:
    """Why <workspace>/<n> does not lead agents to cam-docs/<n>: None (linked; or merged: the person's own folder with
    the kit's entries linked in, their own CLAUDE.md importing the linked AGENTS.md), "missing" (link_workspace fixes
    it) or "yours" (a file of theirs is in the way, and the kit never replaces one)."""
    dst, src = WORKSPACE / n, ROOT / n
    if not src.exists() or _points_at(dst, src):
        return None
    if _linked(dst) or not dst.exists():
        return "missing"
    if dst.is_dir() and src.is_dir():
        pairs = _inside(n)
        if all(_points_at(p, c) for p, c in pairs):
            return None
        return "yours" if any((p.exists() or _linked(p)) and not _points_at(p, c) for p, c in pairs) else "missing"
    if n == "CLAUDE.md" and dst.is_file() and _points_at(WORKSPACE / "AGENTS.md", ROOT / "AGENTS.md"):
        return None if "@AGENTS.md" in dst.read_text(encoding="utf-8") else "missing"
    return "yours"


def _raw(f: Path) -> str:
    with open(f, encoding="utf-8", newline="") as fh:
        return fh.read()


def _merge(n: str, log: Log) -> bool:
    """The person's own <workspace>/<n>: the kit's entries linked in one by one, never over one of theirs; a CLAUDE.md
    of theirs gets the lines that import the linked AGENTS.md. True when nothing is off any more."""
    dst = WORKSPACE / n
    if dst.is_dir():
        for p, c in _inside(n):
            if not p.exists() and not _linked(p):
                link(p, c, log)
    elif workspace_off(n) == "missing":
        text = _raw(dst)
        nl = "\r\n" if "\r\n" in text else "\n"                 # theirs: appended in the file's own line endings
        # one line break of separation, so drop_kit_import gives the file back byte for byte
        with open(dst, "a", encoding="utf-8", newline="") as fh:
            fh.write(("" if not text else nl) + KIT_IMPORT.replace("\n", nl))
        log(f"✔ {WORKSPACE.name}/{n} is yours: it now imports the kit's rules (@AGENTS.md)")
    off = workspace_off(n)
    if off == "yours":
        log(f"⚠ {n} in {WORKSPACE.name}/ is yours and in the way — not merged (move it into {CAM_DIR}/ or run migrate)")
    return off is None


def drop_kit_import(claude_md: Path) -> bool:
    """Take out the lines _merge added to the person's CLAUDE.md, and nothing else: the file is as it was."""
    text = _raw(claude_md) if claude_md.is_file() and not _linked(claude_md) else ""
    for nl in ("\r\n", "\n"):
        block = KIT_IMPORT.replace("\n", nl)
        if block in text:
            with open(claude_md, "w", encoding="utf-8", newline="") as fh:
                fh.write(text.replace(nl + block, "", 1) if nl + block in text else text.replace(block, "", 1))
            return True
    return False


def merged_links(names: tuple[str, ...] = LINKS) -> list[Path]:
    """The links the kit put inside the person's own folders at the workspace root."""
    return [p for n in names if (WORKSPACE / n).is_dir() and not _linked(WORKSPACE / n)
            for p in sorted((WORKSPACE / n).iterdir()) if _linked(p) and Path(os.path.realpath(p)).is_relative_to(ROOT.resolve())]


def link_repo_wiki(name: str, log: Log = print) -> None:
    d, wiki = repo_dir(name), ROOT / "wikis" / name
    if (d / "openwiki").is_dir() and not (d / "openwiki").is_symlink() and not wiki.exists():
        wiki.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d / "openwiki"), str(wiki))
    wiki.mkdir(parents=True, exist_ok=True)
    if link(d / "openwiki", wiki, log):
        git_exclude(d, "/openwiki")


def _is_link(p: Path) -> bool:
    return p.is_symlink() or getattr(p, "is_junction", lambda: False)()
