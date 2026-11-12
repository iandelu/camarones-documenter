from pathlib import Path

from conftest import KIT_DIR
from fixtures import archscan

TREE = {
    "lib/__init__.py": "",
    "lib/a.py": "from .pkg import b\nimport json\n",
    "lib/pkg/__init__.py": "from .c import Y\n",
    "lib/pkg/b.py": "from ..a import X\n\ndef f():\n    from . import c\n",
    "lib/pkg/c.py": "Y = 1\nfrom typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from . import Y as _\n",
    "camarones.py": "from lib import a\nfrom lib.pkg import c\nimport lib.pkg.b\n",
}


def build(tmp_path: Path, tree: dict[str, str]) -> Path:
    kit = tmp_path / "kit"
    for rel, text in tree.items():
        path = kit / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return kit


def test_modules_are_named_from_lib(tmp_path):
    assert set(archscan.modules(build(tmp_path, TREE))) == {"a", "pkg", "pkg.b", "pkg.c", "camarones"}


def test_edges_resolve_relative_absolute_and_nested_imports(tmp_path):
    mods = archscan.modules(build(tmp_path, TREE))
    assert archscan.edges(mods) == {
        ("a", "pkg.b"), ("pkg", "pkg.c"), ("pkg.b", "a"), ("pkg.b", "pkg.c"), ("pkg.c", "pkg"),
        ("camarones", "a"), ("camarones", "pkg.c"), ("camarones", "pkg.b")}


def test_largest_cycle_is_the_biggest_strongly_connected_component(tmp_path):
    mods = archscan.modules(build(tmp_path, TREE))
    assert archscan.largest_cycle(mods, archscan.edges(mods)) == 2
    assert archscan.largest_cycle(["x", "y"], {("x", "y")}) == 0


def test_imports_inside_functions_count_on_the_real_kit():
    found = archscan.edges(archscan.modules(KIT_DIR))
    assert ("camarones", "adr_cli") in found and ("serve", "adr_api") in found
