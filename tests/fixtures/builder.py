"""Synthetic multi-repo workspace: three small git repos next to a cam-docs/ project, the layout the kit documents.
Offline and deterministic; the real-repo sandbox is scripts/sandbox.py.

Building one costs about a dozen git processes, so each layout is built once per process (once per xdist worker) into
a template that every call copies: each test still gets its own workspace under its own tmp_path."""
from __future__ import annotations

import atexit, os, shutil, stat, subprocess, tempfile
from pathlib import Path

import yaml

REPOS = {
    "api": {
        "pom.xml": "<project><artifactId>api</artifactId></project>\n",
        "src/main/java/demo/Api.java": "package demo;\n\npublic class Api {\n    // calls worker over HTTP\n}\n",
        "README.md": "# api\n\nREST backend.\n",
        # a CLAUDE.md the team versioned itself: the kit's pointer block must come and go without touching it
        "CLAUDE.md": "# api notes\n\nRun `mvn test` before pushing.\n",
        ".gitignore": "target/\n",
    },
    "web": {
        "package.json": '{"name": "web", "version": "1.0.0", "dependencies": {"react": "18.0.0"}}\n',
        "src/App.jsx": "export default function App() { return fetch('/api/pets') }\n",
        "README.md": "# web\n\nFrontend.\n",
    },
    "worker": {
        "pyproject.toml": '[project]\nname = "worker"\nversion = "0.1.0"\n',
        "worker/main.py": "def run():\n    return 'ok'\n",
    },
}


# the git identity tests run with; conftest's isolated_env writes the same file for each test
GITCONFIG = ("[user]\n\tname = Test\n\temail = test@example.com\n[init]\n\tdefaultBranch = main\n"
             "[core]\n\tautocrlf = false\n")


def git(repo: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=env).stdout


def make_repo(path: Path, files: dict[str, str], env: dict | None = None) -> Path:
    path.mkdir(parents=True)
    git(path, "init", "-q", "-b", "main", env=env)
    for rel, text in files.items():
        f = path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    git(path, "add", "-A", env=env)
    git(path, "commit", "-q", "-m", "initial", env=env)
    return path


_templates: dict[tuple, Path] = {}


def _template(repos: tuple[str, ...], name: str) -> Path:
    """The workspace for (repos, name), built once in this process with the tests' git identity, never the user's."""
    key = (repos, name)
    if key not in _templates or not _templates[key].exists():
        base = Path(tempfile.mkdtemp(prefix="cam-ws-"))
        atexit.register(lambda: base.exists() and rmtree(base))
        (base / "gitconfig").write_text(GITCONFIG, encoding="utf-8")
        env = {**os.environ, "GIT_CONFIG_GLOBAL": str(base / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1"}
        _templates[key] = build_workspace(base, repos, name, env=env)
    return _templates[key]


def make_workspace(base: Path, repos: tuple[str, ...] = tuple(REPOS), name: str = "demo") -> Path:
    """<base>/<name>/{api,web,worker}/ + <base>/<name>/cam-docs/.camarones/workspace.yaml. Returns the workspace."""
    ws = base / name
    shutil.copytree(_template(tuple(repos), name), ws, symlinks=True)
    return ws


def build_workspace(base: Path, repos: tuple[str, ...] = tuple(REPOS), name: str = "demo",
                    env: dict | None = None) -> Path:
    """make_workspace without the template: runs git for every repo."""
    ws = base / name
    for r in repos:
        make_repo(ws / r, REPOS[r], env=env)
    cam = ws / "cam-docs" / ".camarones"
    cam.mkdir(parents=True)
    (cam / "workspace.yaml").write_text(yaml.safe_dump({
        "project": {"name": name, "id": name, "profile": "full", "canonical_language": "en", "translations": ["es"],
                    "components": ["graphify", "likec4", "openwiki", "quality", "agents"]},
        "repos": [{"name": r, "kind": "service", "branch": "main"} for r in repos],
    }, sort_keys=False), encoding="utf-8")
    return ws


def snapshot(repo: Path) -> dict[str, bytes]:
    """Every file of a repo except .git internals other than info/exclude: what 'untouched' means for a repo."""
    out = {}
    for p in sorted(repo.rglob("*")):
        rel = p.relative_to(repo).as_posix()
        if rel.startswith(".git/") and rel != ".git/info/exclude":
            continue
        if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
            out[rel] = b"<link>"
        elif p.is_file():
            out[rel] = p.read_bytes()
    return out


def rmtree(path: Path) -> None:
    """shutil.rmtree that also clears read-only git objects on Windows."""
    def onerror(fn, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        fn(p)
    shutil.rmtree(path, onerror=onerror)
