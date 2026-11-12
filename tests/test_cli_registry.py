"""The CLI's command registry (lib/interfaces/cli/registry.py): one class per command, found by scanning a package, so
a command is added by adding a module and nothing else."""
from __future__ import annotations

import argparse
import itertools
import subprocess
import sys

import pytest

from conftest import KIT_DIR

MOVED: set[str] = {
    "help", "wizard", "catalog", "app", "new", "switch", "init", "join", "projects",
    "setup", "install", "upgrade", "self-update", "unlink", "profile", "sync", "detect", "arch", "down", "version",
    "repair", "mcp", "up", "migrate", "uninstall", "config",
    "changes", "llms", "graph", "history", "blocks", "pages", "diagrams", "fresh", "mark-documented", "arch-draft",
    "radar", "inventory", "bump", "schemas", "stack",
    "arch-validate", "doctor", "eval", "ab", "kpis", "pipeline", "status", "check", "stats", "health",
    "run", "pr", "runs", "wiki", "docs", "plan", "prompt", "autopilot",
    "portal", "removed", "review", "hook", "hooks", "plugins", "export", "confirm", "translated", "ci", "checkpoint",
    "remote", "share", "trust", "feedback", "interview", "board", "adr",
}
_ids = itertools.count()


def make_pkg(tmp_path, monkeypatch, modules: dict[str, str]) -> str:
    """A throwaway command package on sys.path, with a name no other test uses (imports are cached per process)."""
    name = f"zz_cmds_{next(_ids)}_{tmp_path.name}".replace("-", "_")
    pkg = tmp_path / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    for mod, src in modules.items():
        (pkg / f"{mod}.py").write_text("from lib.interfaces.cli.registry import Command, command\n\n" + src,
                                       encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    return name


@pytest.fixture
def reg():
    """Imported per test: conftest drops every lib module between tests, and a stale Command class would not match."""
    from lib.interfaces.cli import registry
    return registry


def simple(name: str, aliases: tuple[str, ...] = ()) -> str:
    cls = "C" + name.replace("-", "_").title().replace("_", "")
    return f'@command("{name}", "cli", aliases={aliases!r})\nclass {cls}(Command):\n    pass\n'


def test_command_sets_the_spec_and_returns_the_class(reg):
    @reg.command("zz", "app", "check", es="Prueba", en="Test", project=False)
    class Zz(reg.Command):
        pass
    assert Zz.spec == reg.Spec("zz", "app", "check", es="Prueba", en="Test", project=False)
    assert Zz().needs_project([]) is False and Zz().records_usage(argparse.Namespace()) is True


@pytest.mark.parametrize("kw", [dict(verdict="nope"), dict(verdict="app"), dict(verdict="app", zone="check"),
                                dict(verdict="cli", zone="check"), dict(verdict="app", zone="nope", es="a", en="b")])
def test_a_bad_catalog_row_is_refused(kw, reg):
    with pytest.raises(ValueError):
        reg.command("zz", **kw)


def test_a_new_module_is_picked_up_with_no_other_edit(tmp_path, monkeypatch, reg):
    pkg = make_pkg(tmp_path, monkeypatch, {"extra": (
        '@command("zz-extra", "cli")\nclass ZzExtra(Command):\n'
        "    def configure(self, p):\n        p.add_argument('--n', type=int, default=1)\n\n"
        "    def run(self, args, cli):\n        return args.n\n")})
    cmds = reg.load(pkg)
    p = argparse.ArgumentParser()
    reg.add_all(p.add_subparsers(dest="cmd"), cmds)
    args = p.parse_args(["zz-extra", "--n", "3"])
    assert cmds["zz-extra"].run(args, reg.CliContext(p)) == 3


@pytest.mark.parametrize("second", [simple("zz-a"), simple("zz-b", aliases=("zz-a",))])
def test_a_name_used_twice_is_refused(second, tmp_path, monkeypatch, reg):
    pkg = make_pkg(tmp_path, monkeypatch, {"one": simple("zz-a"), "two": second})
    with pytest.raises(ValueError):
        reg.load(pkg)


def test_order_comes_first_and_the_rest_by_name(tmp_path, monkeypatch, reg):
    pkg = make_pkg(tmp_path, monkeypatch, {"one": simple("zz-b") + "\n\n" + simple("zz-a"), "two": simple("version")})
    assert list(reg.load(pkg)) == ["version", "zz-a", "zz-b"]


def test_an_alias_parses_and_finds_the_same_command(tmp_path, monkeypatch, reg):
    pkg = make_pkg(tmp_path, monkeypatch, {"one": simple("zz-new", aliases=("zz-old",))})
    cmds = reg.load(pkg)
    p = argparse.ArgumentParser()
    reg.add_all(p.add_subparsers(dest="cmd"), cmds)
    assert p.parse_args(["zz-old"]).cmd == "zz-old"
    assert reg.find(cmds, "zz-old") is cmds["zz-new"] and reg.find(cmds, "zz-new") is cmds["zz-new"]
    assert reg.find(cmds, "nope") is None


def test_entries_have_the_catalog_shape(reg):
    @reg.command("zz", "app", "check", es="Prueba", en="Test")
    class Zz(reg.Command):
        pass
    assert reg.entries({"zz": Zz()}) == {"zz": {"verdict": "app", "zone": "check", "es": "Prueba", "en": "Test",
                                                     "ai": False, "destructive": False, "reads": None}}


def test_loading_the_registry_imports_nothing_outside_the_cli():
    code = ("import sys\nsys.path.insert(0, sys.argv[1])\nfrom lib.interfaces.cli import registry\nregistry.load()\n"
            "print('\\n'.join(sorted(m for m in sys.modules if m == 'lib' or m.startswith('lib.'))))\n")
    r = subprocess.run([sys.executable, "-c", code, str(KIT_DIR)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    loaded = r.stdout.split()
    assert [m for m in loaded if m not in ("lib", "lib.interfaces") and not m.startswith("lib.interfaces.cli")] == []


def test_moved_commands_are_registry_commands(reg):
    assert MOVED <= set(reg.load())


def test_the_old_cli_modules_are_facades():
    from lib import adr_cli
    from lib.interfaces.cli.commands import adr, board
    from lib.kanban import cli as board_cli
    assert board_cli.__facade__ == "lib.interfaces.cli.commands.board" and board_cli.run is board.run
    assert board_cli.add_parser is board.add_parser
    assert adr_cli.__facade__ == "lib.interfaces.cli.commands.adr" and adr_cli.add_parser is adr.add_parser
    assert adr_cli.run is adr.run
