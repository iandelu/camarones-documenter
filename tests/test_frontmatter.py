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


def windows_newlines(monkeypatch):
    """`Path.write_text` as it behaves on Windows: a text write that names no newline turns each `\n` into `\r\n`."""
    from pathlib import Path
    real = Path.write_text

    def write_text(self, data, encoding=None, errors=None, newline=None):
        return real(self, data, encoding=encoding, errors=errors, newline="\r\n" if newline is None else newline)
    monkeypatch.setattr(Path, "write_text", write_text)


def test_confirming_a_page_writes_unix_line_endings_on_every_os(kit, monkeypatch):
    f = write(kit, "domain/glossary.md", GLOSSARY)
    windows_newlines(monkeypatch)
    kit.docs.confirm([str(f)], "Test")
    raw = f.read_bytes()
    assert b"\r\n" not in raw and b"x-confirmed:" in raw


def test_marking_a_translation_writes_unix_line_endings_on_every_os(kit, monkeypatch):
    write(kit, "domain/glossary.md", GLOSSARY)
    f = write(kit, "i18n/es/domain/glossary.md", "---\ntitle: Glosario\n---\n# Glosario\n")
    windows_newlines(monkeypatch)
    kit.docs.translated([str(f)])
    raw = f.read_bytes()
    assert b"\r\n" not in raw and b"x-translation-of:" in raw
