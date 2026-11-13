"""Shared fixtures. The kit captures ROOT, HOME and friends at import time (lib/common.py), so every test gets a fresh
import of `lib` pointed at its own temporary workspace and home folder — nothing leaks into the real ~/.camarones."""
from __future__ import annotations

import atexit, importlib, json, os, shutil, socketserver, sys, tempfile
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import pytest

TESTS = Path(__file__).resolve().parent
REPO = TESTS.parent
KIT_DIR = REPO / ".camarones"
for p in (str(KIT_DIR), str(TESTS)):
    if p not in sys.path:
        sys.path.insert(0, p)

from fixtures import bytecode, fast_git, hang_watchdog  # noqa: E402
from fixtures.facade_guard import GuardedMonkeyPatch  # noqa: E402
from fixtures.builder import GITCONFIG, clone, drop_links, make_workspace, rmtree, slim  # noqa: E402
from fixtures.hang_watchdog import pytest_runtest_protocol, pytest_terminal_summary  # noqa: E402,F401
from fixtures.host_tools import hidden_tools, masked_path  # noqa: E402
from fixtures.reaper import Reaper  # noqa: E402

fast_git.install()
START_ENV = dict(os.environ)                    # before any test touched it: what the wired template is built under
REAPER = Reaper()
# a server stops when its serve_forever loop next looks up, every half second by default: each test that shut one down
# waited for it
socketserver.BaseServer.serve_forever.__defaults__ = (0.05,)


def pytest_configure(config) -> None:
    bytecode.pytest_configure(config)
    hang_watchdog.pytest_configure(config)


def pytest_unconfigure(config) -> None:
    REAPER.wait()
    hang_watchdog.pytest_unconfigure(config)
    bytecode.pytest_unconfigure(config)


MODULES = ("common", "docs", "env", "plan", "serve", "projects", "migrate", "quality", "codemap", "install", "quickarch", "creds", "questionnaire", "usage", "onboard", "wizard")


@pytest.hookimpl(tryfirst=True)                 # before xdist's own hook reads the groups
def pytest_collection_modifyitems(items) -> None:
    """`@pytest.mark.serial` tests share one xdist group: under `-n auto --dist loadgroup` one worker runs them all,
    one after the other, while the other workers carry on with the rest."""
    for item in items:
        if item.get_closest_marker("serial"):
            item.add_marker(pytest.mark.xdist_group("serial"))


@pytest.fixture
def monkeypatch():
    mp = GuardedMonkeyPatch()
    yield mp
    mp.undo()


PASSED = pytest.StashKey[bool]()


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    rep = yield
    if rep.when == "call":
        item.stash[PASSED] = rep.passed
    return rep


@pytest.fixture(autouse=True)
def _drop_tmp_path_when_passed(request):
    """A passing test's tmp_path goes in the background (fixtures/reaper.py); a failing one stays."""
    yield
    path = request.node.funcargs.get("tmp_path")
    if path is not None and request.node.stash.get(PASSED, False):
        REAPER.drop(path)


def purge_kit_modules() -> None:
    for name in [m for m in sys.modules if m == "lib" or m.startswith("lib.")]:
        del sys.modules[name]


UNSET = ("CAMARONES_ROOT", "CAMARONES_GLOBAL", "CAMARONES_STATE_ROOT")


def isolated_vars(home: Path, gitconfig: Path, path: str, hidden: frozenset[str]) -> dict[str, str]:
    """What a test runs under: `path` without the machine's `hidden` tools (fixtures/host_tools.py)."""
    out = {"HOME": str(home), "USERPROFILE": str(home), "GIT_CONFIG_GLOBAL": str(gitconfig), "GIT_CONFIG_NOSYSTEM": "1",
           "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring", "LANG": "es_ES.UTF-8"}
    return {**out, "PATH": masked_path(path, hidden), "CAMARONES_KEEP_PATH": "1"} if hidden else out


@pytest.fixture
def isolated_env(request, tmp_path, monkeypatch):
    """Temporary HOME + git identity, none of the machine's own kit tools on PATH; restores os.environ afterwards
    (common.ensure_path edits PATH at import)."""
    saved = dict(os.environ)
    home = tmp_path / "home"
    home.mkdir()
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text(GITCONFIG, encoding="utf-8")
    for k, v in isolated_vars(home, gitconfig, os.environ.get("PATH", ""), hidden_tools(request.node)).items():
        monkeypatch.setenv(k, v)
    for k in UNSET:
        monkeypatch.delenv(k, raising=False)
    yield home
    os.environ.clear()
    os.environ.update(saved)


def load_kit(root: Path, home: Path, ws: Path | None) -> SimpleNamespace:
    os.environ["CAMARONES_ROOT"] = str(root)
    purge_kit_modules()
    ns = SimpleNamespace(root=root, ws=ws or root.parent, home=home, kit_dir=KIT_DIR)
    for m in MODULES:
        setattr(ns, m, importlib.import_module(f"lib.{m}"))
    return ns


@pytest.fixture
def kit(request, tmp_path, isolated_env):
    """A fresh `lib` import on a synthetic workspace: <tmp>/demo/{api,web,worker} + <tmp>/demo/cam-docs. A test that
    asks for `wired` gets a copy of a project wired once per process instead (see `copy_wired`)."""
    if "wired" in request.fixturenames:
        ns = copy_wired(tmp_path, isolated_env)
    else:
        ws = make_workspace(tmp_path)
        ns = load_kit(ws / "cam-docs", isolated_env, ws)
    yield ns
    purge_kit_modules()


def wire_project(kit) -> SimpleNamespace:
    """The offline part of `setup` (no external tools): the 'documented project' state the kit leaves behind."""
    env = kit.env
    ws = kit.docs.workspace()
    ws["project"]["repo_pointer"] = True
    kit.docs.save_workspace(ws)
    env.init_templates(log=lambda _: None)
    env.write_agent_config(["likec4", "openwiki", "agents"])
    kit.linked = env.link_workspace(log=lambda _: None)
    for r in kit.docs.repo_names():
        env.link_repo_wiki(r, log=lambda _: None)
        env.add_repo_pointer(r)
    (kit.root / "docs" / "overview.md").write_text("---\ntitle: Overview\n---\n# Overview\n", encoding="utf-8")
    kit.env.checkpoint_commit("wired")
    return kit


_templates: dict[str, Path] = {}


def project_template(name: str, build) -> Path:
    """<base>/demo and <base>/home after `build(kit)` on the synthetic workspace, built once per process (once per
    xdist worker) for each name, under the environment the process started with: never under what the test that
    happens to come first has set."""
    base = _templates.get(name)
    if base and base.exists():
        return base
    base = Path(tempfile.mkdtemp(prefix=f"cam-{name}-")).resolve()
    atexit.register(lambda: base.exists() and rmtree(base))
    home = base / "home"
    home.mkdir()
    (base / "gitconfig").write_text(GITCONFIG, encoding="utf-8")
    saved = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update({k: v for k, v in START_ENV.items() if k not in UNSET},
                          **isolated_vars(home, base / "gitconfig", START_ENV.get("PATH", ""), hidden_tools()))
        ws = make_workspace(base)
        build(load_kit(ws / "cam-docs", home, ws))
        slim(ws)
    finally:
        purge_kit_modules()
        os.environ.clear()
        os.environ.update(saved)
    _templates[name] = base
    return base


def _is_link(p: Path) -> bool:
    """A symlink, or a Windows junction (absolute: it would still lead into the template)."""
    if p.is_symlink():
        return True
    if hasattr(p, "is_junction"):                                       # Python 3.12+
        return p.is_junction()
    return p.is_dir() and Path(os.path.realpath(p)) != Path(os.path.realpath(p.parent)) / p.name


def copy_project(src: Path, base: Path, home: Path) -> SimpleNamespace:
    """A project template copied to <base>/demo instead of built again: the workspace without its links, the machine's
    records under ~/.camarones moved to this project's root."""
    ws = base / "demo"
    if clone(src / "demo", ws):
        drop_links(ws)
    else:
        shutil.copytree(src / "demo", ws, symlinks=True, ignore=lambda d, names: [n for n in names if _is_link(Path(d) / n)])
    kit = load_kit(ws / "cam-docs", home, ws)
    old, new = (src / "demo" / "cam-docs").resolve(), kit.root.resolve()
    store = importlib.import_module("lib.trust").store_path      # records are named after a hash of the root
    swaps = [(str(old), str(new)), (json.dumps(str(old))[1:-1], json.dumps(str(new))[1:-1])]
    for f in (p for p in (src / "home").rglob("*") if p.is_file()):
        rel = f.relative_to(src / "home")
        dst = home / rel.parent / (store(new).name if rel.name == store(old).name else rel.name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = f.read_text(encoding="utf-8")
        for a, b in swaps:
            text = text.replace(a, b)
        dst.write_text(text, encoding="utf-8", newline="\n")
    return kit


def copy_wired(base: Path, home: Path) -> SimpleNamespace:
    """What `wire_project` leaves behind, copied instead of a dozen git processes; the kit links the copy itself, as it
    would on any OS."""
    kit = copy_project(project_template("wired", wire_project), base, home)
    kit.linked = kit.env.link_workspace(log=lambda _: None)
    for r in kit.docs.repo_names():
        kit.env.link_repo_wiki(r, log=lambda _: None)
    return kit


@pytest.fixture
def wired(kit):
    """A documented project (`wire_project`): `kit` already copied one when the test asked for this fixture."""
    return kit if hasattr(kit, "linked") else wire_project(kit)


class Answers:
    """Queued answers for the wizard prompts; each prompt pops the next one (a callable gets the prompt text)."""

    def __init__(self, answers):
        self.q = deque(answers)
        self.asked: list[str] = []

    def __call__(self, msg, *_a, **_kw):
        self.asked.append(str(msg))
        if not self.q:
            raise AssertionError(f"unexpected prompt: {msg}")
        a = self.q.popleft()
        return a(msg) if callable(a) else a


@pytest.fixture
def fake_wizard(kit, monkeypatch):
    """Returns make(answers) → a W whose sel/chk/txt/yes pop from `answers`; screen and pauses are no-ops."""
    W = kit.wizard.W

    def make(answers):
        a = Answers(answers)
        for name in ("sel", "chk", "txt", "yes"):
            monkeypatch.setattr(W, name, lambda self, msg, *x, **kw: a(msg, *x, **kw))
        monkeypatch.setattr(W, "banner", lambda self, *x, **kw: None)
        monkeypatch.setattr(W, "pause", lambda self: None)
        monkeypatch.setattr(W, "busy", lambda self, fn, *x, total=None, **kw: fn(*x, log=lambda _: None, **kw))
        w = W()
        w.answers = a
        return w
    return make
