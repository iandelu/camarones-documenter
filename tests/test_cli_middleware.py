"""What wraps every CLI command (lib/interfaces/cli/middleware.py): errors become one line and exit 1, and each run
is counted in the usage log unless the command says otherwise."""
from __future__ import annotations

import argparse

import pytest

from lib.interfaces.cli import middleware
from lib.interfaces.cli.middleware import Invocation
from lib.interfaces.cli.registry import CliContext, Command, command


def fake(calls: list[str], usage: bool = True) -> Command:
    @command("zz", "cli", usage=usage)
    class Zz(Command):
        def run(self, args, cli):
            calls.append("run")
            return 0
    return Zz()


@pytest.mark.parametrize("err,line", [(ValueError("boom"), "🦐✖ boom"), (KeyError("k"), "🦐✖ 'k'"),
                                      (RuntimeError("r"), "🦐✖ r"), (OSError("o"), "🦐✖ o")])
def test_a_command_error_is_one_line_and_exit_1(err, line, capsys):
    def boom():
        raise err
    assert middleware.errors_to_exit(None, boom) == 1
    assert capsys.readouterr().err == line + "\n"


@pytest.mark.parametrize("err", [SystemExit(2), KeyboardInterrupt()])
def test_exit_and_interrupt_pass_through(err):
    def stop():
        raise err
    with pytest.raises(type(err)):
        middleware.errors_to_exit(None, stop)


def _dispatch(kit, monkeypatch, usage: bool) -> list[str]:
    from lib import usage as usage_log
    calls: list[str] = []
    monkeypatch.setattr(usage_log, "record", lambda event, **kw: calls.append(f"usage:{event}"))
    p = argparse.ArgumentParser()
    assert middleware.dispatch(Invocation(fake(calls, usage), argparse.Namespace(cmd="zz"), CliContext(p))) == 0
    return calls


def test_usage_is_recorded_before_the_command_runs(kit, monkeypatch):
    assert _dispatch(kit, monkeypatch, usage=True) == ["usage:cli:zz", "run"]


def test_a_command_that_records_no_usage_logs_nothing(kit, monkeypatch):
    assert _dispatch(kit, monkeypatch, usage=False) == ["run"]


def test_an_error_while_counting_is_mapped_too(kit, monkeypatch, capsys):
    from lib import usage as usage_log

    def broken(event, **kw):
        raise OSError("disk full")
    monkeypatch.setattr(usage_log, "record", broken)
    inv = Invocation(fake([]), argparse.Namespace(cmd="zz"), CliContext(argparse.ArgumentParser()))
    assert middleware.dispatch(inv) == 1 and capsys.readouterr().err == "🦐✖ disk full\n"
