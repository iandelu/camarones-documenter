"""Story text: parse, compose, title, fingerprint and the instant lint hints (pure functions, no workspace)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

CASES = json.loads((Path(__file__).resolve().parent / "fixtures" / "story_lint_cases.json").read_text(encoding="utf-8"))


def test_parse_es_and_en(kit):
    from lib.stories import parse
    assert parse("Como dev,\nquiero X,\npara Y.\n\nNotas", "es") == {"as_": "dev", "want": "X", "so": "Y", "rest": "Notas"}
    one_line = {"as_": "dev", "want": "X", "so": "Y", "rest": ""}
    assert parse("As a dev, I want X so that Y", "en") == one_line
    assert parse("As a dev, I want X so that Y", "es") == one_line      # markers of both languages, whatever `lang`
    assert parse("Como dev, quiero X, para Y.", "en") == one_line
    assert parse("As an admin,\nI want X,\nso that Y.\n\nNotes", "en")["as_"] == "admin"


def test_parse_keeps_dots_inside_a_clause(kit):
    from lib.stories import parse
    assert parse("Como dev, quiero ver v1.2, para saber qué cambió. Notas", "es") == {
        "as_": "dev", "want": "ver v1.2", "so": "saber qué cambió", "rest": "Notas"}


def test_parse_without_clauses_keeps_everything_in_rest(kit):
    from lib.stories import parse
    assert parse("Arreglar el login", "es") == {"as_": "", "want": "", "so": "", "rest": "Arreglar el login"}
    assert parse("", "en") == {"as_": "", "want": "", "so": "", "rest": ""}


@pytest.mark.parametrize("lang,text", [
    ("es", "Como dev,\nquiero exportar a PDF,\npara compartirlo.\n\nNotas del equipo"),
    ("en", "As dev,\nI want to export to PDF,\nso that I can share it.\n\nTeam notes"),
])
def test_compose_round_trip(kit, lang, text):
    from lib.stories import compose, parse
    c = parse(text, lang)
    assert compose(c["as_"], c["want"], c["so"], lang) + "\n\n" + c["rest"] == text


def test_compose_strips_trailing_punctuation(kit):
    from lib.stories import compose
    assert compose("dev.", "X,", "Y.", "es") == "Como dev,\nquiero X,\npara Y."
    assert compose("dev", "X", "Y", "en") == "As dev,\nI want X,\nso that Y."


def test_title_for(kit):
    from lib.stories import title_for
    assert title_for("exportar una página a PDF") == "Exportar una página a PDF"
    assert title_for("  exportar a PDF. ") == "Exportar a PDF"
    long = " ".join(["documento"] * 12)                  # 119 characters
    title = title_for(long)
    assert len(title) <= 80 and title.endswith("documento") and title == " ".join(["Documento"] + ["documento"] * 7)
    assert title_for("x" * 100) == "X" + "x" * 79             # no word boundary: cut hard


def test_fingerprint_ignores_case_and_spacing(kit):
    from lib.stories import fingerprint
    assert fingerprint("Dev ", "x  y", "z") == fingerprint("dev", "X y", "Z")
    assert fingerprint("dev", "x y", "z") != fingerprint("dev", "x", "z")
    assert len(fingerprint("a", "b", "c")) == 8 and int(fingerprint("a", "b", "c"), 16) >= 0


def test_lint_words_serves_both_languages(kit):
    from lib.stories import lint_words
    for lang in ("es", "en"):
        words = lint_words(lang)
        for key in ("generic_roles", "conjunctions", "solution_words", "observable_verbs", "stopwords", "verbs"):
            assert isinstance(words[key], list)
    assert "usuario" in lint_words("es")["generic_roles"] and "user" in lint_words("en")["generic_roles"]


def test_case_table_covers_every_code_both_ways(kit):
    codes = {"empty", "generic-role", "two-goals", "so-repeats-want", "too-long", "solution-in-want", "no-footprint"}
    for lang in ("es", "en"):
        rows = [r for r in CASES if r["lang"] == lang]
        for code in codes:
            assert any(code in r["codes"] for r in rows), (lang, code, "positive")
            assert any(code not in r["codes"] for r in rows), (lang, code, "negative")


@pytest.mark.parametrize("row", CASES, ids=lambda r: f"{r['lang']}-{'+'.join(r['codes']) or 'clean'}-{r['want'][:18]}")
def test_lint_cases(kit, row):
    from lib.stories import lint
    hints = lint(row["as"], row["want"], row["so"], row["lang"], touches=row["touches"])
    assert [h["code"] for h in hints] == row["codes"]
    assert all(h["message"] and h["field"] for h in hints)


def test_lint_messages_follow_the_language(kit):
    from lib.stories import lint
    es = lint("usuario", "exportar", "compartir", "es", touches=["a:b"])[0]["message"]
    en = lint("user", "export", "share", "en", touches=["a:b"])[0]["message"]
    assert es != en and "rol" in es.lower()
