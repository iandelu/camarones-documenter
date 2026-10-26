"""Story text: a user story is three clauses — who (`Como … / As …`), what (`quiero … / I want …`) and why
(`para … / so that …`) — followed by free notes. This module reads that text into clauses, writes clauses back as text,
derives the title and the fingerprint, and gives the instant hints (`lint`): short, deterministic checks over the
words, no model call. The word lists live in `templates/board/{es,en}/story-lint.yaml` (JSON syntax, so the portal
reads the same files); `tests/fixtures/story_lint_cases.json` is the case table both implementations must satisfy."""
from __future__ import annotations

import hashlib, re
from functools import lru_cache
from pathlib import Path
from typing import Sequence, TypedDict

import yaml

TEMPLATES = Path(__file__).resolve().parents[1] / "templates" / "board"

TITLE_MAX = 80
TOO_LONG = 280                 # characters of the three clauses together
REPEAT_SHARE = 0.6             # share of the "so" content words already in the "want" above which it only restates it
CONTENT_MIN = 4                # letters a word needs to count as a content word

Clauses = TypedDict("Clauses", {"as_": str, "want": str, "so": str, "rest": str})
Hint = TypedDict("Hint", {"code": str, "field": str, "message": str})

_END = r"(?:\.(?=\s|$)|\n[ \t]*\n|\Z)"        # a story ends at a full stop that ends a sentence, a blank line, or the text
_PATTERNS = (
    re.compile(r"\A\s*Como\s+(?P<as_>.+?)\s*,?\s+quiero\s+(?P<want>.+?)\s*,?\s+para\s+(?P<so>.+?)\s*" + _END, re.I | re.S),
    re.compile(r"\A\s*As\s+(?:an?\s+)?(?P<as_>.+?)\s*,?\s+I\s+want\s+(?P<want>.+?)\s*,?\s+so\s+that\s+(?P<so>.+?)\s*" + _END,
               re.I | re.S),
)
_SHAPE = {"es": "Como {as_},\nquiero {want},\npara {so}.", "en": "As {as_},\nI want {want},\nso that {so}."}
_WORD = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*")
_ARTICLES = {"es": ("el", "la", "los", "las", "un", "una", "unos", "unas"), "en": ("a", "an", "the")}
_INFINITIVE = re.compile(r"(?:ar|er|ir)(?:se|me|te|lo|la|los|las|le|les|nos)?$")

MESSAGES = {
    ("es", "empty"): "Completa las tres partes: quién, qué y para qué.",
    ("en", "empty"): "Fill in all three parts: who, what and why.",
    ("es", "generic-role"): "El rol es demasiado genérico: nombra quién es en este proyecto (por ejemplo, quien mantiene el servicio).",
    ("en", "generic-role"): "The role is too generic: name who it is in this project (for example, the service owner).",
    ("es", "two-goals"): "Parecen dos objetivos en uno: separa la historia en dos.",
    ("en", "two-goals"): "This looks like two goals in one: split it into two stories.",
    ("es", "so-repeats-want"): "El «para» repite el «quiero»: explica el beneficio, no la acción.",
    ("en", "so-repeats-want"): "The \"so that\" repeats the \"I want\": state the benefit, not the action.",
    ("es", "too-long"): f"La historia supera los {TOO_LONG} caracteres: acórtala o divídela.",
    ("en", "too-long"): f"The story is over {TOO_LONG} characters: shorten it or split it.",
    ("es", "solution-in-want"): "El «quiero» describe una solución (botón, tabla, API…): describe la necesidad y deja la solución para las tareas.",
    ("en", "solution-in-want"): "The \"I want\" describes a solution (button, table, API…): describe the need and leave the solution to the tasks.",
    ("es", "no-footprint"): "No indica qué toca: añade al menos un archivo o página.",
    ("en", "no-footprint"): "It does not say what it touches: add at least one file or page.",
}


def _clean(s: str) -> str:
    return " ".join(s.split())


def _trim(s: str) -> str:
    return _clean(s).rstrip(".,").rstrip()


def parse(text: str, lang: str) -> Clauses:
    """Both languages' markers are read whatever `lang` is; `lang` only picks which is tried first.
    Text without the three clauses stays whole in `rest`."""
    order = _PATTERNS if lang == "es" else _PATTERNS[::-1]
    for pattern in order:
        m = pattern.match(text)
        if m:
            return {"as_": _trim(m["as_"]), "want": _trim(m["want"]), "so": _trim(m["so"]),
                    "rest": text[m.end():].strip()}
    return {"as_": "", "want": "", "so": "", "rest": text.strip()}


def compose(as_: str, want: str, so: str, lang: str) -> str:
    return _SHAPE["es" if lang == "es" else "en"].format(as_=_trim(as_), want=_trim(want), so=_trim(so))


def title_for(want: str) -> str:
    text = _clean(want)
    if len(text) > TITLE_MAX:
        cut = text[:TITLE_MAX]
        text = cut.rsplit(" ", 1)[0] if text[TITLE_MAX] != " " and " " in cut else cut
    text = text.rstrip(" .,;:")
    return text[:1].upper() + text[1:]


def fingerprint(as_: str, want: str, so: str) -> str:
    joined = "\n".join(_clean(part).lower() for part in (as_, want, so))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8]


@lru_cache(maxsize=None)
def _words(lang: str) -> dict:
    f = TEMPLATES / lang / "story-lint.yaml"
    if not f.exists():
        f = TEMPLATES / "en" / "story-lint.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8"))


def lint_words(lang: str) -> dict[str, list[str]]:
    """The word lists as loaded (a copy): `generic_roles`, `conjunctions`, `solution_words`, `observable_verbs`,
    `stopwords`, `verbs`."""
    return {key: list(value) for key, value in _words("es" if lang == "es" else "en").items()}


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _content(text: str, stop: set[str]) -> list[str]:
    return [w for w in _tokens(text) if len(w) >= CONTENT_MIN and w not in stop]


def _generic_role(as_: str, lang: str, words: dict) -> bool:
    tokens = _tokens(as_)
    while len(tokens) > 1 and tokens[0] in _ARTICLES[lang]:
        tokens = tokens[1:]
    return " ".join(tokens) in set(words["generic_roles"])


def _two_goals(want: str, lang: str, words: dict) -> bool:
    tokens = _tokens(want)
    conjunctions = set(words["conjunctions"])
    positions = [i for i, w in enumerate(tokens) if w in conjunctions and 0 < i < len(tokens) - 1]
    if lang == "es":
        return any(_INFINITIVE.search(w) and len(w) >= 4 for i in positions for w in tokens[i + 1:i + 3])
    stop, verbs = set(words["stopwords"]), set(words["verbs"])
    return (any(tokens[i + 1] not in stop for i in positions)
            and sum(1 for w in tokens if w in verbs) >= 2)


def _repeats(want: str, so: str, words: dict) -> bool:
    stop = set(words["stopwords"])
    mine = _content(so, stop)
    if not mine:
        return False
    theirs = set(_content(want, stop))
    return sum(1 for w in mine if w in theirs) / len(mine) > REPEAT_SHARE


def _has_solution(want: str, words: dict) -> bool:
    padded = f" {' '.join(_tokens(want))} "
    return any(f" {' '.join(_tokens(w))} " in padded for w in words["solution_words"])


def lint(as_: str, want: str, so: str, lang: str, *, touches: Sequence[str] = ()) -> list[Hint]:
    """Instant hints, in a fixed order: empty, generic-role, two-goals, so-repeats-want, too-long, solution-in-want,
    no-footprint. Each code appears at most once; checks over a blank clause are skipped."""
    lang = "es" if lang == "es" else "en"
    words = _words(lang)
    as_, want, so = _clean(as_), _clean(want), _clean(so)
    found: list[tuple[str, str]] = []
    blank = [name for name, value in (("as", as_), ("want", want), ("so", so)) if not value]
    if blank:
        found.append(("empty", blank[0]))
    if as_ and _generic_role(as_, lang, words):
        found.append(("generic-role", "as"))
    if want and _two_goals(want, lang, words):
        found.append(("two-goals", "want"))
    if want and so and _repeats(want, so, words):
        found.append(("so-repeats-want", "so"))
    if len(as_) + len(want) + len(so) > TOO_LONG:
        found.append(("too-long", "story"))
    if want and _has_solution(want, words):
        found.append(("solution-in-want", "want"))
    if not [t for t in touches if t]:
        found.append(("no-footprint", "touches"))
    return [{"code": code, "field": field, "message": MESSAGES[(lang, code)]} for code, field in found]
