"""A monkeypatch that refuses to patch a name a facade only re-exports: the patch would land on the facade while the
code under test reads the name from the module that really defines it, so the test would pass for the wrong reason."""
from __future__ import annotations

import importlib

import pytest


def _owner_and_name(target, args, kwargs):
    if isinstance(target, str):
        parts = target.split(".")
        name = parts[-1]
        for i in range(len(parts) - 1, 0, -1):
            try:
                owner = importlib.import_module(".".join(parts[:i]))
            except ImportError:
                continue
            for part in parts[i:-1]:
                owner = getattr(owner, part)
            return owner, name
        raise ImportError(target)
    name = args[0] if args else kwargs.get("name")
    return target, name


class GuardedMonkeyPatch(pytest.MonkeyPatch):
    def setattr(self, target, *args, **kwargs):
        if not args and "target" in kwargs:
            target = kwargs["target"]
        try:
            owner, name = _owner_and_name(target, args, kwargs)
        except Exception:
            owner = name = None
        facade = getattr(owner, "__facade__", None) if owner is not None else None
        if facade and isinstance(name, str) and name in getattr(owner, "__all__", ()):
            home = getattr(getattr(owner, name, None), "__module__", None)
            where = home if isinstance(home, str) and home.startswith("lib.") else facade
            raise AssertionError(f"{owner.__name__}.{name} is re-exported by a facade: patch it in {where}")
        return super().setattr(target, *args, **kwargs)
