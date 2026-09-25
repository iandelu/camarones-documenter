"""Central registry of cam-docs projects. A global kit install serves many projects; this is how
`camarones` finds, creates and switches between them instead of requiring CAMARONES_ROOT set by hand.
Registry lives at ~/.camarones/projects.json — outside any project, next to the global kit copy."""
from __future__ import annotations

import json, os, re, urllib.parse, urllib.request
from pathlib import Path

from .common import CAM_DIR, HOME, IS_WIN, docs_root, find_project_marker, run

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


def unregister(*paths: Path) -> int:
    """Drop the rows of these paths (a project's cam-docs and its workspace folder). Returns how many went."""
    gone = {p.resolve() for p in paths}
    rows = load()
    keep = [r for r in rows if Path(r["path"]).resolve() not in gone]
    if len(keep) != len(rows):
        save(keep)
    return len(rows) - len(keep)


def list_registered() -> list[dict]:
    """Registered projects that still exist on disk (stale entries are skipped, never deleted silently), one row
    per docs root: a workspace folder and its cam-docs/ are the same project."""
    seen, rows = set(), []
    for r in load():
        if not Path(r["path"]).is_dir():
            continue
        root = docs_root(Path(r["path"]))
        if root not in seen:
            seen.add(root)
            rows.append({**r, "path": str(root)})
    return rows


def create(name: str, at: Path | None = None, url: str = "") -> Path:
    """Make <at>/<name>/cam-docs/ (a new workspace folder for the repos, with its docs folder) and register it.
    The wizard's first-run flow (env.init_templates) does the actual bootstrap once it's opened.
    `url`: the team's cam-docs repo — joined (cloned, or reused if already here) instead of starting from zero."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "project"
    base = at or Path.cwd()
    workspace = base if base.name == slug or has_repos(base) else base / slug
    return join(url, workspace, slug)[0] if url.strip() else adopt(workspace, slug)


# ---------- the team's docs repo ----------
def remote_key(url: str) -> str:
    """What a git remote points at, so the scp, https, ssh:// and token-in-URL spellings of one repo compare equal."""
    u = url.strip()
    m = re.match(r"^[\w.+-]+@([^:/]+):(?!//)(.+)$", u)                  # git@host:group/repo.git
    if m:
        host, path = m.groups()
    else:
        p = urllib.parse.urlparse(u)
        if not p.hostname:                                             # local path or file:// (tests, shared drives)
            local = urllib.request.url2pathname(p.path) if p.scheme == "file" else u
            return os.path.normcase(str(Path(local).resolve()))
        host, path = p.hostname, p.path
    return f"{host.lower()}/{path.strip('/').removesuffix('.git').strip('/').lower()}"


def _git(*args: str, cwd: Path | None = None, url: str = "", check: bool = False):
    from . import creds                                               # token for this host only, never stored in .git
    return run(["git", *args], cwd=cwd, check=check, quiet=True, env=creds.git_env(url) if url else None)


def origin_of(repo: Path) -> str:
    r = _git("remote", "get-url", "origin", cwd=repo)
    return r.stdout.strip() if r.returncode == 0 else ""


def _is_project(root: Path) -> bool:
    return (root / ".camarones" / "workspace.yaml").exists()


def _last_line(r) -> str:
    lines = (r.stderr or r.stdout or "").strip().splitlines()
    return lines[-1] if lines else f"exit {r.returncode}"


def join(url: str, workspace: Path | None = None, name: str | None = None) -> tuple[Path, bool]:
    """The team's cam-docs repo at `url` becomes <workspace>/cam-docs. Returns (docs root, joined): joined = it
    already holds a Camarón project, so only this machine needs setting up. Never does the work twice: a registered
    project or a local cam-docs with that remote is reused (fast-forwarded), an empty remote becomes the origin of a
    fresh local project, and only otherwise is the repo cloned."""
    key, workspace = remote_key(url), (workspace or Path.cwd())
    for r in list_registered():                                     # already cloned somewhere on this machine
        root = Path(r["path"])
        if (root / ".git").exists() and origin_of(root) and remote_key(origin_of(root)) == key:
            return _reuse(root, url, name)
    dest = workspace / CAM_DIR
    if (dest / ".git").exists():
        have = origin_of(dest)
        if have and remote_key(have) != key:
            raise ValueError(f"{dest} ya es un repo con otro remoto ({have}) — elige otra carpeta.")
        if have:
            return _reuse(dest, url, name)
    probe = _git("ls-remote", "--heads", url, url=url)
    if probe.returncode != 0:
        raise RuntimeError(f"no puedo leer {url}: {_last_line(probe)}")
    if not probe.stdout.strip():                                    # empty remote: start here, publish on share
        dest = adopt(workspace, name)
        if not (dest / ".git").exists():
            _git("init", "-q", str(dest), check=True)
        _git("remote", "remove", "origin", cwd=dest)
        _git("remote", "add", "origin", url, cwd=dest, check=True)
        return dest, _is_project(dest)
    if (dest / ".git").exists() or (dest.exists() and any(dest.iterdir())):
        raise ValueError(f"{dest} ya existe y no está vacía — elige otra carpeta.")
    workspace.mkdir(parents=True, exist_ok=True)
    r = _git("clone", "--quiet", url, str(dest), url=url)
    if r.returncode != 0:
        raise RuntimeError(f"no puedo clonar {url}: {_last_line(r)}")
    if _git("rev-parse", "--verify", "--quiet", "HEAD", cwd=dest).returncode != 0:
        # the remote's HEAD names a branch nobody pushed (repo created with `main`, first push from `master`)
        heads = [ln.split("refs/heads/", 1)[1] for ln in probe.stdout.splitlines() if "refs/heads/" in ln]
        _git("checkout", "-q", next((b for b in ("main", "master") if b in heads), heads[0]), cwd=dest, check=True)
    register(dest, name=name or workspace.name)
    return dest, _is_project(dest)


def _reuse(root: Path, url: str, name: str | None) -> tuple[Path, bool]:
    """A clone that is already here: bring in the team's latest work if that is a fast-forward, keep it as is if not."""
    if not _git("status", "--porcelain", "--untracked-files=no", cwd=root).stdout.strip():
        _git("pull", "--ff-only", "--quiet", cwd=root, url=url)
    known = next((r["name"] for r in load() if Path(r["path"]).resolve() == root.resolve()), None)
    register(root, name=name or known or root.parent.name)
    return root.resolve(), _is_project(root)


def adopt(workspace: Path, name: str | None = None) -> Path:
    """Use `workspace` (a folder with — or for — the repos) as a project: its docs root is workspace/cam-docs."""
    dest = workspace / CAM_DIR
    if (dest / ".camarones" / "workspace.yaml").exists():
        register(dest, name=name)
        return dest
    if dest.exists() and any(dest.iterdir()) and not (dest / ".git").exists():
        raise ValueError(f"{dest} ya existe y no está vacía — elige otra carpeta.")
    dest.mkdir(parents=True, exist_ok=True)
    register(dest, name=name or workspace.name)
    return dest


def has_repos(folder: Path) -> bool:
    """True if `folder` already looks like an umbrella folder full of repos ('drop the kit next to your
    repos' case) — the signal used to offer adopting it as-is instead of nesting a new project inside it."""
    return folder.is_dir() and any((p / ".git").exists() for p in folder.iterdir() if p.is_dir())


TEAM_URL_Q = {"es": "¿Tu equipo ya tiene un repo de cam-docs? Pega su URL (vacío = empezar uno nuevo):",
              "en": "Does your team already have a cam-docs repo? Paste its URL (empty = start a new one):"}


def _tr(text: dict) -> str:
    """The wizard's language (saved preference, else the system's) before any project — and its T table — is loaded."""
    try:
        lang = json.loads((HOME / ".camarones.json").read_text(encoding="utf-8")).get("lang")
    except (OSError, ValueError):
        lang = None
    lang = lang or ("es" if os.environ.get("LANG", "es").startswith("es") or IS_WIN else "en")
    return text.get(lang, text["en"])


def pick(allow_new: bool = True, here: Path | None = None) -> Path | None:
    """Interactive project picker (questionary). Returns None if the user cancelled (Esc/Ctrl-C).
    `here`: offer adopting this folder as-is (e.g. the cwd) when it isn't already a registered project —
    covers running `camarones` straight from an existing repos folder instead of a cama-docs-* one."""
    import questionary
    rows = list_registered()
    choices = [questionary.Choice(f"{r['name']}  ({r['path']})", value=Path(r["path"])) for r in rows]
    offer_here = here is not None and not any(Path(r["path"]).resolve() in (here.resolve(), (here / CAM_DIR).resolve())
                                              for r in rows)
    if offer_here:
        label = f"usar esta carpeta ({here}/{CAM_DIR})" + ("  — repos detectados" if has_repos(here) else "")
        choices.append(questionary.Choice(label, value=here))
    if allow_new:
        choices.append(questionary.Choice("+ nuevo proyecto (<nombre>/cam-docs)", value="__new__"))
    if not choices:
        name = questionary.text("Ningún proyecto registrado todavía. Nombre del proyecto (ej. enjoy):").ask()
        return create(name) if name else None
    picked = questionary.select("🦐 ¿Qué proyecto quieres abrir?", choices=choices).ask()
    if picked is None:
        return None
    if picked == "__new__" or (offer_here and picked == here):
        name = questionary.text("Nombre del nuevo proyecto (ej. enjoy):").ask() if picked == "__new__" else here.name
        url = questionary.text(_tr(TEAM_URL_Q)).ask() if name else None
        if url is None:
            return None
        try:
            return create(name, url=url) if picked == "__new__" else (join(url, here)[0] if url.strip() else adopt(here))
        except (ValueError, RuntimeError) as e:
            print(f"✖ {e}")
            return None
    picked = docs_root(picked)
    touch(picked)
    return picked
