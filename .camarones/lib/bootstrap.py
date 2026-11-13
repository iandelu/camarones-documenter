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


PROVIDERS: dict[str, Callable[[], object]] = {
    "launcher": _launcher,
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
