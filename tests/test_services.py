"""The process's services (lib/app/services.py) and the composition root that builds them (lib/bootstrap.py): every
process entry builds them once, and commands and routes receive them."""
from __future__ import annotations

import importlib
import json
import sys

import pytest

from conftest import purge_kit_modules
from fixtures.http_probe import arm, request, serving
from test_env_split import NEW


@pytest.fixture
def svc(kit):
    return importlib.import_module("lib.app.services")


def main(argv: list[str]) -> int:
    return importlib.import_module("lib.interfaces.cli.main").main(argv)


def test_current_before_a_build_says_how_to_get_one(svc, monkeypatch):
    monkeypatch.setattr(svc, "_current", None)
    with pytest.raises(RuntimeError, match="lib.bootstrap.build"):
        svc.current()


def test_build_installs_what_it_returns(kit, svc):
    s = kit.bootstrap.build()
    assert svc.current() is s


def test_the_cli_entry_builds_the_services(svc, monkeypatch):
    monkeypatch.setattr(svc, "_current", None)
    assert main(["version"]) == 0
    assert isinstance(svc.current(), svc.Services)


def test_a_command_that_needs_no_env_code_imports_none(kit):
    purge_kit_modules()
    assert main(["version"]) == 0
    assert sorted(f"lib.{n}" for n in NEW if f"lib.{n}" in sys.modules) == []


def test_kit_code_run_in_another_tree_has_services(kit):
    integrate = importlib.import_module("lib.harness.integrate")
    kit_ctx = importlib.import_module("lib.core.paths").CTX
    out = integrate._kit(kit_ctx, "from lib.app import services\nprint(json.dumps(type(services.current()).__name__))")
    assert json.loads(out.strip().splitlines()[-1]) == "Services"


def test_build_refuses_an_unknown_service(kit):
    with pytest.raises(TypeError, match="unknown service: nope"):
        kit.bootstrap.build(nope=object())


def test_a_command_gets_the_services(svc, monkeypatch):
    seen = []
    monkeypatch.setattr(importlib.import_module("lib.interfaces.cli.middleware"), "dispatch",
                        lambda inv, *a, **kw: seen.append(inv) or 0)
    assert main(["version"]) == 0
    assert seen[0].cli.services is svc.current()


def test_a_request_carries_the_processs_services(kit, svc, monkeypatch):
    router = importlib.import_module("lib.interfaces.http.router")
    m = importlib.import_module("lib.interfaces.http.messages")
    arm(monkeypatch)

    @router.route("GET", "/api/zz")
    def h(req):
        return m.json_response({"same": req.services is svc.current()})
    monkeypatch.setattr(router, "load", lambda: router.Router(h.__routes__))
    with serving(kit.serve.Handler) as base:
        got = request(base, "GET", "/api/zz")
    assert (got[0], json.loads(got[2])) == (200, {"same": True})
