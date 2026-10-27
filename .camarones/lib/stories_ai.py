"""AI suggestions for the story wizard, on by default like Ask (`stories: {ai: false}` in workspace.yaml turns them off);
nothing runs until the person asks for one. The model only suggests wording (`rewrite` of the three clauses),
acceptance `criteria` and subtask ideas (`tasks`); it never decides footprints, dependencies, waves or the verdict:
those stay with the rules in `stories`, and a file a model names is kept only if the board's index knows it. Built like Ask's AI answer (`answers`): the runner routed for
bounded work (a local model is fine), one headless call with no tools in an empty folder so the project's agent config
does not load, and only the part asked for, to keep the prompt small. Nothing here writes a file."""
from __future__ import annotations

import sqlite3, tempfile
from pathlib import Path
from typing import Literal, Sequence

from . import docs, stories
from .kanban import deps, index

WHAT = ("rewrite", "criteria", "tasks")
TIMEOUT = 90                   # seconds a person waits in the wizard
CHEAP = {"claude": "haiku"}    # suggesting wording from a few lines needs no large model
LIMIT = 6000                   # characters of documentation excerpts
MAX_TASKS = 8
MAX_CRITERIA = 8
OFF = "AI suggestions are off: stories: {ai: false} in workspace.yaml"
LANGUAGES = {"es": "Spanish", "en": "English"}
_GIVEN = {"es": "Dado … cuando … entonces …", "en": "Given … when … then …"}


def _section() -> dict:
    section = docs.workspace().get("stories")
    return section if isinstance(section, dict) else {}


def _switched_on() -> bool:
    return _section().get("ai") is not False


def runner() -> str | None:
    """The routed runner for bounded work, if one is installed; looks it up and runs nothing."""
    if not _switched_on():
        return None
    from . import plan
    found = plan._agents(lambda _: None, "bounded", allow_local=True)
    return found[0] if found else None


def enabled() -> bool:
    return runner() is not None


def model(target: str) -> str | None:
    """The model to ask for: `stories.model`, else the route's own (`claude:opus`), else the runner's cheap one."""
    from .harness import routing
    chosen = _section().get("model")
    if chosen:
        return str(chosen)
    route = routing.parse(target)
    return None if route.model else CHEAP.get(route.runner)


def status() -> dict:
    """What `GET /api/stories` tells the page: whether the suggestions can run, with what, or why not."""
    target = runner()
    if not target:
        return {"available": False, "runner": None, "model": None, "reason": "no-runner" if _switched_on() else "off"}
    from .harness import routing
    return {"available": True, "runner": target, "model": model(target) or routing.parse(target).model, "reason": None}


# ── the prompt ───────────────────────────────────────────────────────────────────────────────────────────────────

def _one_line(text: object) -> str:
    return " ".join(str(text).split())


def _instructions(what: str, lang: str) -> tuple[str, str]:
    """(what to do, the JSON shape of the reply) for the one part asked for."""
    if what == "rewrite":
        return ("Rewrite the three clauses of the story so each is clear: a specific role (not just \"user\"), a "
                "need rather than a solution, and a benefit that does not restate the need. Keep the meaning and "
                "invent nothing. Write each clause without the leading \"As a\" / \"I want\" / \"so that\".",
                '{"rewrite": {"as": "<who>", "want": "<what>", "so": "<why>"}}')
    if what == "criteria":
        return (f"Suggest up to {MAX_CRITERIA} acceptance criteria, each one observable and testable, in the form "
                f"\"{_GIVEN[lang]}\". Do not repeat the existing criteria.",
                '{"criteria": ["<criterion>", ...]}')
    return (f"Suggest up to {MAX_TASKS} small subtasks that together deliver the story, each a short imperative "
            "title. For each, list in `touches` the files it changes, chosen only from the files listed below "
            "(copy them exactly); leave it empty if none applies.",
            '{"tasks": [{"title": "<title>", "touches": ["<repo:path>", ...]}]}')


def _context(story: stories.Story) -> str:
    """Up to four documentation excerpts about the story (only what agents may read, through the freshness gate)."""
    from . import mcp
    found = mcp.ask(_one_line(f"{story['want']} {story['so']}"), limit=4)
    if found.startswith("Nothing in the docs"):
        return ""
    return _one_line(found.split("\n\n", 1)[1])[:LIMIT]


def _prompt(story: stories.Story, what: str, exclude: Sequence[str], lang: str) -> str:
    do, shape = _instructions(what, lang)
    parts = [f"You help write a user story for a software project. {do}",
             f"Story. As: {_one_line(story['as_'])} | I want: {_one_line(story['want'])} | So that: "
             f"{_one_line(story['so'])}."]
    criteria = [_one_line(c) for c in story["criteria"] if _one_line(c)]
    if criteria:
        parts.append("Existing criteria: " + " | ".join(criteria) + ".")
    touches = stories._touches(story["touches"])
    if touches:
        parts.append("Files the story touches: " + ", ".join(touches) + ".")
    skip = [_one_line(e) for e in exclude if _one_line(e)]
    if skip:
        parts.append("Do not suggest again: " + " | ".join(skip) + ".")
    excerpts = _context(story)
    if excerpts:
        parts.append(f"Documentation excerpts for context: {excerpts}")
    parts.append(f"Write the suggestions in {LANGUAGES[lang]}. Reply with one JSON object on the last line: {shape}")
    return " ".join(parts)


# ── the reply ────────────────────────────────────────────────────────────────────────────────────────────────────

def _key(text: str) -> str:
    return _one_line(text).casefold()


def _texts(value: object, seen: set[str], limit: int) -> list[str]:
    """The non-blank text items of a list, trimmed, in order, without repeats or anything in `seen`, at most `limit`."""
    out: list[str] = []
    for item in value if isinstance(value, list) else ():
        text = _one_line(item) if isinstance(item, str) else ""
        if text and _key(text) not in seen:
            seen.add(_key(text))
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _rewrite(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    clauses = {k: stories._trim(value[src]) if isinstance(value.get(src), str) else ""
               for k, src in (("as_", "as" if "as" in value else "as_"), ("want", "want"), ("so", "so"))}
    return clauses if all(clauses.values()) else None


def _known(touch: object, conn) -> str | None:
    """The normalised touch if the index has exactly that file (a group, a page or a made-up name does not count)."""
    if not isinstance(touch, str):
        return None
    try:
        touch = deps.norm_touch(touch, fold=False)
    except ValueError:
        return None
    return touch if any(h["kind"] == "file" and h["touch"] == touch for h in index.search(conn, touch, 20)) else None


def _tasks(value: object, exclude: set[str]) -> list[dict]:
    wanted = [t for t in value if isinstance(t, dict)] if isinstance(value, list) else []
    conn = None
    try:
        if any(isinstance(t.get("touches"), list) and t["touches"] for t in wanted):
            try:
                conn = index.connect()
            except (OSError, sqlite3.Error):
                conn = None                                  # no index to check against: no file is believed
        out: list[dict] = []
        for t in wanted:
            title = t.get("title")
            title = stories._cut(title, stories.TASK_TITLE_MAX) if isinstance(title, str) else ""
            if not title or _key(title) in exclude:
                continue
            exclude.add(_key(title))
            found = t.get("touches") if isinstance(t.get("touches"), list) else []
            files = sorted({k for k in (_known(f, conn) for f in found) if k}) if conn is not None else []
            out.append({"title": title, "touches": files})
            if len(out) >= MAX_TASKS:
                break
        return out
    finally:
        if conn is not None:
            conn.close()


def suggest(story: stories.Story, *, what: Literal["rewrite", "criteria", "tasks"], exclude: Sequence[str] = (),
            lang: str) -> dict:
    """Ask the model for one part of a story: `{rewrite: {as_, want, so} | None, criteria: [str], tasks: [{title,
    touches}], missing: [what] when nothing usable came back, runner, model, seconds}`. `exclude` holds criteria or
    task titles the person already has or dismissed. A RuntimeError says why not (off, no runner, too slow)."""
    if not _switched_on():
        raise RuntimeError(OFF)
    if what not in WHAT:
        raise ValueError(f"what must be one of {', '.join(WHAT)}")
    target = runner()
    if not target:
        raise RuntimeError("no AI suggestions here: no runner for bounded work")
    from .harness.evals import _ask, _last_json
    from .harness import routing
    from .harness.ports import RunRequest
    lang = "es" if lang == "es" else "en"
    prompt = _prompt(story, what, exclude, lang)
    chosen = model(target)
    with tempfile.TemporaryDirectory(prefix="cam-stories-") as empty:
        got = _ask(target, RunRequest(prompt=prompt, cwd=Path(empty), env={}, model=chosen, allow_tools=(), stream=True),
                   timeout=TIMEOUT)
    if got.get("timed_out"):
        raise RuntimeError(f"no suggestions within {TIMEOUT} s: {target} is slow or waiting for a login; try again or "
                           "set a faster model with `stories: {model: …}` in workspace.yaml")
    obj = _last_json(got["lines"], what) or {}
    seen = {_key(e) for e in exclude}
    result = {"rewrite": None, "criteria": [], "tasks": []}
    if what == "rewrite":
        result["rewrite"] = _rewrite(obj.get("rewrite"))
    elif what == "criteria":
        result["criteria"] = _texts(obj.get("criteria"), seen, MAX_CRITERIA)
    else:
        result["tasks"] = _tasks(obj.get("tasks"), seen)
    made = bool(result[what])
    from . import usage
    usage.record("stories:suggest", channel="human", hit=made)
    return {**result, "missing": [] if made else [what], "runner": target,
            "model": chosen or routing.parse(target).model, "seconds": got["seconds"]}
