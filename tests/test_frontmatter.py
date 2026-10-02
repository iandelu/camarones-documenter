"""Frontmatter written by agents or by hand is not always valid YAML. One bad doc must never take down the dashboard,
the portal or `check`: common slips are read anyway, the rest is reported as a doc error."""
from __future__ import annotations

GLOSSARY = ("---\ntype: glossary\ntitle: Glosario\n"
            "description: Lenguaje ubicuo de chub: término, definición, nombre en el código.\n"
            "tags: [domain, glossary]\nx-sources:\n  - api:pom.xml\n---\n# Glosario\n")


def write(kit, rel: str, text: str):
    f = kit.root / "docs" / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")
    return f


def test_unquoted_colon_in_a_value_is_read(kit):
    fm, body = kit.docs.split_fm(GLOSSARY)
    assert fm["description"] == "Lenguaje ubicuo de chub: término, definición, nombre en el código."
    assert fm["tags"] == ["domain", "glossary"] and fm["x-sources"] == ["api:pom.xml"]
    assert body == "# Glosario\n"


def test_broken_frontmatter_never_leaks_into_the_body(kit):
    fm, body = kit.docs.split_fm("---\ntitle: [unclosed\n  - : :\n---\n# Doc\n")
    assert fm == {} and body == "# Doc\n"


def test_collect_survives_a_broken_translation(kit):
    write(kit, "domain/glossary.md", "---\ntitle: Glossary\n---\n# Glossary\n")
    write(kit, "i18n/es/domain/glossary.md", "---\ntitle: [unclosed\n  - : :\n---\n# Glosario\n")
    rows = {r["path"]: r for r in kit.docs.collect()}
    assert rows["domain/glossary.md"]["i18n"]["es"] == "outdated"


def test_check_reports_unreadable_frontmatter(kit):
    write(kit, "broken.md", "---\ntitle: [unclosed\n  - : :\n---\n# Broken\n")
    errors, _ = kit.docs.check()
    assert any("broken.md" in e and "invalid frontmatter" in e for e in errors)
