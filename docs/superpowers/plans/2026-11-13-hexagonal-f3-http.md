# Hexagonal refactor F3 (HTTP router) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `lib/serve.py`'s `if p == "/api/…"` chains with routes declared per area under
`.camarones/lib/interfaces/http/`, each declaring who may call it, with one dispatcher that applies today's gates in
today's order, and nothing a user can notice.

**Architecture:** `serve.Handler` stays the live handler while the areas move: from Task 3 it asks the router first,
and each area task moves its functions into `interfaces/http/routes/<area>.py` and deletes its branches. Task 17 moves
the transport into `interfaces/http/server.py`, writes the gates once in `router.dispatch`, deletes the `APP_ONLY`
regex (access comes from the declarations) and leaves `lib/serve.py`, `lib/appapi.py` and `lib/adr_api.py` as facades.
The views the static export shares with the server move to `lib/app/portal_views.py`, so `env` stops importing the
HTTP layer.

**Tech Stack:** Python ≥ 3.10 stdlib (`http.server`, `re`, `pkgutil`, `importlib`, `dataclasses`, `json`,
`urllib`), pytest + pytest-xdist. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-12-hexagonal-refactor-design.md` (§2, §3 rows `serve.py, appapi.py` and
`adr_cli.py, adr_api.py`, §4.2, §5 HTTP snapshot, §6 row F3, §7). Read it first, and the F2 plan's decisions P6 and
P11 (`docs/superpowers/plans/2026-11-12-hexagonal-f2-cli.md`), which this plan reuses.

## Decisions this plan takes

The spec leaves these open; each is final for F3.

| # | Decision | Why |
|---|---|---|
| P1 | A handler is `def h(req: Request) -> Response`. `Request` gains `services` when `bootstrap.py` exists (F4+) | No `Services` exists yet (F2's P1, same reason) |
| P2 | No transitional `legacy` module: `serve.Handler` keeps the unmoved branches and asks `router.load().match(...)` first, at two points (Task 3). Task 17 moves the transport to `server.py` | A `server.py` subclassing `serve.Handler` while `serve` re-exports it is an import cycle, and `cycle_modules` may not grow |
| P3 | `tree`, `read`, `status`, `doc_file`, `reviewer`, the ADR `covering` and the code map lookup, with `APP`, `UI`, `UI_LIBS`, go to `lib/app/portal_views.py` (app layer) | `env`'s static export needs them; a route module imported by `env` would join `env`'s import cycle and add allowlist lines. In `app`, `env → portal_views` is no violation |
| P4 | One owner per adapter among the HTTP modules (table below); the others go through the owner. `lib/onboard.py` gains `set_stack(repo, text) -> dict` | Each `serve -> X` allowlist line becomes exactly one line (F2's P10 rule): the count never grows |
| P5 | Paths match as today: GET/HEAD on the percent-decoded path, POST/PUT on the path as sent (a handler unquotes a parameter, as `app_unit` does); `query` keeps the first value of each key | `serve.do_GET` unquotes, `serve.do_POST` does not; `/api/app/units/a%2Fb/stop` names unit `a/b` |
| P6 | Patterns: `{name}` is `[^/]+`, `{name:regex}` any regex without braces; the whole path must match. A path under `/api/` matches only patterns under `/api/`. Most specific first: longest literal prefix (text before the first `{`), then a pattern with no parameter; then declaration order (modules by name, then source order) | Reproduces today's branch order for every overlap (`/raw/wikis/` before `/raw/`, `/` before the portal fallback, `adr/candidates` before `adr/<id>`); an unknown `/api/…` GET stays a JSON 404, never the portal page |
| P7 | Gate order (Task 17, `router.dispatch`), as today. GET/HEAD: foreign host → 403 `{"error": "forbidden host"}`; then, inside the error mapping: APP access without the app token → 403; unmatched under `/api/app/` → 404 `{"error": "not found"}`; a `static=True` route; static mode → the exported site; unmatched under `/api/` → 404 JSON; the matched route; else `not found`. POST/PUT: static mode → 405; no `X-Camarones: 1` or foreign host → 403 `{"error": "forbidden"}`; APP access without the app token → 403; then inside the error mapping: JSON body; `by` (when unmatched or the route's `by` is true); unmatched → 404 JSON; PORTAL access without a writing token → 403 `{"error": <route's refusal>, "token": True}`; the handler | Each step is a line of today's `do_GET`/`do_POST`/`kanban_post`/`stories_post`; the routes snapshot and `tests/test_http_contract.py` pin them |
| P8 | Unmatched paths: under `/api/app/` they are APP; elsewhere PUBLIC. A route under `/api/app/` must declare APP (`route()` refuses otherwise) | Today `/api/app/anything` without the token is a 403 whether or not it exists |
| P9 | A move keeps today's function bodies: a branch on `p.startswith(X)` becomes pattern `X{rest:.*}` with `rest` for `p[len(X):]`; `p == X` becomes the literal pattern; a regex branch becomes regex parameters with the same expressions; a function that dispatches on its own argument (`app_onboard(name, b)`, `c4_change(path, b, by)`, `adr_api.post(action, b, by)`) keeps its body behind one route with an alternation parameter. `self.json(x, c)` → `return json_response(x, c)`, `self.is_app()` → `req.is_app`, `self.can_write()` → `req.can_write`, `b` → `req.body`, `q` → `req.query`, `by` → `req.by` | A behaviour change hidden inside a move is an anti-goal (spec §1); verbatim bodies make each diff reviewable |
| P10 | Moved code keeps its logger names (`camaron.serve`, `camaron.adr_api`) and its import placement: module-level stays module-level, inside a function stays inside. Kit imports in `lib/interfaces/` and `lib/app/` are absolute (`from lib import docs`), as F2's P11 | Log output and import-time behaviour stay as they are; `routes/adr.py` and `routes/machine.py` share names with `lib/adr.py` and `lib/machine.py` |
| P11 | During Tasks 5–16 `serve.py` imports every moved public name back (tests call `kit.serve.tree()`, `kit.serve.wiki(...)` and so on); Task 17's facade re-exports them. A test that patches or reads module state (tokens, `STATIC`, tunables, caches, private helpers, a `Handler` method, `serve.env`/`serve.docs`) moves to the defining module in the task that moves the name | Old paths keep working for all of 4.x (spec §7); the facade guard and `raising=True` make a stale patch fail loudly |
| P12 | `tests/snapshots/routes.json` gains `POST /api/app/creds/test` and `POST /api/app/creds/delete` (Task 1): real routes today, invisible to the snapshot's literal scan because `app_creds` strips a prefix. From then on the file never changes | The router's table must equal the snapshot (spec §5) |
| P13 | `Response.stream(wfile)` writes server-sent events; the server runs it inside the same error mapping as dispatch (`router.error_response`) | Today a stream runs inside `do_GET`'s `try` |

## Owners of the adapters

| Adapter (allowlist line today) | Owner | Other HTTP modules use |
|---|---|---|
| `codemap` | `lib/app/portal_views.py` | `portal_views.code_map(repo)` (`analysis`) |
| `creds`, `machine` | `routes/machine.py` | `machine_routes.ui_lang(lang)` (`runs`), `machine_routes.sessions_setting()` (`terminals`) |
| `terminals` | `routes/terminals.py` | `unit_terminals()` (`runs`), `shutdown()` (`server`) |
| `kanban`, `kanban.index` | `routes/board.py` | — |
| `inventory`, `schemas`, `quickarch`, `diagrams`, `radar` | `routes/analysis.py` | `onboard.set_stack(repo, text)` in `lib/onboard.py` (`routes/onboard.py`) |
| `harness.events` | `routes/runs.py` | — |

End state of the 12 `serve -> X` lines and of `env -> serve`, `env -> adr_api` (14 → 12): `app.portal_views -> codemap`;
`interfaces.http.routes.machine -> creds`, `-> machine`; `interfaces.http.routes.terminals -> terminals`;
`interfaces.http.routes.board -> kanban`, `-> kanban.index`; `interfaces.http.routes.analysis -> diagrams`,
`-> inventory`, `-> quickarch`, `-> radar`, `-> schemas`; `interfaces.http.routes.runs -> harness.events`.

## Global Constraints

- macOS, Windows and Linux: `pathlib` only, `encoding="utf-8"` on every read and write, processes through the kit
  helpers, `IS_WIN`/`IS_MAC` instead of `sys.platform` (AGENTS.md §2.1).
- No new dependency of any kind.
- Nothing a user notices: after Task 1, `tests/snapshots/routes.json` stays byte-identical; status codes, JSON bodies
  (`json.dumps(data, ensure_ascii=False)`), `Content-Type`, `Content-Length` and `Cache-Control: no-store` are written
  as `serve.Handler.send`/`json`/`file` write them today. Code moves verbatim except the edits P9 and a task name.
- `tests/architecture/allowlist.yaml`: the number of `violations` never grows; lines are renamed per the owner table.
  `largest_cycle` and `cycle_modules` are only ever lowered, to what `tests/test_architecture.py` measures. Each commit
  body states the violation count before → after.
- Facades: explicit imports (never `import *`), `__facade__` and `__all__` listing every imported name. `lib/serve.py`
  sets `__facade__ = "lib.interfaces.http"` (several homes; the guard names the defining module from `__module__`).
  No module reads a facade's re-export at call time (`test_no_module_reads_a_facade_reexport_at_call_time`).
- A file that moves whole moves with `git mv`: `lib/adr_api.py` → `lib/interfaces/http/routes/adr.py`, `lib/appapi.py`
  → `lib/interfaces/http/routes/app_cmd.py`, `lib/serve.py` → `lib/interfaces/http/server.py`; the facade is then
  written at the old path. No module name differs from another in its package only by case.
- No `VERSIONS["kit"]` bump. Conventional commits (`refactor(http): …`, `test(http): …`); every body ends with
  "Nothing a user notices." (AGENTS.md §5.1). No `Co-Authored-By` or "Generated with" trailer. Stage only this plan's
  files: other sessions edit the tree in parallel.
- `uv run pytest -n auto` from the repository root is green before every commit.
- If `main` changes `lib/serve.py`, `lib/appapi.py` or `lib/adr_api.py` while F3 is in flight, port the change into
  its new home on rebase.
- Code and comments in English, comments only for a non-obvious *why*.

## Review Focus

Each line gets its test in Task 1 (`tests/test_http_contract.py`), written against today's server and kept to the end.

- A body that is not JSON → 400 before any portal-token check (`POST /api/kanban/add` with `{` and no token), and an
  unknown `/api/…` POST is 400 with `{`, 404 `{"error": "not found"}` with `{}`.
- Percent-encoding: `GET /raw/a%20b.txt` serves `docs/a b.txt`; `POST /api/app/units/a%2Fb/stop` with the app token
  reaches unit `a/b` (404 `{"error": "no unit a/b"}`).
- Unknown paths by place: under `/api/app/` 403 `"app": true` without the app token (GET and POST) and 404
  `{"error": "not found"}` with it; `GET /api/nope` 404 JSON; `GET /some/page` the portal's `index.html`;
  `GET /missing.js` 404 `not found`.
- Static mode (`up --static`): `POST /api/doc` without `X-Camarones` → 405 read-only; `GET /api/app/info` with the app
  token → 200; `GET /api/tree` → the exported site's `index.html`.
- `HEAD /api/tree` → 200, the GET's `Content-Type`, empty body; `PUT` is POST; a foreign `Host` → 403
  `{"error": "forbidden host"}` (GET) and `{"error": "forbidden"}` (POST).

## File map (end state)

```
.camarones/lib/app/__init__.py              docstring only
.camarones/lib/app/portal_views.py          APP, UI, UI_LIBS, reviewer(), doc_file(), tree(), read(), status(), covering(), code_map()
.camarones/lib/interfaces/http/
  __init__.py                               docstring only
  messages.py      Request, Response, json_response(), not_found(), redirect(), event_stream()
  router.py        Access, APP_ONLY_MSG, Route, Match, route(), Router, load(), dispatch(), error_response()
  server.py        Handler (transport), token_matches(), APP_TOKEN, PORTAL_TOKEN, STATIC, take_tokens(), watch_app(), run_server()
  jobs.py          JOBS, JOB_IDS, JOB_LOCK, CANCEL, start_job(), claim_job(), fail_job(), run_job(), job_running()
  inputs.py        text(), dim(), text_list(), doc_refs()
  routes/          __init__.py (docstring), docs, board, onboard, analysis, machine, terminals, runs, team,
                   architecture, adr, app_cmd, jobs, files
.camarones/lib/serve.py, lib/appapi.py, lib/adr_api.py      facades
tests/fixtures/http_probe.py, tests/test_http_contract.py, tests/test_http_router.py, tests/test_http_server.py
```

## Areas

Paths as in `tests/snapshots/routes.json`; access is the snapshot's (public unless marked). Task 2 transcribes this
table into `AREA` in `tests/test_http_router.py`.

| Task | Area (`routes/<area>.py`) | Routes (pattern · access · flags) | Moves there from `serve.py` (unless noted) |
|---|---|---|---|
| 5 | `docs` | GET `/api/tree`, `/api/doc`, `/api/search`, `/api/check`, `/api/status`, `/api/ask`, `/api/reviews`; POST `/api/doc`, `/api/new`, `/api/confirm`, `/api/feedback`, `/api/commit`, `/api/review/decide`; POST `/api/ask/answer` · app | `api_ask`, `BLOCKS_TTL`, `_blocks_cache`, `_blocks_lock`, `_compute_blocks`, `_blocks`, `api_doc`, `api_search`, `write`, `create` |
| 6 | `board` | GET `/api/kanban`, `/api/kanban/item`, `/api/kanban/{which:next\|waves}`, `/api/stories`, `/api/stories/item`, `/api/stories/files`; POST `/api/kanban/{action:init\|add\|move\|assign\|link\|archive}` · portal, refusal "writing the board needs the machine token: open the portal with \`camaron up\`"; POST `/api/stories/{action:lint\|analyze}`; POST `/api/stories/save` · portal, refusal "saving a story needs the machine token: open the portal with \`camaron up\`"; POST `/api/stories/suggest` · portal, refusal "AI suggestions need the machine token: open the portal with \`camaron up\`" | `kanban_marks`, `kanban_state`, `Handler.kanban_post` and `Handler.stories_post` (bodies without their action and token checks), `_story_body`, `_task_list`, `_refuse_groups` |
| 7 | `onboard` | GET `/api/app/onboard/state`, `/api/app/onboard/tools`, `/api/app/onboard/stack`; POST `/api/app/onboard/{name:step\|repos\|setup\|scan\|stack\|arch\|done}` · all app | `app_onboard` (its `stack` branch calls `onboard.set_stack(str(b.get("repo", "")), text)`); `lib/onboard.py` gains `set_stack(repo: str, text: str \| None) -> dict` (`radar.set_stack(repo, text)`, then `return stack_rows()`) and its "serve.py only parses" comment names `lib/interfaces/http` |
| 8 | `analysis` | GET `/api/inventory`, `/api/schemas`, `/api/health`, `/api/ci`, `/api/codemap`, `/api/viewers`, `/api/wikis`; POST `/api/inventory`, `/api/schemas`, `/api/ci`, `/api/build`, `/api/wiki` · app | `api_schemas`, `schemas_write`, `api_inventory`, `inventory_job`, `first_look`, `build`, `wiki` (`/api/wiki` answers 409 when the result's `error` is `busy`) |
| 9 | `machine` | GET `/api/app/summary`, `/api/app/doctor`, `/api/app/kitdev`, `/api/app/machine`, `/api/app/guide`, `/api/app/creds`; POST `/api/app/doctor`, `/api/app/kitdev`, `/api/app/creds`, `/api/app/creds/test`, `/api/app/creds/delete`, `/api/app/tour-offered` · all app | `ui_lang`, `app_summary`, `app_kitdev`, `app_creds` (the three creds routes call it with `""`, `"/test"`, `"/delete"`); new `sessions_setting() -> str` (`machine.settings()["sessions"]`) |
| 10 | `terminals` | GET `/api/app/terminals`, `/api/app/terminals/stream`, `/api/app/agents`; POST `/api/app/terminals` and `/api/app/agent` (one handler); POST `/api/app/terminals/{tid:t-[\w.-]+-\d+}/{action:input\|resize\|close}` · `by=False`; POST `/api/app/units/{uid}/{action:takeover\|handback\|stop}` · `by=False`, `uid` unquoted · all app | `app_session`, `app_terminal`, `app_unit`, `STREAM_FROM`, `CHUNK`, `KEEP_ALIVE`, `Handler.stream_terminals` split into the handler (parses `from`, 400 on a bad piece) and `follow_terminals(out: BinaryIO, offsets: dict[str, int]) -> None` (the loop); new `unit_terminals() -> dict[str, str]` (today's `term` comprehension in `api_pipeline`) and `shutdown() -> None` (`terminals.shutdown()`, for `run_server`'s `atexit`) |
| 11 | `runs` | GET `/api/pipeline`, `/api/runs`, `/api/runs/{run:[\w.-]+}`, `/api/runs/{run:[\w.-]+}/events`, `/api/plan/cost`; POST `/api/units/retry`, `/api/units/approve`; POST `/api/runs`, `/api/runs/{run:[\w.-]+}/cancel`, `/api/plan/cost` · app | `STOPPED_AFTER`, `start_run`, `retry_unit`, `approve_unit`, `run_stopped`, `api_pipeline`, `Handler.stream_events` (its 204 is `Response(204, ctype=None)`, its loop an `event_stream`) |
| 12 | `team` | GET `/api/sync`, `/api/interview`, `/api/kpis`; POST `/api/sync/share`, `/api/interview/answer`, `/api/kpis/miss` | `api_interview`, `kpis_miss` |
| 13 | `architecture` | GET `/api/c4/view`; POST `/api/c4/{change:element\|confirm\|relation\|remove}` | `api_c4_view` (`"editable": not req.static`), `c4_change` (its `KeyError` answers 404 `not in the model: …`) |
| 14 | `adr` | GET `/api/app/adr{rest:(?:/.*)?}` (calls `get("adr" + rest, req.query)`); POST `/api/app/adr/{action:[a-z]+}` (calls `post(action, req.body, req.by)`) · app | all of `lib/adr_api.py` by `git mv`; its `_text`/`_text_list` replaced by `inputs.text`/`inputs.text_list` (same messages); `lib/adr_api.py` becomes a facade of `BUSY`, `get`, `post` (from `routes.adr`) and `covering` (from `portal_views`); `interfaces/cli/commands/adr.py` imports `BUSY` from `lib.interfaces.http.routes.adr` |
| 15 | `app_cmd` | GET `/api/app/info`, `/api/app/catalog`; POST `/api/app/cmd` (`PermissionError` → 409 with `"confirm": True`, `KeyError` → 404 `unknown command …`) · all app | all of `lib/appapi.py` by `git mv`; `lib/appapi.py` becomes a facade of `HUB`, `PROCS`, `catalog`, `entry`, `info`, `argv`, `start`, `stream_job`, `stoppable`, `cancel`; `routes/machine.py` and `serve.py` import `stream_job`/`stoppable`/`cancel` from `routes.app_cmd` |
| 16 | `jobs` | GET `/api/jobs`, `/api/jobs/{job}`; GET `/api/app/jobs/{job:[\w.-]+}/events`, POST `/api/app/jobs/{job:[\w.-]+}/cancel` · app | `cancel_job`, `Handler.stream_job` (as an `event_stream`; offset from `Last-Event-ID`, else `from`, else 0) |

`routes/files.py` (Task 17) holds every non-API GET, none in the snapshot: `/firstlook` (`static=True`),
`/raw/wikis/{rest:.*}`, `/raw/{rest:.*}`, `/vendor/{pkg:(?:@[\w.-]+/)?[\w.-]+}@{ver:[\w.+-]+}/{file:[\w./+-]+}`,
`/architecture/{rest:.*}`, `/code-graph/{repo:(?:[\w.-]+/?)?}`, `/wiki-graph/{repo:[\w.-]+}/{rest:.*}`, `/next` and
`/next/{rest:.*}` (301 `/`), `/desktop` (301 `/desktop/`), `/desktop/{rest:.*}`, `/` and `/index.html`, and the portal
fallback `/{rest:.*}` (a file of the portal build, else `index.html` for a path without a suffix, else `not found`).

---

### Task 1: The HTTP contract, written against today's server

**Files:**
- Create: `tests/fixtures/http_probe.py`, `tests/test_http_contract.py`
- Modify: `tests/test_routes_snapshot.py`, `tests/snapshots/routes.json`

**Interfaces:**
- Produces: `http_probe.SERVER = "lib.serve"` (Task 17 sets `"lib.interfaces.http.server"`), `APP_TOKEN = "app-token"`,
  `PORTAL_TOKEN = "portal-token"`; `arm(mp, *, static: bool = False) -> None` sets `APP_TOKEN`, `PORTAL_TOKEN` and
  `STATIC` on the `SERVER` module with `mp.setattr`; `serving(handler_cls) -> ContextManager[str]` runs a
  `ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)` in a daemon thread and yields its base URL;
  `request(base, method, path, body: bytes | None = None, token: str | None = None, *, marked: bool = True,
  host: str | None = None) -> tuple[int, dict[str, str], bytes]` (status, lower-cased headers, raw body; sends
  `Content-Type: application/json`, `X-Camarones: 1` when `marked`, `X-Camaron-Token` when `token`, `Host` when `host`).

- [ ] **Step 1: Snapshot entries.** Add `{"method": "POST", "path": "/api/app/creds/delete", "access": "app"}` and
  `{"method": "POST", "path": "/api/app/creds/test", "access": "app"}` to `routes.json`, keeping it sorted by
  `(path, method)`.

- [ ] **Step 2: Three tokens per route.** `test_routes_snapshot.py`'s `server` fixture uses `http_probe` (same module
  scope, same workspace); `test_route_access` is parametrized by `who in ("none", "portal", "app")` as well:

```python
token = {"none": None, "portal": PORTAL_TOKEN, "app": APP_TOKEN}[who]
if access == "app":
    status, answer = probe(server, method, path, b"{" if method == "POST" else None, token)
    if who != "app":
        assert (status, answer.get("app")) == (403, True)
    else:
        assert status == 400 if method == "POST" else status != 403
elif access == "portal":
    status, answer = probe(server, method, path, b"{}", token)
    assert (status, answer.get("token")) == (403, True) if who == "none" else status != 403
else:
    status, _ = probe(server, method, path, b"{" if method == "POST" else None, token)
    assert status == 400 if method == "POST" else status != 403
```

- [ ] **Step 3: The contract tests.** In `tests/test_http_contract.py`, each test builds its server from the `kit`
  fixture with `arm(monkeypatch, …)` and `serving(kit.serve.Handler)`:
  - `test_a_body_that_is_not_json_is_a_400_before_the_portal_token`: `POST /api/kanban/add` `b"{"` no token → 400;
    `POST /api/nope` `b"{"` → 400; `POST /api/nope` `b"{}"` → 404 `{"error": "not found"}`.
  - `test_get_matches_the_decoded_path_and_post_the_path_as_sent`: with `docs/a b.txt` holding `hi`,
    `GET /raw/a%20b.txt` → `(200, b"hi")`; `POST /api/app/units/a%2Fb/stop` `b"{}"` app token → 404
    `{"error": "no unit a/b"}`.
  - `test_unknown_paths_answer_by_their_place`: the five cases of the Review Focus line.
  - `test_static_mode_reads_the_export_and_refuses_writes`: write `<CACHE>/site/index.html` (`kit.common.CACHE`)
    with `<html>site</html>`, `arm(monkeypatch, static=True)`; `POST /api/doc` `b"{}"` `marked=False` → 405
    `{"error": "read-only portal — run \`camaron up\` to edit"}`; `GET /api/app/info` app token → 200;
    `GET /api/tree` → `(200, b"<html>site</html>")`.
  - `test_head_put_and_foreign_hosts`: `HEAD /api/tree` → 200, same `content-type` as GET, body `b""`;
    `PUT /api/new` `b"{}"` `marked=False` → 403, `PUT /api/new` `b"{"` → 400; `GET /api/tree` with
    `host="evil.test"` → 403 `{"error": "forbidden host"}`; `POST /api/new` `b"{}"` with `host="evil.test"` → 403
    `{"error": "forbidden"}`.

- [ ] **Step 4: Run them against today's server.**
  Run: `uv run pytest tests/test_routes_snapshot.py tests/test_http_contract.py -n auto`
  Expected: PASS (a failure is a wrong assumption about today: fix the test, never `serve.py`).

- [ ] **Step 5: Full suite and commit.** `uv run pytest -n auto`, then
  `git add tests/fixtures/http_probe.py tests/test_http_contract.py tests/test_routes_snapshot.py tests/snapshots/routes.json`
  and commit `test(http): the server's contract, every route probed with each token; creds test/delete in the snapshot`.

---

### Task 2: Messages and router, not wired

**Files:**
- Create: `.camarones/lib/interfaces/http/__init__.py`, `messages.py`, `router.py`, `routes/__init__.py`;
  `tests/test_http_router.py`

**Interfaces:**
- Produces, `messages.py` (stdlib only):
  - `@dataclass(frozen=True) class Request`: `method: str` ("GET" for GET/HEAD, "POST" for POST/PUT), `path: str`
    (P5), `query: dict[str, str]`, `headers: Mapping[str, str]`, `raw: bytes = b""`, `body: Any = None`,
    `params: dict[str, str]`, `by: str = ""`, `is_app: bool = False`, `can_write: bool = False`,
    `foreign: bool = False`, `marked: bool = False`, `static: bool = False` (dict fields default to empty).
  - `@dataclass(frozen=True) class Response`: `status: int = 200`, `body: bytes = b""`,
    `ctype: str | None = "text/plain"` (None: neither `Content-Type` nor `Content-Length`),
    `headers: Mapping[str, str]` (empty), `stream: Callable[[BinaryIO], None] | None = None`.
  - `json_response(data, status: int = 200) -> Response` (`json.dumps(data, ensure_ascii=False).encode()`,
    `application/json; charset=utf-8`); `not_found() -> Response` (404, `b"not found"`); `redirect(status: int,
    location: str) -> Response` (`b""`, `Location`); `event_stream(write: Callable[[BinaryIO], None]) -> Response`.
- Produces, `router.py` (imports `messages` and the stdlib only):
  - `class Access: PUBLIC = "public"; PORTAL = "portal"; APP = "app"`; `APP_ONLY_MSG` (today's text, moved in
    Task 17; until then `router.py` holds a copy and `serve.py` imports it from here in Task 3).
  - `@dataclass(frozen=True) class Route`: `method`, `pattern`, `access`, `handler`, `refusal: str = ""`,
    `by: bool = True`, `static: bool = False`; `Match(route: Route, params: dict[str, str])`.
  - `route(method, pattern, *, access=Access.PUBLIC, refusal="", by=True, static=False)`: appends a `Route` to the
    function's `__routes__` list and returns the function; raises `ValueError` naming the pattern for a method other
    than GET/POST, an unknown access, a pattern not starting with `/`, a pattern under `/api/app/` that is not APP,
    PORTAL without a refusal or a refusal on another access, `by=False` on GET, `static=True` on POST, or unbalanced or
    nested braces.
  - `class Router`: `__init__(self, routes: Iterable[Route])` (`ValueError` on a repeated `(method, pattern)`);
    `candidates(method, path) -> list[Match]` (P6 order); `match(method, path) -> Match | None`;
    `table() -> list[dict]` (`method`, `pattern`, `access`, sorted by pattern then method); `routes: tuple[Route, ...]`.
  - `load() -> Router`: every module of `lib.interfaces.http.routes` (`pkgutil.iter_modules`, sorted by name), every
    `__routes__` of its functions in source order; cached per process (`functools.cache`).

- [ ] **Step 1: Write the failing tests** in `tests/test_http_router.py`, on routers built from decorated test
  functions (`Router([*f.__routes__, …])`):
  - `test_parameters_come_from_the_path`: `/api/app/units/{uid}/{action:takeover|handback|stop}` matches
    `/api/app/units/a%2Fb/stop` with `{"uid": "a%2Fb", "action": "stop"}`; `/api/app/units/a/b/stop` does not match.
  - `test_the_most_specific_route_wins`: `/api/x/candidates` over `/api/x/{id}`; `/` over `/{rest:.*}` for `/`;
    `/raw/wikis/{rest:.*}` over `/raw/{rest:.*}`; `/next/{rest:.*}` over `/{rest:.*}`.
  - `test_a_path_under_api_matches_only_api_patterns`: with only `GET /{rest:.*}`, `match("GET", "/api/x") is None`
    and `match("GET", "/x")` matches.
  - `test_the_method_is_part_of_the_route`: a GET route never matches POST.
  - `test_bad_declarations_are_refused`: one `pytest.raises(ValueError)` per refusal listed in Interfaces.
  - `test_a_repeated_route_is_refused`; `test_one_function_carries_several_routes`; `test_the_table_is_sorted`.
  - The area tests (using the `kit` fixture: route modules import kit modules): `SNAP` (from `routes.json`),
    `AREA: dict[tuple[str, str], str]` transcribed from the Areas table (117 entries), `MOVED: set[str] = set()`;
    `test_every_snapshot_route_has_an_area` (`set(AREA) == set(SNAP)`);
    `test_moved_areas_are_routed` (for each entry whose area is in `MOVED`: `load().match` finds a route with the
    snapshot's access whose `handler.__module__ == f"lib.interfaces.http.routes.{area}"`);
    `test_every_declared_api_route_is_in_the_snapshot` (each declared `/api/` route matches at least one snapshot
    entry of its method, and the snapshot's access equals the route's).

- [ ] **Step 2: Run to verify they fail**
  Run: `uv run pytest tests/test_http_router.py -v`
  Expected: FAIL with `ModuleNotFoundError: lib.interfaces.http`.

- [ ] **Step 3: Implement `messages.py`, `router.py` and the two docstring-only `__init__.py` files.**
  Pattern compile: escape the literal text, `{name}` → `(?P<name>[^/]+)`, `{name:rx}` → `(?P<name>rx)`,
  `re.fullmatch`; keep the literal prefix and whether the pattern has parameters for P6's sort key.

- [ ] **Step 4: Run to verify they pass**
  Run: `uv run pytest tests/test_http_router.py tests/test_architecture.py -v`
  Expected: PASS (`interfaces.*` already has its layer; nothing joins a cycle).

- [ ] **Step 5: Full suite and commit.** `uv run pytest -n auto`; `git add .camarones/lib/interfaces/http tests/test_http_router.py`;
  commit `feat(http): request, response and a router of declared routes under lib/interfaces/http, not wired yet`.

---

### Task 3: `serve.Handler` asks the router first; jobs and body checks get their own modules

**Files:**
- Create: `.camarones/lib/interfaces/http/jobs.py`, `.camarones/lib/interfaces/http/inputs.py`,
  `tests/test_http_server.py`
- Modify: `.camarones/lib/serve.py`

**Interfaces:**
- Consumes: Task 2's `messages`, `router` (`router.load()` called at request time through the module, so a test can
  patch `load`).
- Produces: `jobs.py` with today's `JOBS`, `JOB_IDS`, `JOB_LOCK`, `CANCEL`, `start_job`, `claim_job`, `fail_job`,
  `run_job`, `job_running` (moved verbatim, stdlib only); `inputs.py` with today's `_text`, `_dim`, `_text_list`,
  `_doc_refs` renamed `text`, `dim`, `text_list`, `doc_refs` (bodies and messages unchanged);
  `serve.Handler.reply(resp: Response) -> None` (stream: 200, `Content-Type: text/event-stream; charset=utf-8`,
  `Cache-Control: no-store`, `end_headers`, `resp.stream(self.wfile)`; otherwise `send_response(status)`, then
  `Content-Type` and `Content-Length` when `ctype` is set, `Cache-Control: no-store`, `resp.headers`, `end_headers`,
  the body unless HEAD).

- [ ] **Step 1: Write the failing tests** in `tests/test_http_server.py`: each patches
  `lib.interfaces.http.router.load` to return a `Router` of routes declared in the test, and serves
  `kit.serve.Handler` through `http_probe`:
  - `test_a_declared_route_answers_through_the_server`: GET `/api/zz?a=1&a=2` → handler returns
    `json_response(req.query)` → `{"a": "1"}`.
  - `test_a_portal_route_refuses_with_its_own_message`: POST `/api/zz/save` PORTAL refusal `"need the token"` → 403
    `{"error": "need the token", "token": True}` with no token, 200 with the portal token.
  - `test_an_app_route_outside_api_app_needs_the_app_token`: POST `/api/zz/run` APP → 403 `"app": True` with no
    token and with the portal token, 200 with the app token.
  - `test_by_is_resolved_only_where_the_route_asks`: a `by=True` route echoing `req.by` answers `"ana"` for body
    `{"by": " ana "}`; a `by=False` one answers `""`.
  - `test_post_parameters_come_from_the_path_as_sent`: POST `/api/zz/{id}/x` with `/api/zz/a%2Fb/x` → `{"id": "a%2Fb"}`.
  - `test_a_response_without_a_type_has_neither_type_nor_length`: `Response(204, ctype=None)` → 204, no
    `content-type`, no `content-length`.
  - `test_an_event_stream_answers_with_its_headers`: `event_stream(lambda out: out.write(b"data: 1\n\n"))` → 200,
    `text/event-stream; charset=utf-8`, body `b"data: 1\n\n"`.
  - `test_head_on_a_routed_get_has_no_body`.
  - `test_handler_errors_map_as_today`: GET raising `KeyError("k")` → 404 `{"error": "missing or unknown: 'k'"}`;
    POST raising `ValueError("bad")` → 400 `{"error": "bad"}`; GET raising `OSError("x")` → 500 `{"error": "OSError: x"}`.

- [ ] **Step 2: Run to verify they fail**
  Run: `uv run pytest tests/test_http_server.py -v`
  Expected: FAIL (the handler never asks the router: 404s).

- [ ] **Step 3: Wire the router into `serve.Handler`.**
  - `do_GET`, inside the `try`, replacing the `/api/app/` branch:
    `hit = router.load().match("GET", p)`; if (`p` is under `/api/app/` or `hit` is APP) and not `self.is_app()` →
    today's 403; if `hit` and (not `STATIC` or `p` is under `/api/app/` or `hit.route.static`) →
    `return self.reply(hit.route.handler(<Request>))`; then `if p.startswith("/api/app/"): return self.api_app_get(…)`
    and the rest unchanged.
  - `do_POST`: the APP gate also refuses when the POST route matched for `p` is APP; after `json.loads`, before the
    terminal and unit regexes: if a route matched, `by` = today's expression when `hit.route.by` else `""`; PORTAL and
    not `self.can_write()` → 403 `{"error": hit.route.refusal, "token": True}`; then reply with the handler's response.
  - The `Request` carries `query` (GET), `body` (POST, else `{}`), `params`, `by`, `headers`, `is_app`,
    `can_write`, `static=STATIC`.
  - `serve.py` imports the job names from `interfaces.http.jobs` and the body checks from `interfaces.http.inputs`
    (call sites renamed), and `APP_ONLY_MSG` from `router`.

- [ ] **Step 4: Run to verify they pass**
  Run: `uv run pytest tests/test_http_server.py tests/test_http_contract.py tests/test_routes_snapshot.py tests/test_architecture.py -n auto`
  Expected: PASS; the allowlist does not change (`jobs`, `inputs`, `router` import no adapter).

- [ ] **Step 5: Full suite and commit.** `uv run pytest -n auto`; `git add` the two new modules, `serve.py`,
  `tests/test_http_server.py`; commit `refactor(http): serve asks the router first; jobs and body checks in lib/interfaces/http`.

---

### Task 4: The portal's views move to `lib/app/portal_views.py`

**Files:**
- Create: `.camarones/lib/app/__init__.py`, `.camarones/lib/app/portal_views.py`
- Modify: `.camarones/lib/serve.py`, `.camarones/lib/env.py` (the static export), `.camarones/lib/adr_api.py`,
  `.camarones/lib/interfaces/cli/commands/adr.py`, `.camarones/lib/interfaces/cli/commands/skills.py`,
  `tests/architecture/allowlist.yaml`

**Interfaces:**
- Produces: `portal_views.APP`, `UI`, `UI_LIBS`, `reviewer() -> str`, `doc_file(path: str, lang: str = "") -> Path`,
  `tree() -> dict`, `read(path: str, lang: str = "") -> dict`, `status(check: bool = True) -> dict`,
  `covering(logical: str) -> list[dict]` (from `adr_api`, logger `camaron.adr_api`),
  `code_map(repo: str) -> dict | None` (today's `/api/codemap` lookup: `codemap.load(repo)` when `repo` is one of
  `docs.repo_names()`, else None); `_with_adr_status`, `_is_decision`, `_source_info` move with them.

- [ ] **Step 1: Allowlist first.** Remove `env -> serve`, `env -> adr_api`, `serve -> codemap`; add
  `app.portal_views -> codemap`. Run `uv run pytest tests/test_architecture.py`. Expected: FAIL (the old imports
  still happen).
- [ ] **Step 2: Move.** The names above go to `portal_views.py`. `serve.py` imports them back (P11) and its
  `/api/codemap` branch calls `portal_views.code_map(q.get("repo", ""))`; `api_doc` calls `portal_views.covering`.
  `env.py`'s export reads `portal_views.UI`, `tree`, `read`, `status`, `UI_LIBS`, `covering` and no longer imports
  `serve` or `adr_api`. `adr_api.covering` becomes an import of `portal_views.covering`. The two CLI commands call
  `portal_views.reviewer()`.
- [ ] **Step 3: Run.** `uv run pytest tests/test_architecture.py tests/test_portal_smoke.py tests/test_portal_data.py tests/test_freshness.py -n auto`.
  Lower `largest_cycle` and `cycle_modules` to what the test measures (`serve` and possibly `adr_api` leave `env`'s
  cycle, `portal_views` joins it). Expected: PASS.
- [ ] **Step 4: Full suite and commit.** `uv run pytest -n auto`; commit
  `refactor(http): the portal's views, shared with the static export, move to lib/app/portal_views.py` (violations
  N → N−2).

---

### Area move procedure (Tasks 5–16)

Each area task applies these steps to its row of the Areas table. Names: area `A`, module
`.camarones/lib/interfaces/http/routes/A.py`.

- [ ] **Step 1: Tests first.** Add `A` to `MOVED` in `tests/test_http_router.py`; apply the row's allowlist renames
  (owner table: `serve -> X` becomes `interfaces.http.routes.A -> X`; Tasks 5, 7 and 12–16 rename none). Run
  `uv run pytest tests/test_http_router.py tests/test_architecture.py -v`. Expected: FAIL (`A`'s routes are not
  declared; the renamed lines do not happen yet).
- [ ] **Step 2: Move.** Create `routes/A.py`: the row's functions and constants, verbatim (P9, P10), and one handler
  per route with the row's pattern, access, refusal and flags. Handlers return `json_response(...)` (a function that
  returns `(dict, code)` is called as `json_response(*f(...))`). Delete the moved functions and every branch serving
  the row's paths from `serve.py` (`api_get`, `api_app_get`, `do_POST`, the `Handler` methods named in the row), then
  import the row's public names back into `serve.py` (P11). Other HTTP modules reach an adapter through its owner.
- [ ] **Step 3: Retarget tests.** Run the area's tests (the row's "Tests" in the table below); a test that patches or
  reads a moved name's state, a private helper or `serve.env`/`serve.docs` moves to the defining module (P11).
- [ ] **Step 4: Run.**
  `uv run pytest tests/test_http_router.py tests/test_routes_snapshot.py tests/test_http_contract.py tests/test_http_server.py tests/test_architecture.py <area tests> -n auto`
  Expected: PASS; follow `test_big_files_are_listed` if `serve` drops under 600 lines. If the sandbox exists
  (AGENTS.md §2.2): `uv run scripts/sandbox.py cli up`, one GET of the area answers 200 as before,
  `uv run scripts/sandbox.py cli down`.
- [ ] **Step 5: Full suite and commit.** `uv run pytest -n auto`; `git add` the new module, `serve.py` and what the
  row names, the allowlist and the touched tests; commit `refactor(http): <area> routes move to interfaces/http/routes/<A>.py`;
  the body lists the routes, the violation count before → after, and ends with "Nothing a user notices."

| Task | Area | Allowlist renames | Tests to run and retarget |
|---|---|---|---|
| 5 | `docs` | none | `test_portal_actions`, `test_portal_app` (`kit.serve.docs` → `kit.docs`), `test_ask_retrieval`, `test_ask_ai`, `test_ask_review`, `test_diagram_blocks` (`serve._compute_blocks`, `_blocks`, `_blocks_cache`, `serve.docs` → `routes.docs` / `docs`), `test_source_links`, `test_freshness`, `test_usage` |
| 6 | `board` | `kanban`, `kanban.index` | `test_portal_kanban`, `test_portal_stories`, `test_boards_removed` |
| 7 | `onboard` | none (`lib/onboard.py` already imports `radar`) | `test_onboard_api` (add `test_set_stack_returns_the_stack_rows`: after `onboard.set_stack(repo, "Java 21")` the returned rows equal `onboard.stack_rows()`), `test_agents` |
| 8 | `analysis` | `diagrams`, `inventory`, `quickarch`, `radar`, `schemas` | `test_inventory`, `test_schemas`, `test_health`, `test_health_sonar`, `test_ci_view`, `test_wiki_from_portal`, `test_portal_smoke`, `test_pages`, `test_diagram_blocks`, `test_app_api` (`serve.env` → `kit.env` where it patches `which`, `wiki_graph`, `build_c4`) |
| 9 | `machine` | `machine`, `creds` | `test_machine`, `test_app_summary`, `test_kitdev`, `test_guide`, `test_app_api` (creds) |
| 10 | `terminals` | `terminals` | `test_terminals_api` (`KEEP_ALIVE` and the stream wrapper patch `routes.terminals.KEEP_ALIVE` and `follow_terminals`), `test_agent_sessions`, `test_agents` |
| 11 | `runs` | `harness.events` | `test_portal_pipeline` (`STOPPED_AFTER` → `routes.runs`), `test_scheduler`, `test_unit_titles`, `test_kpis_view` |
| 12 | `team` | none | `test_sync`, `test_interview_online`, `test_questionnaire`, `test_kpis_view` |
| 13 | `architecture` | none | `test_c4_edit` |
| 14 | `adr` | none (`env -> adr_api` left in Task 4) | the ADR tests (`grep -l adr_api tests`), `test_cli_snapshot` |
| 15 | `app_cmd` | none | `test_app_api`, `test_kitdev`, `test_desktop_renderer` |
| 16 | `jobs` | none | `test_app_api`, `test_wiki_from_portal`, `test_portal_actions` |

---

### Task 17: The transport moves to `server.py`; the gates live in `router.dispatch`; `serve.py` becomes a facade

**Files:**
- Move: `.camarones/lib/serve.py` → `.camarones/lib/interfaces/http/server.py` (`git mv`), then a new facade at
  `.camarones/lib/serve.py`
- Create: `.camarones/lib/interfaces/http/routes/files.py`
- Modify: `.camarones/lib/interfaces/http/router.py`, `.camarones/lib/interfaces/cli/commands/machine.py`,
  `tests/fixtures/http_probe.py`, `tests/test_routes_snapshot.py`, `tests/test_http_router.py`, the token-patching
  tests, `tests/architecture/allowlist.yaml`, `AGENTS.md`

**Interfaces:**
- Consumes: every area module; `routes.terminals.shutdown`; `portal_views.reviewer`, `APP`.
- Produces: `router.dispatch(req: Request, static_site: Callable[[str], Response]) -> Response` (P7) and
  `router.error_response(method: str, exc: Exception) -> Response` (GET: `KeyError` → 404
  `missing or unknown: …`, other → 500 `Type: …`; POST: `KeyError`/`ValueError`/`RuntimeError` → 400 `str(e)`, other
  → 500); `files.static_site(path: str) -> Response` (today's `get_static_site`), `files.file_response(f: Path,
  local_cdn: bool = False) -> Response`, `files.static_response(base: Path, rel: str, local_cdn: bool = False,
  spa: bool = False) -> Response | None`, `files.cdn_local`, `DESKTOP`, `SITE`, and the `mimetypes.add_type` calls;
  `server.Handler` (reads the body first, builds the `Request` — `foreign` from today's `foreign_host`, `marked`,
  tokens through `token_matches` — calls `router.dispatch(req, files.static_site)` and writes the `Response` as
  Task 3's `reply`, the stream inside `error_response`'s mapping; HEAD → GET, PUT → POST), `token_matches`,
  `APP_TOKEN`, `PORTAL_TOKEN`, `STATIC`, `APP_GONE_GRACE`, `take_tokens`, `watch_app`, `run_server` (its `atexit`
  registers `routes.terminals.shutdown`, its static check reads `files.SITE`).

- [ ] **Step 1: Tests first.**
  - `tests/test_http_router.py`: `MOVED` holds every area; `test_moved_areas_are_routed` also asserts
    `len(load().candidates(method, path)) == 1`; new `test_serve_is_a_facade_of_the_http_interface`
    (`import_module("lib.serve").__facade__ == "lib.interfaces.http"` and `not hasattr(serve, "APP_ONLY")`).
  - `tests/test_routes_snapshot.py`: `test_every_literal_route_in_serve_is_listed` and `literal_paths` give way to
    `test_no_route_path_is_spelled_outside_a_declaration`: no string constant matching `^/api/[\w/.-]*\w$` appears in
    `.camarones/lib/interfaces/http/**/*.py` except as the second argument of a `route(...)` call.
  - `http_probe.SERVER = "lib.interfaces.http.server"`.
  Run `uv run pytest tests/test_http_router.py tests/test_routes_snapshot.py -v`. Expected: FAIL.
- [ ] **Step 2: Move.** `git mv` `serve.py` to `server.py`; the non-API GETs become `routes/files.py` (P9 patterns,
  listed under the Areas table); `dispatch` and `error_response` go into `router.py` (its `by` default imports
  `portal_views.reviewer` inside the function); `APP_ONLY`, `TERMINAL_POST`, `UNIT_POST`, `ONBOARD_POST`,
  `VENDOR_RE` and `get_static_site` disappear; `APP_ONLY_MSG` lives only in `router.py`. `server.py` keeps only the
  transport names of Interfaces.
- [ ] **Step 3: The facade.** `lib/serve.py`: a docstring ("the project server moved to lib/interfaces/http; this path
  stays for old imports"), explicit imports of every public name today's `serve.py` defined that still exists, from
  its new home (`server`, `router`, `jobs`, `portal_views`, the route modules), except the state and tunables
  `STATIC`, `APP_TOKEN`, `PORTAL_TOKEN`, `APP_GONE_GRACE`, `STOPPED_AFTER`, `KEEP_ALIVE`, `CHUNK`, `BLOCKS_TTL`;
  `__facade__ = "lib.interfaces.http"`; `__all__`. `interfaces/cli/commands/machine.py` imports `run_server` from
  `lib.interfaces.http.server`.
- [ ] **Step 4: Retarget the state.** Tests that set or read the tokens on `kit.serve` (none touch `STATIC` or
  `APP_GONE_GRACE` today)
  (`grep -rn "serve, \"APP_TOKEN\"\|serve, \"PORTAL_TOKEN\"\|serve.PORTAL_TOKEN\|serve.APP_TOKEN" tests`: among them
  `test_portal_kanban.py:363-368`, `test_guide.py:180`) use `lib.interfaces.http.server`.
- [ ] **Step 5: Allowlist and docs.** Run `uv run pytest tests/test_architecture.py`: `oversize` drops `serve`; the
  violations are the 12 of the owner table's end state; lower the cycle records if they shrink. AGENTS.md §4: the
  `.camarones/lib/` row says `serve` (facade of `interfaces/http`), `adr_api` and `appapi` (facades of
  `interfaces/http/routes/adr` and `app_cmd`); new rows for `.camarones/lib/interfaces/http/` ("the project server:
  `router` matches declared routes and applies the gates — app token, portal token, `X-Camarones`, host — in one
  place; `routes/<area>.py` one module per area; `server` the transport; `jobs` the background jobs; `inputs` body
  checks") and `.camarones/lib/app/` ("use cases; `portal_views` the docs as the portal shows them, for the server and
  the static export"); the desktop row names `lib/interfaces/http/routes/app_cmd.py` and `routes/adr.py` instead of
  `lib/appapi.py` and `lib/adr_api.py`. The guides name no HTTP module (`grep -n "serve\.py\|appapi\|adr_api"
  .camarones/templates/docs/guides/*.md .camarones/templates/docs/i18n/es/guides/*.md` prints nothing): say so in the
  commit body.
- [ ] **Step 6: Run, then the sandbox.**
  `uv run pytest tests/test_http_router.py tests/test_http_server.py tests/test_http_contract.py tests/test_routes_snapshot.py tests/test_architecture.py tests/test_server_lifeline.py tests/test_portal_smoke.py -n auto`,
  then `uv run pytest -n auto`. Expected: PASS. If the sandbox exists (else `reset` creates it; say so):
  `uv run scripts/sandbox.py cli up`; `/`, `/api/tree`, `/desktop/` and one `/raw/…` image answer as on `main`;
  `uv run scripts/sandbox.py cli down`.
- [ ] **Step 7: Commit** `refactor(http): the server's transport moves to interfaces/http/server.py, its gates to router.dispatch; serve.py is a facade`
  (violations before → after; "Nothing a user notices.").

---

### Task 18: The living docs of camaron-dev

**Files:** pages under `cam-docs/docs/` of the camaron-dev workspace (outside this repo) that name `lib/serve.py`,
`lib/appapi.py` or `lib/adr_api.py`.

- [ ] **Step 1:** Follow the `cam-docs-update` skill: `grep -rln "serve\.py\|appapi\|adr_api" cam-docs/docs`; on a
  `draft` page point to the new module; a `confirmed` page gets a `propose_edit`, never a direct rewrite.
- [ ] **Step 2:** `camaron check` from the workspace: no new error. Commit in `cam-docs` (`docs: the kit's HTTP layer
  lives in lib/interfaces/http`).
