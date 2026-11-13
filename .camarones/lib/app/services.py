"""The process's services: each port's adapter module and each use-case module, built once per process by
lib.bootstrap.build(). Commands receive them as `cli.services`, routes as `req.services`, other code reads
`services.current()`. Only lib.ports may be imported here: a use-case module imported by the holder would join the
import cycle, so each field comes from a provider in lib/bootstrap.py."""
from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping


class Services:
    """A declared field (a class annotation) is its provider's result, resolved on first read and kept; nothing is set
    from outside."""

    def __init__(self, providers: Mapping[str, Callable[[], object]]) -> None:
        object.__setattr__(self, "_providers", dict(providers))

    def __getattr__(self, name: str) -> object:
        if name.startswith("_") or name not in fields():
            raise AttributeError(f"no service {name!r}")
        value = self._providers[name]()
        object.__setattr__(self, name, value)               # later reads find it without coming here
        return value

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"services are built by lib.bootstrap.build(), not set: {name}")


def fields() -> frozenset[str]:
    """The fields Services declares."""
    return frozenset(inspect.get_annotations(Services))


_current: Services | None = None


def install(s: Services) -> Services:
    global _current
    _current = s
    return s


def current() -> Services:
    if _current is None:
        raise RuntimeError("services not built: lib.bootstrap.build() runs first")
    return _current
