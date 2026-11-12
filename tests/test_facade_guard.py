from __future__ import annotations

import sys
import types

import pytest

from fixtures.facade_guard import GuardedMonkeyPatch


def facade(monkeypatch, name="fake_facade"):
    mod = types.ModuleType(name)
    mod.__facade__, mod.__all__, mod.thing, mod.VERSIONS = "lib.core.fake", ["thing"], 1, {"kit": "0"}
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


def test_the_message_names_the_module_that_defines_the_name(monkeypatch):
    mod = facade(monkeypatch)

    def thing():
        pass

    thing.__module__ = "lib.core.process"
    mod.thing = thing
    mp = GuardedMonkeyPatch()
    with pytest.raises(AssertionError, match=r"fake_facade\.thing is re-exported by a facade: patch it in lib\.core\.process$"):
        mp.setattr(mod, "thing", 2)
    mp.undo()


def test_the_message_falls_back_to_the_facade_target(monkeypatch):
    mod = facade(monkeypatch)
    mp = GuardedMonkeyPatch()
    with pytest.raises(AssertionError, match=r"fake_facade\.thing is re-exported by a facade: patch it in lib\.core\.fake$"):
        mp.setattr(mod, "thing", 2)
    mp.undo()


def test_the_dotted_string_form_is_refused_too(monkeypatch):
    facade(monkeypatch)
    with pytest.raises(AssertionError, match="facade"):
        GuardedMonkeyPatch().setattr("fake_facade.thing", 2)


def test_keyword_arguments_are_refused_too(monkeypatch):
    mod = facade(monkeypatch)
    with pytest.raises(AssertionError, match="facade"):
        GuardedMonkeyPatch().setattr(target=mod, name="thing", value=2, raising=False)


def test_a_facade_s_own_data_can_be_patched(monkeypatch):
    mod = facade(monkeypatch)
    monkeypatch.setattr(mod, "VERSIONS", {"kit": "9"})
    assert mod.VERSIONS == {"kit": "9"}


def test_an_unresolvable_dotted_target_keeps_pytests_own_error():
    with pytest.raises(Exception) as err:
        GuardedMonkeyPatch().setattr("no_such_module_xyz.attr", 1)
    assert not isinstance(err.value, AssertionError)


def test_ordinary_modules_are_patched_as_usual(monkeypatch):
    mod = types.ModuleType("plain_mod")
    mod.thing = 1
    monkeypatch.setattr(mod, "thing", 2, raising=False)
    assert mod.thing == 2


def test_the_fixture_is_the_guarded_one(monkeypatch):
    assert isinstance(monkeypatch, GuardedMonkeyPatch)
