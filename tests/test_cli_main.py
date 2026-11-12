"""The CLI's entry (lib/interfaces/cli/main.py and launch.py): which commands a global install runs outside a project,
which ones are counted in the usage log, the wizard with no argument, and a main() that only parses and dispatches."""
from __future__ import annotations

import argparse
import inspect
import os
import subprocess
import sys

import pytest

from lib.interfaces.cli.registry import ORDER      # pure (test_cli_registry): safe at collection time

NO_PROJECT = {"help", "version", "self-update", "mcp", "catalog", "projects", "app"}
NO_USAGE = {"help", "mcp", "wizard"}


def test_order_is_the_parser(kit):
    """ORDER's commands first, in its order; a command added since sorts after them by name (adding a command is
    adding a module, ORDER only keeps today's --help order)."""
    from lib.interfaces.cli import main
    from lib.catalog import subparsers
    names = list(subparsers(main.build_parser()))
    assert set(ORDER) <= set(names), f"ORDER names commands that are gone: {sorted(set(ORDER) - set(names))}"
    assert names == list(ORDER) + sorted(n for n in names if n not in ORDER)


def test_main_is_short():
    from lib.interfaces.cli import main
    assert len(inspect.getsource(main.main).splitlines()) < 50


@pytest.mark.parametrize("name", ORDER)
def test_which_commands_a_global_install_runs_outside_a_project(name):
    from lib.interfaces.cli import launch
    assert launch.needs_project([name]) is (name not in NO_PROJECT)


def test_git_runs_the_board_merge_driver_outside_a_project():
    from lib.interfaces.cli import launch
    assert launch.needs_project(["board", "merge-driver", "O", "A", "B"]) is False
    assert launch.needs_project(["board", "list"]) is True
    assert launch.needs_project([]) is True and launch.needs_project(["nosuch"]) is True


@pytest.mark.parametrize("name", ORDER)
def test_which_commands_record_usage(name, kit):
    from lib.interfaces.cli import registry
    assert registry.find(registry.load(), name).records_usage(argparse.Namespace(cmd=name, action=None)) is (name not in NO_USAGE)


def test_the_board_merge_driver_records_no_usage(kit):
    from lib.interfaces.cli import registry
    assert registry.find(registry.load(), "board").records_usage(argparse.Namespace(cmd="board", action="merge-driver")) is False


def test_no_argument_opens_the_wizard_and_logs_nothing(kit, monkeypatch):
    from lib import usage, wizard
    from lib.interfaces.cli import main
    calls: list[str] = []

    class W:
        def run(self):
            calls.append("wizard")
    monkeypatch.setattr(wizard, "W", W)
    monkeypatch.setattr(usage, "record", lambda event, **kw: calls.append(f"usage:{event}"))
    assert main.main([]) == 0 and calls == ["wizard"]


def test_help_prints_utf8_on_a_cp1252_pipe(kit):
    r = subprocess.run([sys.executable, str(kit.kit_dir / "camarones.py"), "help"], capture_output=True,
                       env={**os.environ, "CAMARONES_ROOT": str(kit.root), "PYTHONIOENCODING": "cp1252"})
    assert r.returncode == 0 and "🦐 Camarón" in r.stdout.decode("utf-8")


def test_an_error_while_building_the_parser_is_one_line_too(kit, monkeypatch, capsys):
    """The old entry script mapped these errors around all of main(), parsing included."""
    from lib.interfaces.cli import main

    def broken():
        raise PermissionError(13, "Permission denied", "/nope")
    monkeypatch.setattr(main, "build_parser", broken)
    assert main.main(["version"]) == 1
    assert capsys.readouterr().err == "🦐✖ [Errno 13] Permission denied: '/nope'\n"
