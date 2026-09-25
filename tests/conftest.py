"""Shared fixtures. The kit captures ROOT, HOME and friends at import time (lib/common.py), so every test gets a fresh
import of `lib` pointed at its own temporary workspace and home folder — nothing leaks into the real ~/.camarones."""
from __future__ import annotations

import importlib, os, sys
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

from fixtures.builder import make_workspace  # noqa: E402

MODULES = ("common", "docs", "env", "plan", "projects", "migrate", "quality", "install", "quickarch", "creds", "wizard")


def purge_kit_modules() -> None:
    for name in [m for m in sys.modules if m == "lib" or m.startswith("lib.")]:
        del sys.modules[name]


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Temporary HOME + git identity; restores os.environ afterwards (common.ensure_path edits PATH at import)."""
    saved = dict(os.environ)
    home = tmp_path / "home"
    home.mkdir()
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = Test\n\temail = test@example.com\n[init]\n\tdefaultBranch = main\n"
                         "[core]\n\tautocrlf = false\n", encoding="utf-8")
    for k, v in {"HOME": home, "USERPROFILE": home, "GIT_CONFIG_GLOBAL": gitconfig, "GIT_CONFIG_NOSYSTEM": "1",
                 "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring", "LANG": "es_ES.UTF-8"}.items():
        monkeypatch.setenv(k, str(v))
    for k in ("CAMARONES_ROOT", "CAMARONES_GLOBAL"):
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
def kit(tmp_path, isolated_env):
    """A fresh `lib` import on a synthetic workspace: <tmp>/demo/{api,web,worker} + <tmp>/demo/cam-docs."""
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


@pytest.fixture
def wired(kit):
    return wire_project(kit)


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
