"""The composition root: picks each port's adapter and each use-case module, builds the process's Services and installs
them. A process entry calls build() once: lib.interfaces.cli.main (every camarones.py run), the kit code that
lib.harness.integrate runs in a unit's tree, and the tests' load_kit. A provider imports its module inside the
function, so a command that reads no service imports none of them."""
from __future__ import annotations

from collections.abc import Callable

from lib.app import services
from lib.app.services import Services


def _launcher() -> object:
    from lib.adapters.system import os_open
    return os_open


def _diagrams() -> object:
    from lib.adapters import likec4
    return likec4


def _links() -> object:
    from lib.adapters import fs_links
    return fs_links


def _agent_config() -> object:
    from lib.adapters import agent_config
    return agent_config


def _toolchain() -> object:
    from lib.adapters import prereqs
    return prereqs


def _code() -> object:
    from lib.adapters import graphify
    return graphify


def _wiki_engine() -> object:
    from lib.adapters import openwiki
    return openwiki


def _containers() -> object:
    from lib.adapters import docker
    return docker


def _vcs() -> object:
    from lib.adapters.git import checkpoint
    return checkpoint


PROVIDERS: dict[str, Callable[[], object]] = {
    "launcher": _launcher,
    "diagrams": _diagrams,
    "links": _links,
    "agent_config": _agent_config,
    "toolchain": _toolchain,
    "code": _code,
    "wiki_engine": _wiki_engine,
    "containers": _containers,
    "vcs": _vcs,
}


def build(**overrides: object) -> Services:
    """The process's services, installed. An override replaces one field (a test passes a fake)."""
    declared = services.fields()
    unknown = sorted(set(overrides) - declared)
    if unknown:
        raise TypeError(f"unknown service: {', '.join(unknown)}")
    missing = sorted(declared - set(PROVIDERS))
    if missing:
        raise RuntimeError(f"no provider for {', '.join(missing)}")
    given = {name: (lambda value=value: value) for name, value in overrides.items()}
    return services.install(Services({**PROVIDERS, **given}))
