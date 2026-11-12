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
