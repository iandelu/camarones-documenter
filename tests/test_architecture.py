import ast
from conftest import KIT_DIR
from fixtures import archscan

SPEC = "docs/superpowers/specs/2026-11-12-hexagonal-refactor-design.md"


def scan():
    mods = archscan.modules(KIT_DIR)
    return mods, archscan.edges(mods), archscan.load_layers(), archscan.load_allowlist()


def edge_lines(pairs):
    return "\n".join(f'  - "{a} -> {b}"' for a, b in sorted(pairs))


def test_every_module_has_a_layer():
    mods, _, table, _ = scan()
    assert [m for m in mods if archscan.layer_of(m, table) is None] == []


def test_every_layer_is_known():
    _, _, table, _ = scan()
    assert set(table.values()) <= set(archscan.ALLOWED)


def test_no_new_layer_violation():
    _, found, table, allow = scan()
    allowed = set(allow["violations"])
    new = {(a, b) for a, b in archscan.violations(found, table) if f"{a} -> {b}" not in allowed}
    assert not new, (
        f"{len(new)} import(s) cross the layer rule ({SPEC} §2). Fix the import, "
        f"or (a debt you accept) add to allowlist.yaml `violations`:\n{edge_lines(new)}")


def test_the_allowlist_holds_no_fixed_debt():
    _, found, table, allow = scan()
    today = {f"{a} -> {b}" for a, b in archscan.violations(found, table)}
    fixed = sorted(set(allow["violations"]) - today)
    assert not fixed, "These debts are paid; remove these lines from allowlist.yaml `violations`:\n" + "\n".join(
        f'  - "{e}"' for e in fixed)


def test_core_imports_only_core():
    _, found, table, _ = scan()
    bad = {(a, b) for a, b in found
           if archscan.layer_of(a, table) == "core" and archscan.layer_of(b, table) != "core"}
    assert not bad, f"core may import only core ({SPEC} §2):\n{edge_lines(bad)}"


def test_the_core_folder_imports_only_the_core_folder():
    _, found, _, _ = scan()
    bad = archscan.core_escapes(found)
    assert not bad, f"lib/core imports nothing outside lib/core ({SPEC} §2); no allowlist applies:\n{edge_lines(bad)}"


def test_the_largest_cycle_never_grows():
    mods, found, _, allow = scan()
    size = archscan.largest_cycle(mods, found)
    want = allow["largest_cycle"]
    assert size <= want, f"the largest import cycle grew to {size} modules (allowlist.yaml says {want})"
    assert size == want, f"the largest import cycle shrank: lower largest_cycle to {size} in allowlist.yaml"


def test_big_files_are_listed():
    mods, _, _, allow = scan()
    big = {m for m, p in mods.items() if archscan.line_count(p) > archscan.MAX_LINES}
    listed = set(allow["oversize"])
    assert big == listed, (
        f"files over {archscan.MAX_LINES} lines differ from allowlist.yaml `oversize`.\n"
        f"Add (new big files, or split them instead):\n" + "\n".join(f"  - {m}" for m in sorted(big - listed))
        + "\nRemove (now small enough):\n" + "\n".join(f"  - {m}" for m in sorted(listed - big)))


def test_every_exact_layer_key_is_a_module():
    mods, _, table, _ = scan()
    stale = sorted(k for k in table if not k.endswith(".*") and k != "bootstrap" and k not in mods)
    assert not stale, f"layers.yaml names modules that no longer exist; remove them: {stale}"


def _facade_problems(tree: ast.Module) -> list[str]:
    bound: set[str] = set()
    problems: list[str] = []
    all_node = None
    is_facade = False
    for i, node in enumerate(tree.body):
        if i == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            continue
        if isinstance(node, ast.ImportFrom):
            bound |= {a.asname or a.name for a in node.names}
        elif isinstance(node, ast.Import):
            bound |= {a.asname or a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) for t in node.targets):
            names = [t.id for t in node.targets]
            try:
                ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError):
                problems.append(f"line {node.lineno}: {', '.join(names)} is not a literal")
            is_facade = is_facade or "__facade__" in names
            if "__all__" in names:
                all_node = node
        else:
            problems.append(f"line {node.lineno}: {type(node).__name__} is not an import, a literal or the docstring")
    if not is_facade:
        return []
    if all_node is None:
        return problems + ["no __all__"]
    try:
        listed = ast.literal_eval(all_node.value)
    except (ValueError, TypeError, SyntaxError):
        return problems + ["__all__ is not a literal"]
    if not isinstance(listed, (list, tuple)) or not all(isinstance(n, str) for n in listed):
        return problems + ["__all__ must be a list or tuple of strings"]
    problems += [f"__all__ lists {n}, which no import binds" for n in listed if n not in bound]
    return problems + [f"{n} is imported but not listed in __all__" for n in sorted(bound - set(listed))]


def test_facades_hold_only_imports_and_literals():
    bad = {}
    for name, path in archscan.modules(KIT_DIR).items():
        found = _facade_problems(ast.parse(path.read_text(encoding="utf-8")))
        if found:
            bad[name] = found
    assert not bad, f"a facade holds only a docstring, imports and literals, and __all__ lists imported names: {bad}"


def test_the_facade_shape_check_sees_a_bad_facade():
    src = 'import os\n__facade__ = "x"\n__all__ = ["os", "gone"]\ndef f(): pass\n'
    found = _facade_problems(ast.parse(src))
    assert any("FunctionDef" in p for p in found) and any("gone" in p for p in found)
    assert _facade_problems(ast.parse("def f(): pass\n")) == []


def test_a_facade_that_imports_a_name_it_does_not_list_fails_the_shape_check():
    src = 'import os\nfrom json import dumps\n__facade__ = "x"\n__all__ = ["os"]\n'
    assert any("dumps is imported but not listed" in p for p in _facade_problems(ast.parse(src)))
    ok = 'from __future__ import annotations\nimport os\n__facade__ = "x"\n__all__ = ["os"]\n'
    assert _facade_problems(ast.parse(ok)) == []
