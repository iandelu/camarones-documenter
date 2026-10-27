"""The ADR as a Markdown document, pure (`docs/decisions/<NNNN>-<slug>.md`, spec §3.1).

Numbering and slugs, the status of an ADR the kit did not write (no frontmatter, Spanish headings, `Propuesto <!-- … -->`,
an inline `Status:` line), its sections read and replaced in place, and the one template a new ADR is rendered from.
Reading is tolerant: a section is an `##` heading whose text is one of the English or Spanish headings of a key.
Writing is narrow: `replace_section` changes one section and keeps every other byte, frontmatter included,
`replace_status` changes only the status line `status_of` reads; only `render_new` renders a whole file. Nothing here
touches the disk or a model."""
from __future__ import annotations

import re
import unicodedata
from pathlib import PurePath
from typing import Iterable

from . import docs
from .common import CAM_DIR

KEYS = ("status", "context", "drivers", "options", "decision", "consequences", "confirmation", "diagram", "evidence",
        "decided_by")
ORDER = KEYS                    # where a missing section is inserted: before the first existing one that comes later
HEADINGS = {"status": "Status", "context": "Context", "drivers": "Decision drivers", "options": "Considered options",
            "decision": "Decision", "consequences": "Consequences", "confirmation": "Confirmation",
            "diagram": "Diagram", "evidence": "Evidence", "decided_by": "Decided by"}
_SPANISH = {"status": "Estado", "context": "Contexto", "drivers": "Drivers", "options": "Opciones consideradas",
           "decision": "Decisión", "consequences": "Consecuencias", "confirmation": "Confirmación",
           "diagram": "Diagrama", "evidence": "Evidencia", "decided_by": "Decidido por"}
_KEY_OF = {h.lower(): k for k in KEYS for h in (HEADINGS[k], _SPANISH[k])}

PLACEHOLDER = "To be decided in review: see the decision points."
POINTS_HEADING = "### Decision points"        # the subsection of Decision that holds `render_points`' output
SLUG_MAX = 60
DESCRIPTION_MAX = 300

_PROPOSED = 'Proposed <!-- agents only write "Proposed"; people accept, supersede or reject -->'
_CLAIM = "Named when the decision was framed"
_STATUS = {word: token for token, words in {
    "proposed": ("proposed", "propuesto", "propuesta"), "accepted": ("accepted", "aceptado", "aceptada"),
    "rejected": ("rejected", "rechazado", "rechazada"), "superseded": ("superseded", "sustituido", "sustituida"),
    "deprecated": ("deprecated", "obsoleto", "obsoleta")}.items() for word in words}
_LABEL_RE = re.compile(r"^[\W_]*(?:status|estado)\b[\W_]*", re.I)
_INLINE_RE = re.compile(r"^[ \t>*_-]*(?:status|estado)[*_]*[ \t]*:.*$", re.I | re.M)
_WORD_RE = re.compile(r"[\W_]*([^\W\d_]+)")
_NUMBER = r"(?<![0-9])([0-9]{4})(?![0-9])"
_NUMBER_RE = re.compile(_NUMBER)
_BY_RE = re.compile(r"\b(?:by|por)\b\D*?" + _NUMBER, re.I)
_DATE_RE = re.compile(r"[0-9]{4}[-/.][0-9]{1,2}[-/.][0-9]{1,2}|[0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{4}")
_FILE_RE = re.compile(r"([0-9]{4})-.+\.md")


def slugify(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    return "-".join(re.findall(r"[a-z0-9]+", ascii_title.lower()))[:SLUG_MAX].strip("-") or "decision"


def next_number(taken: Iterable[str]) -> str:
    numbers = [int(t) for t in taken if re.fullmatch(r"[0-9]+", t)]
    return f"{max(numbers, default=0) + 1:04d}"


def number_of(name: str) -> str | None:
    m = _FILE_RE.fullmatch(PurePath(name).name)
    return m[1] if m else None


# ---------- reading ----------
def _key_of(title: str) -> str | None:
    return _KEY_OF.get(title.strip().lower())


def _find(body: str, key: str) -> dict | None:
    if key not in HEADINGS:
        raise KeyError(key)
    return next((s for s in docs.sections(body) if _key_of(s["title"]) == key), None)


def section(body: str, key: str) -> str | None:
    """The text of the section `key` without its heading (subsections included); None when the page has none."""
    found = _find(body, key)
    if not found:
        return None
    return "\n".join(body.splitlines()[found["start"] + 1:found["end"]]).strip()


def _status_line(body: str) -> str:
    first = next((l for l in (section(body, "status") or "").splitlines() if l.strip()), None)
    if first is not None:
        return first
    inline = _INLINE_RE.search(body)
    return inline[0] if inline else ""


def status_of(body: str) -> tuple[str, str | None]:
    """(token, number of the ADR that supersedes this one). Read from the first line of the Status section, else a
    `Status:` line; the number is the one after `by`/`por`, else the first outside a date."""
    line = _LABEL_RE.sub("", _status_line(docs.COMMENT_RE.sub("", body)))
    word = _WORD_RE.match(line)
    token = _STATUS.get(word[1].lower(), "unknown") if word else "unknown"
    rest = _DATE_RE.sub(" ", line[word.end():]) if word and token == "superseded" else ""
    by = _BY_RE.search(rest) or _NUMBER_RE.search(rest)
    return token, by[1] if by else None


# ---------- writing ----------
def _fill(lines: list[str], found: dict, new: str) -> None:
    start, end = found["start"], found["end"]
    written = [i for i in range(start + 1, end) if lines[i].strip()]
    if written:
        first, last = written[0], written[-1]
        eol = lines[last][len(lines[last].rstrip("\r\n")):]
        lines[first:last + 1] = [new + eol] if new else []
    elif new:
        if not lines[start].endswith("\n"):
            lines[start] += "\n"
        lines[start + 1:end] = ["\n", new + "\n"] + (["\n"] if end < len(lines) else [])


def _insert(lines: list[str], key: str, new: str, secs: list[dict]) -> None:
    rank = ORDER.index(key)
    later = next((s for s in secs if (k := _key_of(s["title"])) and ORDER.index(k) > rank), None)
    block = f"## {HEADINGS[key]}\n\n{new}\n"
    if later:
        at = later["start"]
        lines.insert(at, ("\n" if at and lines[at - 1].strip() else "") + block + "\n")
        return
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines.append(("\n" if lines and lines[-1].strip() else "") + block)


def replace_section(text: str, key: str, new_body: str) -> str:
    """Whole file in, whole file out: only the text of section `key` changes, frontmatter and every other byte stay.
    A missing section is added before the first existing one that comes later in `ORDER`, else at the end."""
    _, body, _ = docs.parse_fm(text)
    head, lines = text[:len(text) - len(body)], body.splitlines(keepends=True)
    found, new = _find(body, key), new_body.strip("\n")
    if found:
        _fill(lines, found, new)
    elif new:
        _insert(lines, key, new, docs.sections(body))
    return head + "".join(lines)


def _blank_comments(body: str) -> str:
    """`body` with each HTML comment turned into spaces, line breaks kept: the same lines and offsets, minus what a reader skips."""
    return docs.COMMENT_RE.sub(lambda m: "".join(c if len(f"a{c}b".splitlines()) > 1 else " " for c in m[0]), body)


def _line_end(text: str, at: int) -> int:
    rest = text[at:].splitlines()
    return at + (len(rest[0]) if rest else 0)


def replace_status(text: str, new: str) -> str:
    """Whole file in, whole file out: `new` takes the place of the status `status_of` reads (the first text of the Status
    section once comments are set aside) and of what else is on its line, comments there included. A comment on a line of
    its own or before the status, and every note below, stay. A section with only a comment gets `new` below it."""
    _, body, _ = docs.parse_fm(text)
    seen = _blank_comments(body)
    found = _find(seen, "status")
    if not found:
        return replace_section(text, "status", new)
    head, lines, masked = text[:len(text) - len(body)], body.splitlines(keepends=True), seen.splitlines()
    rows = range(found["start"] + 1, found["end"])
    first = next((i for i in rows if masked[i].strip()), None)
    if first is None:
        written = [i for i in rows if lines[i].strip()]
        if not written:
            return replace_section(text, "status", new)
        last = written[-1]
        lines[last] += "" if lines[last].endswith(("\n", "\r")) else "\n"
        lines.insert(last + 1, new + "\n")
        return head + "".join(lines)
    start = len("".join(lines[:first]))
    lo = start + len(masked[first]) - len(masked[first].lstrip())
    hi = start + len(lines[first].splitlines()[0])
    for c in docs.COMMENT_RE.finditer(body):
        if lo <= c.start() < hi < c.end():
            hi = _line_end(body, c.end())
    return head + body[:lo] + new + body[hi:]


# ---------- rendering ----------
def _texts(value) -> list[str]:
    return [t for t in (str(v).strip() for v in value or []) if t]


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items)


def _letter(i: int) -> str:
    return chr(ord("A") + i) if i < 26 else str(i + 1)


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def evidence_table(rows: list[tuple[str, str]]) -> str:
    return "\n".join(["| Claim | Evidence |", "|---|---|", *(f"| {_cell(c)} | {_cell(e)} |" for c, e in rows)])


def _option_line(i: int, option: dict) -> str:
    notes = [f"+ {p}" for p in option.get("pros") or []] + [f"− {c}" for c in option.get("cons") or []]
    return f"- **{option.get('id') or _letter(i)} · {option.get('name', '')}**" + (" — " + "; ".join(notes) if notes else "")


def render_points(points: list[dict]) -> str:
    """One `#### P1 · question` block per point with a line per option and its pros (+) and cons (−), no heading."""
    blocks = []
    for n, point in enumerate(points, 1):
        options = [_option_line(i, o) for i, o in enumerate(point.get("options") or [])]
        head = f"#### {str(point.get('id') or f'p{n}').upper()} · {point.get('question', '')}"
        blocks.append("\n".join([head, "", *options]) if options else head)
    return "\n\n".join(blocks)


def _outcome(point: dict) -> str:
    chosen = point.get("chosen")
    if chosen:
        option = next((o for o in point.get("options") or [] if o.get("id") == chosen), None)
        return str((option or {}).get("name") or chosen).strip()
    return str(point.get("other") or "").strip()


def render_decision(points: list[dict]) -> str:
    """One paragraph per decided point: the question, what was chosen and why. A point nobody decided has none."""
    paragraphs = []
    for point in points:
        outcome = _outcome(point)
        if not outcome:
            continue
        lead = f"**{point.get('question', '')}** — {outcome}" + ("" if outcome.endswith((".", "!", "?")) else ".")
        why = str(point.get("rationale") or "").strip()
        paragraphs.append(f"{lead} {why}" if why else lead)
    return "\n\n".join(paragraphs)


def render_decided_by(date: str, attendees: list[str], driver: str, mode: str) -> str:
    rows = [("Date", date), ("Attendees", ", ".join(_texts(attendees))), ("Mode", mode), ("Led by", driver.strip())]
    return "\n".join(f"- {label}: {value}" for label, value in rows if value)


def _source(touch: str) -> str:
    repo, sep, path = touch.partition(":")
    return path if sep and repo == CAM_DIR else touch


def render_new(fields: dict, number: str) -> str:
    """The full proposed file: Status `Proposed`, `x-owner: ai`, the person's framing and an empty decision. What the
    person did not give is a `TODO(question)`, never an invented fact. The proposal carries no date: accepting writes it."""
    title = " ".join(str(fields.get("title") or "").split())
    touches = list(dict.fromkeys(_texts(fields.get("touches"))))
    drivers, constraints, options = (_texts(fields.get(k)) for k in ("drivers", "constraints", "options_hint"))
    fm = {"type": "decision", "title": f"{number} — {title}",
          "description": (f"Why the project chose an option for: {title}. Proposed decision with its options, evidence "
                          "and the decision points the team reviews.")[:DESCRIPTION_MAX],
          "tags": sorted({t.partition(":")[0] for t in touches if ":" in t and not t.startswith(CAM_DIR + ":")}),
          "x-sources": list(dict.fromkeys(_source(t) for t in touches)), "x-owner": "ai"}
    context = str(fields.get("problem") or "").strip() or "TODO(question): what is the problem and which forces are at play?"
    if constraints:
        context += "\n\n**Constraints**\n\n" + _bullets(constraints)
    parts = [("status", _PROPOSED), ("context", context)]
    if drivers:
        parts.append(("drivers", _bullets(drivers)))
    parts += [("options", "\n\n".join(f"### {_letter(i)} · {name}" for i, name in enumerate(options))
                          or "TODO(question): which options were considered?"),
              ("decision", PLACEHOLDER),
              ("consequences", "TODO(question): what gets easier and what gets harder?"),
              ("evidence", evidence_table([(_CLAIM, f"`{t}`") for t in touches]))]
    tldr = f"Decision record for {title}: problem, options, outcome and evidence. Check the status first."
    body = f"# {number} — {title}\n\n> **TL;DR:** {tldr}\n\n" + "\n\n".join(
        f"## {HEADINGS[key]}\n\n{text}" for key, text in parts) + "\n"
    return docs.join_fm(fm, body)
