"""Story text: a user story is three clauses — who (`Como … / As …`), what (`quiero … / I want …`) and why
(`para … / so that …`) — followed by free notes. This module reads that text into clauses, writes clauses back as text,
derives the title and the fingerprint, and gives the instant hints (`lint`): short, deterministic checks over the
words, no model call. The word lists live in `templates/board/{es,en}/story-lint.yaml` (JSON syntax, so the portal
reads the same files); `tests/fixtures/story_lint_cases.json` is the case table both implementations must satisfy.

Then the review a story gets before it is saved, all by rules over the board's index (no model call): `invest` gives
the INVEST verdict letter by letter, `split` proposes subtasks from `templates/board/{es,en}/split.yaml` (one change
task per code-map group, groups that use each other merged, one docs task per page in or citing the footprint), and
`analyze` (what the story wizard calls on every keystroke) returns hints, verdict, tasks, waves and conflicts at once.
Nothing here writes a file."""
from __future__ import annotations

import hashlib, logging, re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Sequence, TypedDict

import yaml

from . import codemap, docs
from .common import ROOT
from .kanban import deps, index
from .kanban.state import id_key

log = logging.getLogger("camaron.stories")

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


def _cut(text: str, limit: int) -> str:
    """`text` on one line, cut to `limit` characters on a word boundary, without trailing punctuation."""
    text = _clean(text)
    if len(text) > limit:
        cut = text[:limit]
        text = cut.rsplit(" ", 1)[0] if text[limit] != " " and " " in cut else cut
    return text.rstrip(" .,;:")


def title_for(want: str) -> str:
    text = _cut(want, TITLE_MAX)
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


# ── INVEST (spec §4.3) ───────────────────────────────────────────────────────────────────────────────────────────

SMALL = {"groups": 3, "files": 15, "repos": 2}    # defaults of workspace.yaml → stories.small
TASK_TITLE_MAX = 120
DOCS = index.DOCS_REPO + ":"
_GIVEN_WHEN_THEN = (({"dado", "dada", "dados", "dadas"}, {"cuando"}, {"entonces"}), ({"given"}, {"when"}, {"then"}))

Story = TypedDict("Story", {"id": "str | None", "as_": str, "want": str, "so": str, "criteria": "list[str]",
                            "touches": "list[str]", "epic": "str | None", "priority": "str | None"})

INVEST_MESSAGES = {
    ("es", "I-ok"): "No comparte archivos con otras historias abiertas ni espera a ninguna.",
    ("en", "I-ok"): "It shares no files with other open stories and waits for none.",
    ("es", "I-overlaps"): "Comparte archivos con {ids}: coordínalas o fusiónalas.",
    ("en", "I-overlaps"): "It shares files with {ids}: coordinate or merge them.",
    ("es", "I-waits"): "Depende de {ids}, aún sin terminar.",
    ("en", "I-waits"): "It depends on {ids}, not done yet.",
    ("es", "N-ok"): "Describe la necesidad, no la solución.",
    ("en", "N-ok"): "It describes the need, not the solution.",
    ("es", "N-fail"): "El «quiero» fija una solución: deja margen para negociarla.",
    ("en", "N-fail"): "The \"I want\" fixes a solution: leave room to negotiate it.",
    ("es", "V-ok"): "El «para» explica el beneficio.",
    ("en", "V-ok"): "The \"so that\" states the benefit.",
    ("es", "V-missing"): "Falta el «para»: di qué beneficio aporta.",
    ("en", "V-missing"): "The \"so that\" is missing: say what benefit it brings.",
    ("es", "V-repeats"): "El «para» repite el «quiero»: explica el beneficio.",
    ("en", "V-repeats"): "The \"so that\" repeats the \"I want\": state the benefit.",
    ("es", "E-ok"): "Tiene archivos y criterios: se puede estimar.",
    ("en", "E-ok"): "It has files and criteria: it can be estimated.",
    ("es", "E-no-footprint"): "Sin nada en «Toca» no se puede estimar.",
    ("en", "E-no-footprint"): "With nothing in \"Touches\" it cannot be estimated.",
    ("es", "E-no-criteria"): "Añade al menos un criterio de aceptación para estimarla.",
    ("en", "E-no-criteria"): "Add at least one acceptance criterion to estimate it.",
    ("es", "S-ok"): "Pequeña: {groups} grupos, {files} archivos, {repos} repos.",
    ("en", "S-ok"): "Small: {groups} groups, {files} files, {repos} repos.",
    ("es", "S-fail"): "Grande: {groups} grupos, {files} archivos, {repos} repos (máximo {max_groups}, {max_files}, "
                      "{max_repos}). Pártela por grupo.",
    ("en", "S-fail"): "Large: {groups} groups, {files} files, {repos} repos (at most {max_groups}, {max_files}, "
                      "{max_repos}). Split it by group.",
    ("es", "T-ok"): "Cada criterio se puede comprobar.",
    ("en", "T-ok"): "Every criterion can be checked.",
    ("es", "T-none"): "Sin criterios de aceptación no se puede probar.",
    ("en", "T-none"): "Without acceptance criteria it cannot be tested.",
    ("es", "T-vague"): "Criterios sin «Dado/cuando/entonces» ni un resultado observable: {refs}.",
    ("en", "T-vague"): "Criteria with no Given/when/then and no observable result: {refs}.",
}


def _lang(lang: str) -> str:
    return "es" if lang == "es" else "en"


def _touches(raw: Sequence[str]) -> list[str]:
    """Valid `repo:path` entries, normalised, sorted and unique; anything else is dropped (this runs while typing)."""
    out = set()
    for ref in raw or ():
        try:
            t = deps.norm_touch(ref, fold=False)
        except (ValueError, AttributeError):
            continue
        if t.partition(":")[2]:
            out.add(t)
    return sorted(out)


def _repo(touch: str) -> str:
    return touch.partition(":")[0]


def _group(touch: str, groups: dict[str, str]) -> str:
    path = touch.partition(":")[2]
    return groups.get(touch) or PurePosixPath(path).parent.name or _repo(touch)


def _small() -> dict[str, int]:
    """`workspace.yaml → stories.small` over the defaults; only positive whole numbers override."""
    section = docs.workspace().get("stories")
    given = section.get("small") if isinstance(section, dict) else None
    given = given if isinstance(given, dict) else {}
    ok = lambda v: isinstance(v, int) and not isinstance(v, bool) and v > 0     # noqa: E731
    return {k: given[k] if ok(given.get(k)) else v for k, v in SMALL.items()}


def _done(node: deps.Node) -> bool:
    return node["status"] == "Done" or bool(node.get("archived"))


def _observable(tokens: list[str], verbs: list[str], lang: str) -> bool:
    """A word-list match that tolerates inflection: an English verb as a prefix (sees, listed), a Spanish one by its
    stem (exporta, recibe); short Spanish verbs (ver, leer) only as they are."""
    for verb in verbs:
        exact = lang == "es" and len(verb) < 5
        stem = verb[:-2] if lang == "es" and not exact else verb
        if any(tok == verb if exact else tok.startswith(stem) for tok in tokens):
            return True
    return False


def _testable(criterion: str) -> bool:
    """Given/when/then (Dado/cuando/entonces) or an observable verb, in either language."""
    tokens = _tokens(criterion)
    present = set(tokens)
    if any(all(present & words for words in markers) for markers in _GIVEN_WHEN_THEN):
        return True
    return any(_observable(tokens, _words(lang)["observable_verbs"], lang) for lang in ("es", "en"))


def _letter(ok: bool, lang: str, code: str, data: dict | None = None, **fields) -> dict:
    return {"ok": ok, "reason": INVEST_MESSAGES[(lang, code)].format(**fields), "data": data or {}}


def _node(item_id: str, touches: list[str], *, priority: str | None = None, needs: Sequence[str] = ()) -> deps.Node:
    return {"id": item_id, "status": "Backlog", "priority": priority, "touches": touches,
            "repos": sorted({_repo(t) for t in touches}), "deps": list(needs), "archived": False}


def invest(story: Story, board: list[deps.Node], *, groups: dict[str, str], lang: str) -> dict:
    """The INVEST verdict by rules (spec §4.3). `board` holds the board's stories (the caller leaves other item types
    out); the story itself may be among them, which gives its dependencies. `groups` maps touches to code-map groups
    (`index.groups`); a file missing from it is grouped by its folder. Same input, same output."""
    lang = _lang(lang)
    touches = _touches(story["touches"])
    codes = {h["code"] for h in lint(story["as_"], story["want"], story["so"], lang, touches=touches)}
    criteria = [c for c in (_clean(c) for c in story["criteria"]) if c]
    sid = (story.get("id") or "").strip().upper()
    letters: dict[str, dict] = {}

    overlaps = [{"id": c["id"], "files": c["files"]} for c in deps.conflicts(_node(sid, touches), board)]
    by_id = {n["id"]: n for n in board}
    mine = by_id.get(sid) if sid else None
    waits = sorted({d for d in (mine["deps"] if mine else ()) if d != sid and d in by_id and not _done(by_id[d])},
                   key=id_key)
    data = {"overlaps": overlaps, "waits": waits}
    if overlaps:
        letters["I"] = _letter(False, lang, "I-overlaps", data, ids=", ".join(o["id"] for o in overlaps))
    elif waits:
        letters["I"] = _letter(False, lang, "I-waits", data, ids=", ".join(waits))
    else:
        letters["I"] = _letter(True, lang, "I-ok", data)

    ok = "solution-in-want" not in codes
    letters["N"] = _letter(ok, lang, "N-ok" if ok else "N-fail")

    code = "V-missing" if not _clean(story["so"]) else "V-repeats" if "so-repeats-want" in codes else "V-ok"
    letters["V"] = _letter(code == "V-ok", lang, code)

    code = "E-no-footprint" if not touches else "E-no-criteria" if not criteria else "E-ok"
    letters["E"] = _letter(code == "E-ok", lang, code)

    limits = _small()
    code_files = [t for t in touches if not t.startswith(DOCS)]       # pages are counted apart, not as size
    by_group: dict[tuple[str, str], list[str]] = defaultdict(list)
    for t in code_files:
        by_group[(_repo(t), _group(t, groups))].append(t)
    counts = {"groups": len(by_group), "files": len(code_files), "repos": len({_repo(t) for t in code_files})}
    fields = {**counts, **{f"max_{k}": v for k, v in limits.items()}}
    if all(counts[k] <= limits[k] for k in limits):
        letters["S"] = _letter(True, lang, "S-ok", dict(counts), **fields)
    else:
        split_by = [sorted(by_group[g]) for g in sorted(by_group)]
        letters["S"] = _letter(False, lang, "S-fail", {**counts, "split_by_group": split_by}, **fields)

    vague = [f"#{i}" for i, c in enumerate(criteria, 1) if not _testable(c)]
    if not criteria:
        letters["T"] = _letter(False, lang, "T-none", {"vague": []})
    else:
        letters["T"] = _letter(not vague, lang, "T-vague" if vague else "T-ok", {"vague": vague},
                               refs=", ".join(vague))

    failed = sum(not v["ok"] for v in letters.values())
    verdict = "poor" if "empty" in codes or failed >= 3 else "improve" if failed else "good"
    return {"verdict": verdict, "letters": {k: letters[k] for k in "INVEST"}}


# ── subtasks by template (spec §4.4) and their order (§4.5) ─────────────────────────────────────────────────────

class _Proposal(TypedDict):
    key: str                # "change:<repo>:<group>[+<group>…]" or "docs:<page touch>": stable while the files stay
    kind: str               # "change" | "docs"
    title: str
    group: str
    touches: list[str]
    criteria: list[str]
    deps: list[str]         # derived: keys of other proposals in the list, ids of board items
    conflicts: list[dict]   # derived: deps.conflicts against the board's open leaf items
    wave: int               # derived: 0-based among the proposals; -1 while there is a cycle or a duplicate key
    edited: bool
    added: list[str]        # the person's: dependencies (keys or board ids) on top of the derived ones
    dropped: list[str]      # the person's: dependencies taken out of the derived ones


class Proposal(_Proposal, total=False):
    outside: list[str]      # an edited task's files that are not in the story's footprint


class _Blank(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@lru_cache(maxsize=None)
def _kit_split(lang: str) -> dict:
    f = TEMPLATES / lang / "split.yaml"
    if not f.exists():
        f = TEMPLATES / "en" / "split.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8"))


def split_templates(lang: str) -> dict[str, str]:
    """The kit's templates for `lang` with the project's `.camarones/board/split.yaml` merged over them key by key
    (only known keys holding text; an unreadable override is ignored with a warning)."""
    merged = dict(_kit_split(_lang(lang)))
    f = ROOT / ".camarones" / "board" / "split.yaml"
    if f.is_file():
        try:
            mine = yaml.safe_load(f.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
            log.warning("ignoring %s: %s", f, e)
            mine = None
        if isinstance(mine, dict):
            merged.update({k: v for k, v in mine.items() if k in merged and isinstance(v, str)})
    return merged


def _fill(templates: dict[str, str], lang: str, name: str, **fields: str) -> str:
    """A template with its fields; a project template that does not format falls back to the kit's."""
    for template in (templates[name], _kit_split(_lang(lang))[name]):
        try:
            return template.format_map(_Blank(fields))
        except (ValueError, IndexError, AttributeError, KeyError):
            continue
    return ""


def _proposal(key: str, kind: str, title: str, group: str, touches: list[str], criteria: list[str]) -> Proposal:
    return {"key": key, "kind": kind, "title": _cut(title, TASK_TITLE_MAX), "group": group, "touches": touches,
            "criteria": criteria, "deps": [], "conflicts": [], "wave": 0, "edited": False, "added": [],
            "dropped": []}


def _code(touches: list[str]) -> list[str]:
    return [t for t in touches if not t.startswith(DOCS)]


def _pages(conn, touches: list[str]) -> list[str]:
    """The pages a story's docs tasks are for: those in its footprint and those citing its code files."""
    return sorted({t for t in touches if t.startswith(DOCS)} | set(index.pages_citing(conn, _code(touches))))


def _proposals(story: Story, conn, lang: str) -> list[Proposal]:
    """Steps 1–4 of spec §4.4: the tasks, without dependencies, conflicts or waves yet."""
    templates = split_templates(lang)
    touches = _touches(story["touches"])
    code = _code(touches)
    grp = index.groups(conn, code)
    name = {t: f"{_repo(t)}:{_group(t, grp)}" for t in code}          # a group belongs to one repo
    members: dict[str, list[str]] = defaultdict(list)
    for t in code:
        members[name[t]].append(t)
    uses: dict[str, set[str]] = {g: set() for g in members}
    for src, dst in index.edges(conn, code):
        if name[src] != name[dst]:
            uses[name[src]].add(name[dst])
    merged = {g: [g] for g in members}
    for comp in deps.sccs({g: sorted(u) for g, u in uses.items()}):  # groups that use each other: one task
        for g in comp:
            merged[g] = comp
    want = _trim(story["want"])
    n_criteria = len([c for c in story["criteria"] if _clean(c)])
    refs = ", ".join(f"#{i}" for i in range(1, n_criteria + 1))
    out: list[Proposal] = []
    for comp in sorted({tuple(c) for c in merged.values()}):
        labels = [g.partition(":")[2] for g in comp]
        group = " + ".join(labels)
        title = _fill(templates, lang, "change_title", group=group, groups=", ".join(labels), want=want)
        out.append(_proposal(f"change:{_repo(comp[0])}:{'+'.join(labels)}", "change", title, group,
                             sorted(t for g in comp for t in members[g]),
                             [_fill(templates, lang, "change_criterion", refs=refs)] if refs else []))
    for page in _pages(conn, touches):
        title = index.page_title(conn, page) or PurePosixPath(page.partition(":")[2]).stem
        out.append(_proposal(f"docs:{page}", "docs", _fill(templates, lang, "docs_title", page=title),
                             index.DOCS_GROUP, [page], []))
    return out


def _code_groups(groups: dict[str, str]) -> dict[str, str]:
    """touch -> `repo:group` for code files only: the same label in two repos is two groups, and doc pages share none."""
    return {t: f"{_repo(t)}:{g}" for t, g in groups.items() if not t.startswith(DOCS)}


def _settle(story: Story, tasks: list[Proposal], conn) -> dict:
    """Spec §4.5 on the tasks. Each task's `deps` = (code order: provider first, docs after the code they cite ∪ the
    In Progress items it shares files with ∪ `added`) − `dropped`. Conflicts are with the board's open leaf items (not
    the story's own children). Waves are left empty while the tasks' dependencies have a cycle or two tasks share a
    key. Returns `{tasks (by wave, then group), waves (keys), cycle, duplicates, unknown_deps}`."""
    sid = (story.get("id") or "").strip().upper()
    count: dict[str, int] = defaultdict(int)
    files: dict[str, set[str]] = defaultdict(set)
    for t in tasks:
        count[t["key"]] += 1
        files[t["key"]] |= set(t["touches"])
    duplicates = sorted(k for k, n in count.items() if n > 1)
    board = index.nodes(conn)
    known = {n["id"] for n in board}
    grouping = deps.containers(board)
    leaves = [n for n in board
              if not _done(n) and n["id"] not in grouping and n["id"] != sid and n["id"] not in count
              and not (sid and (n.get("parent") or "").strip().upper() == sid)]
    status = {n["id"]: n["status"] for n in leaves}
    mine = sorted(set().union(*files.values()))
    order = deps.order({k: sorted(v) for k, v in files.items()}, index.edges(conn, mine), index.cites(conn, mine))
    near = _code_groups(index.groups(conn, mine + [f for n in leaves for f in n["touches"]]))
    unknown: dict[str, list[str]] = {}
    for t in tasks:
        t["conflicts"] = deps.conflicts(_node(t["key"], t["touches"]), leaves, groups=near)
        waiting = {c["id"] for c in t["conflicts"] if c["kind"] == "conflict" and status[c["id"]] == "In Progress"}
        added = set()
        for ref in t["added"]:
            if ref in count or ref in known:
                added.add(ref)
            elif ref.upper() in known:
                added.add(ref.upper())
            elif ref not in unknown.setdefault(t["key"], []):
                unknown[t["key"]].append(ref)
        dropped = set(t["dropped"]) | {d.upper() for d in t["dropped"]} | {t["key"]}
        t["deps"] = sorted((set(order[t["key"]]) | waiting | added) - dropped, key=id_key)
    unknown = {k: v for k, v in sorted(unknown.items()) if v}

    cycles = deps.sccs({k: sorted({d for t in tasks if t["key"] == k for d in t["deps"] if d in count})
                        for k in count})
    out = {"cycle": cycles[0] if cycles else [], "duplicates": duplicates, "unknown_deps": unknown}
    if cycles or duplicates:
        for t in tasks:
            t["wave"] = -1
        return {"tasks": sorted(tasks, key=lambda t: (t["group"], t["key"])), "waves": [], **out}
    nodes = [_node(t["key"], t["touches"], priority=story.get("priority"), needs=t["deps"]) for t in tasks]
    try:
        placed = deps.waves(nodes + leaves)
    except deps.CycleError:                                          # the board's own cycle: not this story's to fix
        placed = deps.waves(nodes + [{**n, "deps": []} for n in leaves])
    by_key = {t["key"]: t for t in tasks}
    waves: list[list[str]] = []
    for wave in placed:
        here = sorted((k for k in wave if k in by_key), key=lambda k: (by_key[k]["group"], k))
        if here:                                                     # renumbered among the tasks: 0, 1, 2…
            for k in here:
                by_key[k]["wave"] = len(waves)
            waves.append(here)
    return {"tasks": sorted(tasks, key=lambda t: (t["wave"], t["group"], t["key"])), "waves": waves, **out}


def split(story: Story, conn, *, lang: str) -> list[Proposal]:
    """Subtasks for a story (spec §4.4): one change task per code-map group of its files (groups that use each other
    merged into one), one docs task per page in its footprint or citing its files; ordered by wave, then group."""
    return _settle(story, _proposals(story, conn, lang), conn)["tasks"]


def _refs(v: object) -> list[str]:
    """A list of dependency refs as the person left it: text only, trimmed, first spelling kept, in order."""
    out: list[str] = []
    for ref in v if isinstance(v, (list, tuple)) else ():
        if isinstance(ref, str) and ref.strip() and ref.strip() not in out:
            out.append(ref.strip())
    return out


def _as_proposal(t: dict) -> Proposal:
    """A task the person edited, back as a proposal: touches normalised, derived fields reset to be recomputed."""
    return {"key": str(t["key"]), "kind": t.get("kind") or "change", "title": str(t.get("title") or ""),
            "group": str(t.get("group") or ""), "touches": _touches(t.get("touches") or []),
            "criteria": [str(c) for c in t.get("criteria") or []], "deps": [], "conflicts": [], "wave": 0,
            "edited": bool(t.get("edited")), "added": _refs(t.get("added")), "dropped": _refs(t.get("dropped"))}


def analyze(story: Story, tasks: list[Proposal] | None, *, lang: str) -> dict:
    """Everything the story wizard shows, recomputed from scratch on the current story: lint hints, the INVEST
    verdict, the tasks, the waves as task keys, conflicts with other open stories, the first dependency cycle among
    the tasks, duplicate task keys (`cycle` and `duplicates` are `[]` when none; waves are `[]` while either is not),
    the `added` dependencies that name nothing (`unknown_deps`, `{key: [ref…]}`) and the repos of the story's files
    that have no code graph.

    The tasks are always a fresh `split`, except that the person's `tasks` marked `edited` are kept as given (with
    `outside`: their files that are not in the story's footprint or a page citing it) and replace the fresh proposal
    with the same key; unedited given tasks are regenerated. Reads the index only."""
    lang = _lang(lang)
    touches = _touches(story["touches"])
    conn = index.connect()
    try:
        board = index.nodes(conn)
        kinds = index.types(conn, [n["id"] for n in board])
        others = [n for n in board if kinds.get(n["id"]) == "story"]
        grp = index.groups(conn, touches + [f for n in others for f in n["touches"]])
        verdict = invest(story, others, groups=grp, lang=lang)
        sid = (story.get("id") or "").strip().upper()
        conflicts = deps.conflicts(_node(sid, touches), others, groups=_code_groups(grp))
        kept = [p for p in (_as_proposal(t) for t in tasks or ()) if p["edited"]]
        mine = {p["key"] for p in kept}
        proposals = kept + [p for p in _proposals(story, conn, lang) if p["key"] not in mine]
        footprint = set(touches) | set(_pages(conn, touches))
        settled = _settle(story, proposals, conn)
    finally:
        conn.close()
    for t in settled["tasks"]:
        if t["edited"]:
            t["outside"] = [f for f in t["touches"] if f not in footprint]
    graphless = sorted({_repo(t) for t in _code(touches) if not codemap.graph_file(_repo(t)).is_file()})
    return {"hints": lint(story["as_"], story["want"], story["so"], lang, touches=touches), "invest": verdict,
            "tasks": settled["tasks"], "waves": settled["waves"], "conflicts": conflicts, "cycle": settled["cycle"],
            "duplicates": settled["duplicates"], "unknown_deps": settled["unknown_deps"], "graphless": graphless}
