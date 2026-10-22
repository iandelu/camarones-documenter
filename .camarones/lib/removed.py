"""What was removed on purpose (X9): docs/overview/removed.md, one row per capability, endpoint, page or component
taken out deliberately, with why and the decision behind it, so agents (and people) do not bring it back."""
from __future__ import annotations

import datetime as dt

from .common import DOCS, rel_file
from . import docs

LOGICAL = "overview/removed.md"
PAGE = DOCS / LOGICAL
PAGES = {
    "en": {"head": "| What | When | Why | Decision |\n|---|---|---|---|\n", "title": "Removed on purpose",
           "description": "Capabilities, endpoints, pages and components removed deliberately, with why and the "
                          "decision behind each, so they are not recreated by mistake.",
           "body": """# Removed on purpose

> **TL;DR:** What was taken out of the system deliberately, and why. Before adding something back, read its row and
> the decision it links: if the reason still holds, do not recreate it.

## Removed on purpose

{table}
## How to add a row

Run `camaron removed add "<what>" --why "<why>" [--decision decisions/NNNN-x.md]` when a capability, endpoint, page or
component is removed on purpose.
"""},
    "es": {"head": "| Qué | Cuándo | Por qué | Decisión |\n|---|---|---|---|\n", "title": "Quitado a propósito",
           "description": "Funciones, endpoints, páginas y componentes quitados a propósito, con el motivo y la "
                          "decisión de cada uno, para no volver a crearlos por error.",
           "body": """# Quitado a propósito

> **TL;DR:** Lo que se quitó del sistema a propósito, y por qué. Antes de volver a añadir algo, lee su fila y la
> decisión que enlaza: si el motivo sigue vigente, no lo vuelvas a crear.

## Quitado a propósito

{table}
## Cómo añadir una fila

Ejecuta `camaron removed add "<qué>" --why "<por qué>" [--decision decisions/NNNN-x.md]` cuando se quite a propósito una
función, un endpoint, una página o un componente.
"""},
}


def _cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ").strip()


def _insert(text: str, head: str, row: str) -> str:
    if head not in text:
        return text.rstrip("\n") + "\n\n" + head + row
    end = text.index(head) + len(head)
    while end < len(text) and text[end] == "|":
        end = text.index("\n", end) + 1
    return text[:end] + row + text[end:]


def _write(f, lang: str, row: str, extra: dict) -> None:
    page = PAGES[lang]
    if f.exists():
        text = _insert(f.read_text(encoding="utf-8"), page["head"], row)
    else:
        fm = {"type": "overview", "title": page["title"], "description": page["description"], "tags": ["decisions"],
              "x-owner": "ai", **extra}
        text = docs.join_fm(fm, page["body"].format(table=page["head"] + row))
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8", newline="\n")


def add(what: str, why: str, decision: str = "", when: str | None = None) -> str:
    when = when or dt.date.today().isoformat()
    link = ""
    if decision:
        target = decision.removeprefix("docs/")
        link = f"[{target.rsplit('/', 1)[-1].removesuffix('.md')}](../{target})"
    row = f"| {_cell(what)} | {when} | {_cell(why)} | {link} |\n"
    _write(PAGE, "en", row, {})
    _, body = docs.split_fm(PAGE.read_text(encoding="utf-8"))
    for lang in docs.workspace()["project"].get("translations", []):
        tf = DOCS / "i18n" / lang / LOGICAL
        if lang not in PAGES or (tf.exists() and not _ours(tf)):
            continue
        _write(tf, lang, row, {})
        fm, tbody = docs.split_fm(tf.read_text(encoding="utf-8"))
        fm["x-translation-of"] = {"path": LOGICAL, "lang": lang, "body_sha": docs.body_sha(body)}
        tf.write_text(docs.join_fm(fm, tbody), encoding="utf-8", newline="\n")
    return rel_file(PAGE)


def _ours(f) -> bool:
    """A translation someone rewrote by hand is theirs: the kit stops touching it."""
    fm, _ = docs.split_fm(f.read_text(encoding="utf-8"))
    return fm.get("x-owner") != "human" and not fm.get("x-confirmed")
