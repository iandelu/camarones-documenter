"""lib/core/yamlio: every YAML the kit reads goes through libyaml when PyYAML has it, about ten times faster than the
pure-Python parser, with the same result; writing stays with PyYAML's own emitter, since libyaml's escapes emoji."""
from __future__ import annotations

import importlib
import re

import pytest
import yaml

from conftest import KIT_DIR

DOCS = ["title: 🦐 Camarón\nx-sources: [api/a.py]\n", "a: 2026-11-12\nb: yes\nc: ~\nd: 1_000\n", "", "- a\n- {b: 1}\n",
        "x: &a 1\ny: *a\n", "key: |\n  lit\n  more\n", "a: 'it''s'\nb: \"\\U0001F990\"\n"]


@pytest.fixture
def yamlio():
    from lib.core import yamlio
    return importlib.reload(yamlio)


@pytest.mark.parametrize("doc", DOCS)
def test_reads_the_same_as_pyyaml(yamlio, doc):
    assert yamlio.safe_load(doc) == yaml.safe_load(doc)


@pytest.mark.parametrize("doc", ["a: [1, 2", "a:\n\tb: 1", "a: b: c", "a: *missing", "a: !!python/object:os.system x"])
def test_bad_yaml_raises_what_pyyaml_raises(yamlio, doc):
    with pytest.raises(yaml.YAMLError) as theirs:
        yaml.safe_load(doc)
    with pytest.raises(yaml.YAMLError) as ours:
        yamlio.safe_load(doc)
    assert type(ours.value) is type(theirs.value)


def test_reads_with_libyaml_when_pyyaml_has_it(yamlio):
    assert yamlio.Loader is (yaml.CSafeLoader if yaml.__with_libyaml__ else yaml.SafeLoader)


def test_without_libyaml_it_reads_with_pure_python(yamlio, monkeypatch):
    monkeypatch.delattr(yaml, "CSafeLoader")
    assert importlib.reload(yamlio).Loader is yaml.SafeLoader
    assert yamlio.safe_load("a: 1\n") == {"a": 1}


def test_reads_every_document_of_a_stream(yamlio):
    assert list(yamlio.safe_load_all("a: 1\n---\nb: 🦐\n")) == [{"a": 1}, {"b": "🦐"}]


def test_reads_a_file_object(yamlio, tmp_path):
    f = tmp_path / "x.yaml"
    f.write_text("a: ñandú\n", encoding="utf-8")
    with f.open(encoding="utf-8") as fh:
        assert yamlio.safe_load(fh) == {"a": "ñandú"}


def test_the_kit_reads_yaml_only_through_yamlio():
    """A direct yaml.safe_load is the slow parser again."""
    slow = re.compile(r"\byaml\.(safe_load|load|safe_load_all|load_all)\(")
    found = [f"{p.relative_to(KIT_DIR).as_posix()}:{n}"
             for p in sorted((KIT_DIR / "lib").rglob("*.py")) + [KIT_DIR / "camarones.py"]
             if p.name != "yamlio.py"
             for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if slow.search(line)]
    assert found == []
