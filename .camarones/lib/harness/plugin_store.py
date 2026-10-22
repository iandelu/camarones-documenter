"""Team plugins, vendored and pinned (R37, H25). `add` copies a plugin from a folder or a git tag into
cam-docs/.camarones/plugins/<name>/ and records it in .camarones/plugins.lock (version, source, folder fingerprint);
`update` re-fetches it explicitly and says what changed; `outdated` lists newer versions; `remove` drops it. No
registry, no download at run time: teammates get the same files through git. A code plugin whose files change is asked
about again by trust (R28), because its fingerprint no longer matches the approval."""
from __future__ import annotations

import re, shutil, tempfile
from pathlib import Path

import yaml

from ..common import CTX, run
from . import plugins

LOCK = CTX.root / ".camarones" / "plugins.lock"
HEADER = "# Written by `camaron plugins add|update|remove`: the team plugins vendored in .camarones/plugins/.\n"
GIT = re.compile(r"git:(?P<url>.+?)@(?P<ref>[^@#]+)(?:#(?P<sub>.+))?$")


class PluginError(RuntimeError):
    """A plugin cannot be added, updated or removed; nothing was written."""


def load_lock() -> dict:
    if not LOCK.is_file():
        return {}
    data = yaml.safe_load(LOCK.read_text(encoding="utf-8")) or {}
    return dict(data.get("plugins") or {})


def save_lock(entries: dict) -> None:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(HEADER + yaml.safe_dump({"plugins": dict(sorted(entries.items()))}, sort_keys=False),
                    encoding="utf-8", newline="\n")


def _fetch(source: str, into: Path) -> tuple[Path, str]:
    """The plugin folder for `source`, and the source as it goes in the lock."""
    m = GIT.match(source)
    if m:
        dest = into / "repo"
        r = run(["git", "clone", "-q", "--depth", "1", "--branch", m["ref"], m["url"], str(dest)], check=False, quiet=True)
        if r.returncode != 0:
            why = ((r.stderr or "").strip().splitlines() or ["git clone failed"])[-1]
            raise PluginError(f"cannot fetch {m['url']} at {m['ref']}: {why}")
        folder = dest / m["sub"] if m["sub"] else dest
        return folder, source
    path = Path(source.removeprefix("path:")).expanduser()
    if not path.is_dir():
        raise PluginError(f"no plugin folder at {source} (use a folder, or git:<url>@<tag>[#subfolder])")
    return path.resolve(), f"path:{path.resolve().as_posix()}"


def _read(folder: Path) -> plugins.Plugin:
    if not (folder / "plugin.yaml").is_file():
        raise PluginError(f"{folder.name}: no plugin.yaml")
    p = plugins._load(folder, "project", {k.name for k in plugins.kit()})
    if p.errors:
        raise PluginError("; ".join(p.errors))
    return p


def _files(folder: Path) -> dict[str, bytes]:
    return {f.relative_to(folder).as_posix(): f.read_bytes() for f in sorted(folder.rglob("*"))
            if f.is_file() and ".git" not in f.relative_to(folder).parts and "__pycache__" not in f.parts}


def _vendor(src: plugins.Plugin) -> Path:
    dest = plugins.PROJECT_DIR / src.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src.path, dest, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return dest


def _entry(dest: Path, source: str) -> tuple[plugins.Plugin, dict]:
    p = plugins._load(dest, "project", {k.name for k in plugins.kit()})
    return p, {"version": str(p.manifest.get("version")), "source": source, "sha256": p.fingerprint()}


def add(source: str) -> plugins.Plugin:
    entries = load_lock()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        folder, locked = _fetch(source, Path(tmp))
        src = _read(folder)
        if src.name in entries or (plugins.PROJECT_DIR / src.name).exists():
            raise PluginError(f"{src.name} is already vendored: use `camaron plugins update {src.name}`")
        p, entries[src.name] = _entry(_vendor(src), locked)
    save_lock(entries)
    return p


def update(name: str | None = None, to: str | None = None) -> list[dict]:
    """Re-fetch locked plugins (all, or `name`; `to` moves a git source to another tag). Returns what changed."""
    entries, changes = load_lock(), []
    names = [name] if name else sorted(entries)
    for n in names:
        if n not in entries:
            raise PluginError(f"{n} is not in plugins.lock: add it with `camaron plugins add <source>`")
        source = entries[n]["source"]
        if to:
            m = GIT.match(source)
            if not m:
                raise PluginError(f"{n} comes from a folder: --to only moves a git source to another tag")
            source = f"git:{m['url']}@{to}" + (f"#{m['sub']}" if m["sub"] else "")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            folder, locked = _fetch(source, Path(tmp))
            src = _read(folder)
            if src.name != n:
                raise PluginError(f"{source} holds plugin '{src.name}', not '{n}'")
            dest = plugins.PROJECT_DIR / n
            old, new = (_files(dest) if dest.is_dir() else {}), _files(folder)
            if old == new and entries[n]["source"] == locked:
                continue
            before = entries[n].get("version")
            p, entries[n] = _entry(_vendor(src), locked)
        changes.append({"name": n, "from": before, "to": entries[n]["version"], "runs_code": p.runs_code,
                        "needs_trust": p.needs_trust,
                        "files": {"added": sorted(set(new) - set(old)), "removed": sorted(set(old) - set(new)),
                                  "changed": sorted(k for k in set(old) & set(new) if old[k] != new[k])}})
    save_lock(entries)
    return changes


def _semver(tag: str) -> tuple[int, ...] | None:
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag.strip())
    return tuple(int(x) for x in m.groups()) if m else None


def outdated() -> list[dict]:
    out = []
    for n, e in sorted(load_lock().items()):
        have, latest = _semver(str(e.get("version", ""))), None
        m = GIT.match(e["source"])
        if m:
            r = run(["git", "ls-remote", "--tags", m["url"]], check=False, quiet=True)
            tags = [line.rsplit("refs/tags/", 1)[-1].removesuffix("^{}") for line in (r.stdout or "").splitlines()]
            versions = sorted({v for t in tags if (v := _semver(t))})
            latest = versions[-1] if versions else None
        else:
            try:
                latest = _semver(str(_read(Path(e["source"].removeprefix("path:"))).manifest.get("version")))
            except PluginError:
                latest = None
        if have and latest and latest > have:
            out.append({"name": n, "version": e["version"], "latest": ".".join(map(str, latest)), "source": e["source"]})
    return out


def remove(name: str) -> bool:
    entries = load_lock()
    dest = plugins.PROJECT_DIR / name
    if name not in entries and not dest.is_dir():
        raise PluginError(f"no team plugin called {name}")
    if dest.is_dir():
        shutil.rmtree(dest)
    entries.pop(name, None)
    save_lock(entries)
    return True


def issues() -> list[str]:
    """What `check` warns about: folders that no longer match the lock, folders it does not know, locked plugins gone.
    A project that never used `plugins add` (no lock) has nothing to say."""
    entries = load_lock()
    if not entries:
        return []
    out = []
    found = {p.path.name: p for p in plugins.discover() if p.source == "project"}
    for n, e in sorted(entries.items()):
        p = found.get(n)
        if not p:
            out.append(f".camarones/plugins/{n}: in plugins.lock but the folder is gone (`camaron plugins update {n}`)")
        elif p.fingerprint() != e.get("sha256"):
            out.append(f".camarones/plugins/{n}: edited by hand since plugins.lock recorded it "
                       f"(`camaron plugins update {n}` restores {e.get('version')})")
    out += [f".camarones/plugins/{n}: not in plugins.lock (vendor it with `camaron plugins add <source>`)"
            for n in sorted(set(found) - set(entries))]
    return out
