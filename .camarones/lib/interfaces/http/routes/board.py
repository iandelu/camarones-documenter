"""The Board and the user stories: the board's cards (read by everyone, written with a writing token) and the stories
that become cards (checked by everyone, saved and AI-suggested with a writing token)."""
from __future__ import annotations

import logging

from lib import docs
from lib.interfaces.http import inputs
from lib.interfaces.http.messages import Request, Response, json_response
from lib.interfaces.http.router import Access, route

_log = logging.getLogger("camaron.serve")
BOARD_TOKEN = "writing the board needs the machine token: open the portal with `camaron up`"


def _story_body(b: dict) -> dict:
    """The `stories.Story` of a request body (`story`, with `as` accepted for `as_`); anything not text, or a blank
    `want`, is a ValueError (a 400)."""
    raw = b.get("story")
    if not isinstance(raw, dict):
        raise ValueError("story must be an object")
    as_ = raw["as_"] if "as_" in raw else raw.get("as")
    clauses = {"as_": as_, "want": raw.get("want"), "so": raw.get("so")}
    for k, v in clauses.items():
        if v is not None and not isinstance(v, str):
            raise ValueError(f"{'as' if k == 'as_' else k} must be text")
    if not (clauses["want"] or "").strip():
        raise ValueError("want is required: say what the story is about")
    return {"id": (inputs.text(raw, "id") or "").strip() or None, "as_": clauses["as_"] or "", "want": clauses["want"] or "",
            "so": clauses["so"] or "", "criteria": inputs.text_list(raw, "criteria"), "touches": inputs.text_list(raw, "touches"),
            "epic": (inputs.text(raw, "epic") or "").strip() or None, "priority": (inputs.text(raw, "priority") or "").strip() or None}


def _task_list(b: dict) -> list[dict]:
    """The `tasks` of a body, each checked field by field so a malformed one is a 400 that names the field (never a
    TypeError deep in analyze or save): `key` and `title` are required text; `group` and `kind` text; `touches`,
    `criteria`, `deps`, `added` and `dropped` lists of text; `edited` a bool."""
    v = b.get("tasks")
    if v is None:
        return []
    if not isinstance(v, list):
        raise ValueError("tasks must be a list of objects")
    for n, t in enumerate(v, 1):
        if not isinstance(t, dict):
            raise ValueError(f"task {n}: it must be an object")
        for k in ("key", "title"):
            if not isinstance(t.get(k), str) or not t[k].strip():
                raise ValueError(f"task {n}: {k} is required and must be text")
        for k in ("group", "kind"):
            if t.get(k) is not None and not isinstance(t[k], str):
                raise ValueError(f"task {n}: {k} must be text")
        for k in ("touches", "criteria", "deps", "added", "dropped"):
            if t.get(k) is not None and not (isinstance(t[k], list) and all(isinstance(x, str) for x in t[k])):
                raise ValueError(f"task {n}: {k} must be a list of text")
        if t.get("edited") is not None and not isinstance(t["edited"], bool):
            raise ValueError(f"task {n}: edited must be true or false")
    return v


def _refuse_groups(story: dict, tasks: list[dict]) -> None:
    """A group of the code map (`repo:<group label>`) is a way to search, not something a story touches: analyze works
    on files (save refuses a group itself). The story's and every task's touches are checked."""
    from lib.kanban import index
    asked = []
    for touches in [story["touches"]] + [t.get("touches") or [] for t in tasks]:
        if not isinstance(touches, list) or not all(isinstance(x, str) for x in touches):
            raise ValueError("touches must be a list of text")
        asked += touches
    conn = index.connect()
    try:
        for touch, files in index.files_of(conn, asked).items():
            if files:
                raise ValueError(f'"{touch}" is a group of the code map, not a file: expand groups into files first')
    finally:
        conn.close()


def kanban_marks(cards: list[dict]) -> dict[str, tuple[int | None, list[dict]]]:
    """Each card's `(wave, blocked_by)` for the Board, from one index connection, in the people's view: a card without
    declared files touches nothing. `wave` is its place in the open work's waves (`deps.waves(agent=False)`), only for
    a card that declares files: None for one without (an old board shows no waves), for a Done or archived card, a
    container, or a board with a dependency cycle. `blocked_by` is the start gate's answer, only for Backlog/Ready leaf
    cards. If the index cannot open, nothing is marked (a warning is logged) and the board still loads."""
    from lib.kanban import deps, index
    try:
        conn = index.connect()
        try:
            board = index.nodes(conn)
        finally:
            conn.close()
        ids = {c["id"] for c in cards}
        grouping = deps.containers(board)                       # judged on the whole board, as ops.waves does
        by_id = {n["id"]: n for n in board}
        try:
            placed = {i: w for w, wave in enumerate(deps.waves([n for n in board if n["id"] in ids
                                                                 and n["id"] not in grouping and n["status"] != "Done"],
                                                               agent=False))
                      for i in wave if by_id[i]["touches"]}
        except deps.CycleError:
            placed = {}
        marks = {}
        for c in cards:
            node = by_id.get(c["id"])
            gated = (node is not None and node["id"] not in grouping and not node["archived"]
                     and node["status"] in ("Backlog", "Ready"))
            marks[c["id"]] = (placed.get(c["id"]),
                              deps.blocked_by(node, board, agent=False, grouping=grouping, by_id=by_id) if gated else [])
        return marks
    except Exception as e:                                      # noqa: BLE001 — a broken index never hides the board
        _log.warning("board marks unavailable (%s); the board loads without waves and blockers", e)
        return {}


def kanban_state(writable: bool) -> dict:
    """The whole board for the Board view; read-only, so a GET never creates the layout."""
    from lib import kanban
    from lib.kanban import ops
    data = ops.list_items(with_links=True) if kanban.enabled() else {"cards": [], "problems": []}
    cards = data["cards"]                     # each card brings its link states: the docs filter runs in the page
    marks = kanban_marks(cards) if cards else {}
    for c in cards:
        c["wave"], c["blocked_by"] = marks.get(c["id"], (None, []))
    uniq = lambda xs: sorted({str(x) for x in xs if x})                 # noqa: E731  (str: a hand-edited item cannot break the view)
    return {"enabled": kanban.enabled(), "writable": writable, "statuses": list(kanban.STATUSES),
            "types": list(kanban.TYPES), "priorities": list(kanban.PRIORITIES), **data,
            "epics": [c for c in cards if c["type"] == "epic"],
            "repos": uniq(r for c in cards for r in c["repos"]), "labels": uniq(l for c in cards for l in c["labels"])}


@route("GET", "/api/kanban")
def get_kanban(req: Request) -> Response:
    return json_response(kanban_state(req.can_write))


@route("GET", "/api/kanban/item")
def get_kanban_item(req: Request) -> Response:
    from lib.kanban import ops
    try:
        return json_response(ops.show(req.query.get("id", "")))
    except ops.BoardError as e:
        return json_response({"error": str(e)}, 400)


@route("GET", "/api/kanban/{which:next|waves}")
def get_kanban_plan(req: Request) -> Response:
    from lib.kanban import ops
    q = req.query
    try:
        scope = {"story": q.get("story") or None, "epic": q.get("epic") or None}
        if req.params["which"] == "waves":
            return json_response(ops.waves(**scope))
        n = int(q.get("n") or 3)
        return json_response(ops.next_items(n, **scope, agent=False))     # people's view: the portal and the app
    except ValueError as e:                                             # BoardError is a ValueError
        return json_response({"error": str(e)}, 400)


@route("POST", "/api/kanban/{action:init|add|move|assign|link|archive}", access=Access.PORTAL, refusal=BOARD_TOKEN)
def post_kanban(req: Request) -> Response:
    from lib.kanban import ops
    action, b = req.params["action"], req.body
    surface = "app" if req.is_app else "portal"
    try:                                   # every field is checked before anything is written: bad input is a 400
        by = (inputs.text(b, "by") or "").strip() or None
        if action == "init":
            return json_response({"created": ops.init(log=lambda *_: None)})
        if action == "add":
            return json_response(ops.add(inputs.text(b, "type", True), inputs.text(b, "title", True), epic=inputs.text(b, "epic") or None,
                                         parent=inputs.text(b, "parent") or None,
                                         repos=inputs.text_list(b, "repos"), labels=inputs.text_list(b, "labels"),
                                         priority=inputs.text(b, "priority") or None, docs=inputs.doc_refs(b), by=by, surface=surface))
        if action == "move":
            return json_response(ops.move(inputs.text(b, "id", True), inputs.text(b, "status", True), before=inputs.text(b, "before"),
                                          after=inputs.text(b, "after"), by=by, surface=surface, force=b.get("force") is True))
        if action == "assign":
            return json_response(ops.assign(inputs.text(b, "id", True), inputs.text(b, "who", True), by=by, surface=surface))
        if action == "link":
            return json_response(ops.link(inputs.text(b, "id", True), inputs.text(b, "ref", True), by=by, surface=surface))
        return json_response(ops.archive(inputs.text(b, "id", True), by=by, surface=surface))
    except ops.GateError as e:            # the start gate said no: the Board asks, then resends with `force`
        return json_response({"error": str(e), "blocked_by": e.blocked_by}, 409)
    except ValueError as e:               # BoardError is a ValueError
        return json_response({"error": str(e)}, 400)


@route("GET", "/api/stories")
def get_stories(req: Request) -> Response:
    from lib import kanban, stories, stories_ai, stories_save
    from lib.kanban.index import DOCS_REPO
    return json_response({"enabled": kanban.enabled(), "writable": req.can_write,
                          "ai": stories_ai.status(),
                          "lint_words": {lg: stories.lint_words(lg) for lg in ("es", "en")},
                          "repos": sorted(docs.repo_names()) + [DOCS_REPO],   # Toca's new-file prefixes
                          "stories": stories_save.list_stories() if kanban.enabled() else []})


@route("GET", "/api/stories/item")
def get_story(req: Request) -> Response:
    from lib import stories_save
    from lib.kanban.ops import BoardError
    try:
        return json_response(stories_save.item(req.query.get("id", "")))
    except BoardError as e:
        return json_response({"error": str(e)}, 404)


@route("GET", "/api/stories/files")
def get_story_files(req: Request) -> Response:
    from lib.kanban import index
    q = req.query
    try:
        limit = min(max(int(q.get("limit") or 20), 1), 50)
    except ValueError:
        return json_response({"error": "limit must be a number"}, 400)
    conn = index.connect()
    try:
        hits = index.search(conn, q.get("q", ""), limit)
        files = index.files_of(conn, [h["touch"] for h in hits if h["kind"] == "group"])
    finally:
        conn.close()
    return json_response([{**h, "files": files[h["touch"]]} if h["kind"] == "group" else h for h in hits])


@route("POST", "/api/stories/{action:lint|analyze}")
def post_story_check(req: Request) -> Response:
    return _stories(req.params["action"], req)


@route("POST", "/api/stories/save", access=Access.PORTAL,
       refusal="saving a story needs the machine token: open the portal with `camaron up`")
def post_story_save(req: Request) -> Response:
    return _stories("save", req)


@route("POST", "/api/stories/suggest", access=Access.PORTAL,       # it runs the machine's AI runner
       refusal="AI suggestions need the machine token: open the portal with `camaron up`")
def post_story_suggest(req: Request) -> Response:
    return _stories("suggest", req)


def _stories(action: str, req: Request) -> Response:
    from lib import stories, stories_save
    from lib.kanban import ops
    b = req.body
    try:                                   # every field is checked before anything is written: bad input is a 400
        lang = inputs.text(b, "lang") or ops.docs_lang()
        if action == "lint":
            for k in ("as", "want", "so"):
                inputs.text(b, k)
            return json_response({"hints": stories.lint(b.get("as") or "", b.get("want") or "", b.get("so") or "", lang,
                                                        touches=inputs.text_list(b, "touches"))})
        if action == "suggest":
            from lib import stories_ai
            what, skip = inputs.text(b, "what", True), inputs.text_list(b, "exclude")
            if what not in stories_ai.WHAT:
                raise ValueError(f"what must be one of {', '.join(stories_ai.WHAT)}")
            story = _story_body(b)
            try:
                return json_response(stories_ai.suggest(story, what=what, exclude=skip, lang=lang))
            except RuntimeError as e:      # off, no runner, too slow: the page shows the reason
                return json_response({"error": str(e)}, 503)
        story, tasks = _story_body(b), _task_list(b)
        if action == "analyze":
            removed = inputs.text_list(b, "removed")
            _refuse_groups(story, tasks)
            return json_response(stories.analyze(story, tasks, lang=lang, removed=removed))
        by = (inputs.text(b, "by") or "").strip() or None
        base_sha, docs_refs, title = inputs.text(b, "base_sha") or None, inputs.doc_refs(b), inputs.text(b, "title")
        base_title = inputs.text(b, "base_title")
        base_touches = None if b.get("base_touches") is None else inputs.text_list(b, "base_touches")
        return json_response(stories_save.save(story, title=title, tasks=tasks, base_sha=base_sha, docs=docs_refs,
                                               lang=lang, by=by, surface="app" if req.is_app else "portal",
                                               base_title=base_title, base_touches=base_touches))
    except stories_save.StoryConflict as e:
        return json_response({"error": str(e), "id": e.story_id}, 409)
    except ValueError as e:               # BoardError is a ValueError
        return json_response({"error": str(e)}, 400)
