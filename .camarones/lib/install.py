"""Explicit, non-destructive kit installation. No tools, hooks or source folders are moved."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from .common import VERSIONS

PROFILES = {"quick": [], "full": ["graphify", "likec4", "openwiki", "agents"]}
RECEIPT = Path('.camarones/install.json')
DIRECTORIES = ('lib', 'templates', 'portal', 'ci')
FILES = ('camarones.py', 'camarones.py.lock', 'README.md', 'TUTORIAL.md', 'PLAYBOOK.md', 'CONVENTIONS.md', 'nginx.conf')
SKIP = {'__pycache__', 'node_modules', '.astro', 'dist', '.cache'}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(path: Path) -> None:
    """Reject symlinks/junctions in an existing path, including its parents."""
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError(f'Refusing linked path: {part}')
        # Python 3.10 on Windows: junctions carry a reparse point attribute.
        if os.name == 'nt' and part.exists() and getattr(part.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError(f'Refusing reparse point: {part}')


def payload(source: Path) -> dict[str, bytes]:
    safe_path(source)
    required = [source / 'camarones.cmd', source / 'camarones.command', source / '.camarones/camarones.py',
                source / '.camarones/lib/common.py']
    if not all(p.is_file() for p in required):
        raise ValueError('Source is not a Camarones kit (launchers and .camarones/ are required).')
    paths = required[:2] + [source / '.camarones' / name for name in FILES if (source / '.camarones' / name).is_file()]
    for name in DIRECTORIES:
        base = source / '.camarones' / name
        if not base.is_dir():
            raise ValueError(f'Missing kit directory: {base}')
        for current, dirs, files in os.walk(base, followlinks=False):
            safe_path(Path(current))
            dirs[:] = [d for d in dirs if d not in SKIP]
            for d in dirs:
                safe_path(Path(current) / d)
            paths += [Path(current) / f for f in files if not f.endswith(('.pyc', '.pyo'))]
    result = {}
    for path in paths:
        safe_path(path)
        result[path.relative_to(source).as_posix()] = path.read_bytes()
    return result


def install(source: Path, destination: Path, profile: str = 'quick', *, update: bool = False,
            dry_run: bool = False, log=print) -> dict:
    if profile not in PROFILES:
        raise ValueError(f'Unknown profile: {profile}')
    source = source.absolute()
    destination = destination.expanduser().absolute()
    safe_path(destination)
    source, destination = source.resolve(), destination.resolve()
    if destination == source or source in destination.parents:
        raise ValueError('Choose a separate project folder outside the source kit.')
    if destination == Path(destination.anchor) or destination == Path.home().resolve():
        raise ValueError('Choose a project folder, not a filesystem root or your home folder.')
    if destination.exists() and not destination.is_dir():
        raise ValueError('Destination must be a directory.')
    files = payload(source)
    # Read the source version (an update may come from a newer kit).
    import re
    match = re.search(r'"kit":\s*"([\d.]+)"', files['.camarones/lib/common.py'].decode('utf-8'))
    version = match.group(1) if match else VERSIONS['kit']
    receipt_path = destination / RECEIPT
    safe_path(receipt_path)
    previous = json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.exists() else {}
    old_hashes = previous.get('files', {})
    changes = {}
    for name, data in files.items():
        target = destination / name
        safe_path(target)
        if target.exists():
            if not target.is_file():
                raise ValueError(f'File conflicts with a directory: {target}')
            current = target.read_bytes()
            if current == data:
                continue
            if not update:
                raise ValueError(f'Existing file differs: {name}. Use upgrade explicitly.')
            if name in old_hashes and digest(current) != old_hashes[name]:
                raise ValueError(f'Locally modified kit file: {name}. Preserve your edits before upgrading.')
        changes[name] = data
    ws = destination / '.camarones/workspace.yaml'
    safe_path(ws)
    if not ws.exists():
        import yaml
        changes['.camarones/workspace.yaml'] = yaml.safe_dump({
            'project': {'name': destination.name, 'profile': profile, 'components': PROFILES[profile], 'translations': ['es']},
            'repos': [],
        }, sort_keys=False).encode('utf-8')
    receipt = {'version': version, 'files': {name: digest(data) for name, data in sorted(files.items())}}
    receipt_data = (json.dumps(receipt, indent=2) + '\n').encode('utf-8')
    if not receipt_path.exists() or receipt_path.read_bytes() != receipt_data:
        changes[RECEIPT.as_posix()] = receipt_data
    result = {'destination': str(destination), 'version': version, 'changed': sorted(changes), 'dry_run': dry_run}
    log(f'{"Preview" if dry_run else "Install"}: {destination} · {version} · {len(changes)} file(s)')
    for name in sorted(changes):
        log(f'  {name}')
    if dry_run or not changes:
        return result
    # Preflight is complete. Stage the complete payload before replacing any file.
    destination.mkdir(parents=True, exist_ok=True)
    backup = destination / '.camarones/.cache/install-backups' / uuid.uuid4().hex
    safe_path(backup)
    originals = {name: (destination / name).read_bytes() if (destination / name).exists() else None for name in changes}
    written = []
    with tempfile.TemporaryDirectory(prefix='.camarones-install-', dir=destination) as staging:
        stage = Path(staging)
        for name, data in changes.items():
            temporary = stage / name
            temporary.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(data)
        try:
            for name in changes:
                target = destination / name
                safe_path(target)
                target.parent.mkdir(parents=True, exist_ok=True)
                if originals[name] is not None:
                    saved = backup / name
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    saved.write_bytes(originals[name])
                os.replace(stage / name, target)
                written.append(name)
            if os.name != 'nt':
                (destination / 'camarones.command').chmod(0o755)
        except BaseException:
            for name in reversed(written):
                target = destination / name
                if originals[name] is None:
                    target.unlink()
                else:
                    target.write_bytes(originals[name])
            raise
    log('Kit copied. Source, repositories and existing workspace settings were preserved.')
    return result


def unlink(destination: Path, *, log=print) -> list[str]:
    """Inverse of install(): strip a project's local kit code (the launchers, .camarones/lib,
    templates, portal, ci, camarones.py…) after switching that project to a global install.
    workspace.yaml, .cache and install.json are left untouched — CAMARONES_ROOT / the cwd-marker
    walk-up finds this project the same way whether or not its own copy of the code is still here."""
    destination = destination.resolve()
    removed = []
    for rel in ('camarones.cmd', 'camarones.command', *(f'.camarones/{name}' for name in FILES)):
        p = destination / rel
        if p.is_file():
            p.unlink()
            removed.append(rel)
    for name in DIRECTORIES:
        p = destination / '.camarones' / name
        if p.is_dir():
            shutil.rmtree(p)
            removed.append(f'.camarones/{name}/')
    for name in removed:
        log(f"  - {name}")
    return removed
