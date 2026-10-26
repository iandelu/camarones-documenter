# User stories (Historias) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A *Historias* zone and `camaron board story|next|waves` that write a story, check it against INVEST, split it
into subtasks with computed footprints, dependencies, conflicts and waves, and a start gate so agents never work on
colliding tasks at the same time — all deterministic, AI optional and off by default.

**Architecture:** Pure functions do the work (`lib/stories.py` for story text, INVEST and splitting;
`lib/kanban/deps.py` for order, conflicts and waves). `lib/kanban/index.py` is a derived SQLite index (stdlib) that
feeds them from the cards and the code graph. Cards stay Backlog.md files; only `dependencies` and `x-touches` are
stored. The portal gets a `Stories.jsx` view over new `/api/stories/*` routes; the Kanban gets badges and the gate.

**Tech Stack:** Python 3 stdlib (`sqlite3`, `hashlib`), PyYAML (already a dep), pytest; React 19 + Vite + Vitest in
`.camarones/portal/app`.

**Spec:** [docs/superpowers/specs/2026-10-26-user-stories-design.md](../specs/2026-10-26-user-stories-design.md)

## Global Constraints

- macOS, Windows, Linux: `pathlib` only, `encoding="utf-8"`, LF (`newline="\n"`), processes via `lib/common.py`
  helpers, OS branches via `IS_WIN`/`IS_MAC` (AGENTS.md §2.1).
- TDD: failing test first; tests offline with `make_workspace`/`isolated_env`/`kit`/`wired` fixtures; run
  `uv run pytest -n auto` from the repo root; portal tests `npm test` in `.camarones/portal/app`.
- No new dependency: SQLite is `sqlite3` from the stdlib.
- Backward compatibility: a 3.x/4.x board without `x-touches`, with epics only, opens and lists exactly as before;
  `board move` with no collision behaves exactly as before.
- Stored in git: only `dependencies` (Backlog.md field) and `x-touches` (`<repo>:<posix path>`, sorted, unique;
  `cam-docs:` for doc pages). Conflicts, waves, groups, verdicts are never stored.
- Thresholds (defaults, overridable in `workspace.yaml → stories.small`): `groups: 3`, `files: 15`, `repos: 2`.
  Lint: `too-long` at 280 characters; `so-repeats-want` above 60% shared content words. Titles ≤ 80 (story, from the
  want) and ≤ 120 (tasks). Subtask ideas from AI ≤ 8. AI timeout 90 s.
- Verdict: `good` all letters pass; `poor` when `empty` is present or 3+ letters fail; `improve` otherwise.
- Wave tie-break: priority (P0 first, none last), then id (numeric).
- Start gate: surfaces `cli`/`portal`/`app` are people (refused unless `force=True`); `mcp`/`harness` are agents
  (always refused). Items without `x-touches` count as touching all of their `x-repos` (or everything) — for agents.
- AI: `stories: {ai: true}` turns on `suggest`; default off. It never decides footprints, dependencies, waves or the
  verdict.
- User-facing strings in es + en; no jokes in errors, prompts or `--json` (AGENTS.md §3).
- Conventional commits, staging only this plan's files (other sessions may edit the tree). Note: git in this checkout
  refuses to run ("dubious ownership"); the executor asks the user before working around it (e.g. per-command
  `git -c safe.directory=<repo> …`), never edits global git config unasked.
- README (Spanish), `lib/tutorial.py` + regenerated `TUTORIAL.md`, `templates/docs/guides/tutorial.md` and its es twin
  move with the code (Task 15); bump `VERSIONS["kit"]` minor (4.62.0 → 4.63.0).

## Review Focus

- `x-touches` typed with backslashes, `./`, trailing spaces or different case → stored as clean POSIX
  `repo:path`; on case-insensitive filesystems (`IS_WIN`/`IS_MAC`) two spellings of one file are one entry and
  conflict with each other. Test in Task 4.
- A dependency on an **archived** item (moved to `archive/tasks/` after Done) counts as done, not unknown, for the
  gate and `next`. Test in Task 6.
- Hand-written scalar fields (`dependencies: WI-3`, `x-touches: api:a.py`) behave like one-element lists everywhere
  (deps, index, gate). Test in Task 5.
- Two processes (portal server and CLI) rebuilding the index at once: neither crashes nor reads a half-written db.
  Test in Task 5.
- An existing story whose description has the three clauses **and** extra notes, or none of the clauses: saving keeps
  every line of the notes, in order, below the clauses. Test in Task 8.

---

## File map

| File | Responsibility |
|---|---|
| `.camarones/lib/stories.py` (new) | story text (parse, compose, title, fingerprint, lint), INVEST, split proposals, `analyze`, `save`, `list_stories`, `item` |
| `.camarones/lib/stories_ai.py` (new) | the optional `suggest` call (kept apart so the deterministic module never imports a runner) |
| `.camarones/lib/kanban/deps.py` (new) | pure: footprint normalisation, order, conflicts, waves, cycles, readiness |
| `.camarones/lib/kanban/index.py` (new) | SQLite index: snapshot, build, queries |
| `.camarones/lib/kanban/ops.py` | `add` new params, `_row` new keys, `list_items(parent=)`, `move` gate, `next_items`, `waves` |
| `.camarones/lib/kanban/repair.py` | subtasks in step for any parent; warnings for missing touches and cycles |
| `.camarones/lib/kanban/cli.py` | actions `story`, `next`, `waves`; `--force`, `--accept`, `--n`, `--story`, `--touch` |
| `.camarones/lib/codemap.py` | `file_edges(repo)`, `group_of(repo)` |
| `.camarones/lib/serve.py` | `/api/stories*`, `/api/kanban/next`, `/api/kanban/waves`, move `force` + 409 |
| `.camarones/lib/mcp.py` | tools `board_next`, `board_waves` |
| `.camarones/templates/board/{es,en}/story-lint.yaml`, `split.yaml` (new) | word lists, split templates |
| `.camarones/portal/app/src/stories.js`, `Stories.jsx` (new) | view helpers and screen |
| `.camarones/portal/app/src/{zones,router,kanban}.js`, `Kanban.jsx`, `i18n/portal.js`, `main.jsx`/shell | zone, route, badges, gate confirm |
| `tests/fixtures/story_lint_cases.json` (new) | one case table shared by pytest and Vitest |

---

### Task 1: Story text — parse, compose, title, fingerprint, lint

**Files:**
- Create: `.camarones/lib/stories.py`, `.camarones/templates/board/es/story-lint.yaml`,
  `.camarones/templates/board/en/story-lint.yaml`, `tests/fixtures/story_lint_cases.json`
- Test: `tests/test_stories_text.py`

**Interfaces:**
- Produces:
  - `Clauses = TypedDict("Clauses", {"as_": str, "want": str, "so": str, "rest": str})`
  - `parse(text: str, lang: str) -> Clauses` — accepts both languages' markers regardless of `lang`.
  - `compose(as_: str, want: str, so: str, lang: str) -> str` — es `"Como {as_},\nquiero {want},\npara {so}."`, en
    `"As {as_},\nI want {want},\nso that {so}."`; strips a trailing `.`/`,` from each clause first.
  - `title_for(want: str) -> str` — first letter upper-cased, ≤ 80 chars cut on a word boundary, no trailing
    punctuation.
  - `fingerprint(as_: str, want: str, so: str) -> str` — first 8 hex of sha256 over the three clauses lower-cased,
    whitespace collapsed, joined by `"\n"`.
  - `Hint = TypedDict("Hint", {"code": str, "field": str, "message": str})`; `lint(as_, want, so, lang, *,
    touches: Sequence[str] = ()) -> list[Hint]`, codes in this order: `empty`, `generic-role`, `two-goals`,
    `so-repeats-want`, `too-long`, `solution-in-want`, `no-footprint`.
  - `lint_words(lang: str) -> dict[str, list[str]]` — the YAML as loaded (keys: `generic_roles`, `conjunctions`,
    `solution_words`, `observable_verbs`, `stopwords`), served to the UI later.

- [ ] **Step 1: Write the case table** `tests/fixtures/story_lint_cases.json`: a list of
  `{"lang", "as", "want", "so", "touches", "codes"}`; at least one positive and one negative per code in es and in en,
  e.g. `{"lang":"es","as":"usuario","want":"exportar a PDF","so":"compartirla","touches":["portal:a.py"],
  "codes":["generic-role"]}` and `{"lang":"en","as":"service owner","want":"export to PDF and share it","so":"send it
  to people without portal access","touches":["portal:a.py"],"codes":["two-goals"]}`.

- [ ] **Step 2: Write the failing tests** in `tests/test_stories_text.py`:
  - `test_parse_es_and_en`: `parse("Como dev,\nquiero X,\npara Y.\n\nNotas", "es") == {"as_": "dev", "want": "X",
    "so": "Y", "rest": "Notas"}`; the same text with `As a dev, I want X so that Y` on one line parses in either lang.
  - `test_parse_without_clauses_keeps_everything_in_rest`: `parse("Arreglar el login", "es")["rest"] == "Arreglar el
    login"` and the three clauses are `""`.
  - `test_compose_round_trip`: for template-shaped text `t`, `compose(**parse(t)…) + rest == t` (es and en).
  - `test_title_for`: `title_for("exportar una página a PDF") == "Exportar una página a PDF"`; an 120-char want gives
    ≤ 80 chars ending on a whole word.
  - `test_fingerprint_ignores_case_and_spacing`: `fingerprint("Dev ", "x  y", "z") == fingerprint("dev", "X y", "Z")`
    and differs from `fingerprint("dev", "x", "z")`.
  - `test_lint_cases`: for every row of the JSON table, `[h["code"] for h in lint(...)] == row["codes"]`.

- [ ] **Step 3: Run** `uv run pytest tests/test_stories_text.py -v` — Expected: FAIL (`ModuleNotFoundError: lib.stories`).

- [ ] **Step 4: Implement** the YAML word lists and the functions above in `.camarones/lib/stories.py` (module
  docstring in the style of `lib/answers.py`). `two-goals`: a conjunction from `conjunctions` followed (within two
  words) by a word ending in an infinitive suffix (es `ar|er|ir`, en: the next word is not a stopword and the want has
  two verbs from a short list in the YAML `verbs` key). `so-repeats-want`: content words = words ≥ 4 letters not in
  `stopwords`; share of the so's content words found in the want > 0.6. Messages from a `MESSAGES` dict keyed by
  `(lang, code)`.

- [ ] **Step 5: Run** the same command — Expected: PASS.

- [ ] **Step 6: Commit** `feat(stories): story text parsing and instant hints`.

### Task 2: Code graph — full file edges and groups

**Files:**
- Modify: `.camarones/lib/codemap.py` (extract the owner/edge loop of `build` into `_file_edges(g) -> Counter`)
- Test: `tests/test_codemap.py`

**Interfaces:**
- Produces:
  - `file_edges(repo: str) -> set[tuple[str, str]]` — every `(src_path, dst_path)` with a `DEP_RELATIONS` link, tests
    and non-code files excluded exactly as `build` does, **not** truncated to `NEIGHBOURS`. Empty set when the repo has
    no graph.
  - `group_of(repo: str) -> dict[str, str]` — path → group label from `load(repo)` (`files[i]["path"]` →
    `groups[files[i]["group"]]["label"]`); `{}` without a graph.
  - Paths are graphify's `source_file`, relative to the repo root, POSIX.

- [ ] **Step 1: Failing tests** (reuse `GRAPH`/`write_graph` of the file):
  - `test_file_edges_are_complete`: with `GRAPH`, `("api-web/src/main/java/demo/shop/web/OrderResource.java",
    JAVA + "orders/OrderService.java") in file_edges("api")`, no edge from the test file, none to `""`; a graph with
    20 callers of one file yields all 20 edges.
  - `test_group_of_matches_the_map`: every path in `load("api")["files"]` is a key of `group_of("api")` and maps to its
    group's label; `group_of("nope") == {}`.
  - `test_build_unchanged`: `build("api")` equals the value before the refactor (compare to a literal of the current
    `links`/`files[*].out` for `GRAPH`).
- [ ] **Step 2: Run** `uv run pytest tests/test_codemap.py -v` — Expected: the two new tests FAIL.
- [ ] **Step 3: Implement** `_file_edges`, `file_edges`, `group_of`; `build` calls `_file_edges`.
- [ ] **Step 4: Run** — Expected: PASS (all of `test_codemap.py`).
- [ ] **Step 5: Commit** `feat(codemap): full file-level edges and group lookup`.

### Task 3: Dependencies, conflicts and waves (pure)

**Files:**
- Create: `.camarones/lib/kanban/deps.py`
- Test: `tests/test_kanban_deps.py`

**Interfaces:**
- Produces (plain data in, plain data out; no I/O):
  - `norm_touch(ref: str, *, fold: bool) -> str` — `repo:path` with `\` → `/`, leading `./` and surrounding spaces
    removed, `..` refused (`ValueError`); `fold=True` lower-cases the path for comparison keys only.
  - `Node = TypedDict("Node", {"id": str, "status": str, "priority": str | None, "touches": list[str], "repos":
    list[str], "deps": list[str], "archived": bool})`
  - `ALL = "*"`; `footprint(node: Node, *, agent: bool) -> set[str]` — `touches`; when empty and `agent`, `{f"{r}:*" for
    r in repos}` or `{ALL}`.
  - `overlap(a: set[str], b: set[str]) -> set[str]` — shared entries, where `ALL` overlaps everything and `repo:*`
    overlaps every entry of that repo.
  - `order(tasks: dict[str, list[str]], edges: set[tuple[str, str]], cites: dict[str, set[str]]) -> dict[str,
    list[str]]` — `tasks` is id → touches; B depends on A when an edge goes from a file of B to a file of A; a docs task
    (all touches `cam-docs:`) depends on every task whose files its page cites (`cites`: page touch → set of code
    touches). Self-loops ignored; result lists sorted by id key.
  - `sccs(graph: dict[str, list[str]]) -> list[list[str]]` — strongly connected components with ≥ 2 members, each
    sorted, list sorted (Tarjan, iterative).
  - `conflicts(node: Node, others: list[Node]) -> list[dict]` — `{"id", "kind": "conflict" | "near", "files"}` for
    others not Done/archived; `near` needs a `groups: dict[str, str]` keyword (touch → group) and no shared file.
  - `waves(nodes: list[Node]) -> list[list[str]]` — §4.5: topological levels over `deps` among `nodes` (deps outside
    the set ignored), each level placed greedily by `(priority rank, id key)` into the first wave of that level or later
    with no overlap; raises `CycleError(ValueError)` with `.cycle: list[str]`.
  - `blocked_by(node: Node, board: list[Node], *, agent: bool) -> list[dict]` — reasons it cannot start now:
    `{"id", "kind": "dependency"}` for deps not Done (archived counts as Done; unknown ids are reported as
    `"missing"`), `{"id", "kind": "conflict", "files"}` for In Progress items whose footprint overlaps.
  - `ready(board: list[Node], *, agent: bool = True) -> list[str]` — Backlog/Ready nodes with no `blocked_by`, sorted by
    (wave index, priority rank, id key).
  - Id key = `state.id_key` from `lib/kanban/state.py`.

- [ ] **Step 1: Failing tests** with small literal fixtures:
  - `test_norm_touch`: `norm_touch(" api:.\\src\\A.java ", fold=False) == "api:src/A.java"`; `"api:../x"` raises.
  - `test_order_provider_first`: edges `{("b.py","a.py")}` with tasks `{"T1": ["api:a.py"], "T2": ["api:b.py"]}` (edges
    keyed with repo: pass `{("api:b.py","api:a.py")}`) → `{"T1": [], "T2": ["T1"]}`.
  - `test_docs_after_code`: a `cam-docs:docs/x.md` task whose page cites `api:a.py` depends on the task touching it.
  - `test_sccs_finds_two_way_groups`: `{"A": ["B"], "B": ["A"], "C": []}` → `[["A", "B"]]`.
  - `test_conflict_and_near`: shared file → `conflict`; same group, different file → `near`; Done item ignored.
  - `test_waves_golden`: a fixed 6-node fixture (two chains, one shared file, priorities P0/P2/None) equals a literal
    `[["WI-2","WI-5"],["WI-3"],["WI-4","WI-6"],["WI-7"]]`-style expected value written from the rules; running it twice
    and with the input list shuffled gives the same result.
  - `test_waves_cycle_raises`: `CycleError` with `.cycle == ["WI-1", "WI-2"]`.
  - `test_unknown_footprint_is_whole_repo_for_agents`: a node without touches and `repos=["api"]` overlaps any
    `api:` file for `agent=True` and nothing for `agent=False`.
  - `test_blocked_by_and_ready`: dependency not Done → blocked; archived dependency → not blocked; In Progress overlap →
    blocked with files; `ready` order follows waves then priority then id.
- [ ] **Step 2: Run** `uv run pytest tests/test_kanban_deps.py -v` — Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `deps.py` (module docstring: pure, deterministic, what each function is for).
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(board): deterministic dependencies, conflicts and waves`.

### Task 4: Board ops — parents, footprints, dependencies, repair

**Files:**
- Modify: `.camarones/lib/kanban/ops.py` (`add`, `_row`, `list_items`), `.camarones/lib/kanban/items.py`
  (`new_body(type_, lang, dod, *, description=None, criteria=())`), `.camarones/lib/kanban/repair.py`
- Test: `tests/test_kanban_ops.py`, `tests/test_kanban_repair.py`

**Interfaces:**
- Consumes: `deps.norm_touch`, `deps.sccs`.
- Produces:
  - `ops.add(type_, title, *, epic=None, parent=None, repos=(), labels=(), priority=None, docs=(), description=None,
    criteria=(), touches=(), dependencies=(), by=None, surface="cli") -> dict` — `epic` is an alias of `parent` (both
    given and different → `BoardError`). Allowed parent pairs: epic → story/bug/spike/task; story → task. `touches`
    normalised, sorted, unique (case-folded uniqueness when `IS_WIN or IS_MAC`), stored as `x-touches` (omitted when
    empty); `dependencies` must be existing ids (tasks/ or archive), stored upper-cased and sorted; `x-repos` defaults
    to the repos of `touches` when `repos` is empty.
  - `_row` adds `"parent"` (same value as `"epic"`, which stays for compatibility), `"touches"`, `"dependencies"`.
  - `ops.list_items(..., parent=None)` filters on `parent_task_id`.
  - `ops.update_item(item_id, *, title=None, description=None, add_criteria=(), touches=None, docs=(), subtasks=None,
    by=None, surface="cli") -> dict` — used by `stories.save`; appends criteria after the existing ones (never
    renumbers), replaces description and touches when given.
  - `repair.repair(...)` keeps `subtasks` in step for **any** parent from its children's `parent_task_id`, and adds
    warnings `"WI-n: x-touches file not found: api:x.py"` and `"dependency cycle: WI-1 -> WI-2 -> WI-1"`.

- [ ] **Step 1: Failing tests** (`board` fixture of `test_kanban_ops.py`):
  - `test_add_task_under_story`: story WI-1, `add("task", "x", parent="WI-1", touches=["api:b.py", "api:a.py"])` →
    file has `parent_task_id: WI-1`, `x-touches: [api:a.py, api:b.py]`, story's `subtasks == ["WI-2"]`.
  - `test_add_refuses_bad_parents`: story under story, task under bug, unknown parent → `BoardError`.
  - `test_add_description_and_criteria_fill_the_template`: description replaces the placeholder block; criteria are
    `- [ ] #1 …`, `- [ ] #2 …` in the AC block; DoD unchanged.
  - `test_add_dependencies_must_exist` and `test_add_dependency_on_archived_item_is_allowed`.
  - `test_touches_normalised_and_case_folded` (Review Focus 1): `["api:src\\A.java", "api:./src/a.java"]` → one entry
    when `IS_WIN or IS_MAC`, two otherwise (monkeypatch `ops.IS_WIN`).
  - `test_old_board_lists_the_same`: a 4.x-shaped board (epics + stories, no new fields) gives the same `list_items()`
    except for the three new keys, which are `parent == epic`, `touches == []`, `dependencies == []`.
  - `test_update_item_appends_criteria_and_keeps_numbering`.
  - In `test_kanban_repair.py`: `test_repair_fills_story_subtasks_after_a_crash` (child written, parent not updated),
    `test_repair_warns_missing_touch_and_cycle`.
- [ ] **Step 2: Run** `uv run pytest tests/test_kanban_ops.py tests/test_kanban_repair.py -v` — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the changes listed in Interfaces.
- [ ] **Step 4: Run** the two files plus `tests/test_kanban_items.py tests/test_portal_kanban.py` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(board): story parents, footprints and dependencies on items`.

### Task 5: SQLite index

**Files:**
- Create: `.camarones/lib/kanban/index.py`
- Test: `tests/test_kanban_index.py`

**Interfaces:**
- Consumes: `kanban.TASKS/ARCHIVE/BOARD`, `ops.load_state`, `codemap.file_edges/group_of/graph_file`,
  `docs.iter_docs/parse_fm`, `deps.Node`.
- Produces:
  - `DB = CACHE / "board.db"`; `FORMAT = 1`.
  - `snapshot() -> str` — sha256 hex over sorted `(name, size, mtime_ns)` of `board.yaml`, `tasks/*.md`,
    `archive/tasks/*.md`, doc files, and each repo's `graph.json` `(size, mtime_ns)`; no file contents read.
  - `connect() -> sqlite3.Connection` — fresh when `meta.snapshot` matches; otherwise rebuilds into
    `DB.with_suffix(".db.tmp-<pid>")`, `journal_mode=DELETE`, then `os.replace` onto `DB`; any `sqlite3.Error` → unlink
    and rebuild once; a second failure → build in `":memory:"` and `log.warning`. Caller closes it.
  - Tables exactly as the spec §5 (`meta`, `items`, `touches`, `deps`, `edges`, `cites`). `touches.grp` from
    `codemap.group_of`, else the parent folder name, `cam-docs` pages → `"docs"`.
  - Queries: `nodes(conn) -> list[deps.Node]` (tasks and archived, with `archived` flag; scalar fields read as lists),
    `edges(conn, touches: Iterable[str]) -> set[tuple[str, str]]` (repo-qualified), `cites(conn, touches) -> dict[str,
    set[str]]` (page touch → cited code touches), `groups(conn, touches) -> dict[str, str]`, `search(conn, q: str,
    limit: int = 20) -> list[dict]` (`{"touch", "group", "kind": "file" | "group" | "page", "title"?}`, prefix matches
    first, then substring, case-insensitive), `pages_citing(conn, touches) -> list[str]`.
  - `edges` table holds only edges whose both ends are in `touches` ∪ cited files, per the spec.

- [ ] **Step 1: Failing tests** (fixture: `board` + `write_graph` from `test_codemap.py` + one doc page with
  `x-sources: [api:<OrderService path>]`):
  - `test_builds_and_answers`: `nodes` lists the cards with touches; `cites` maps the page to the code file; `search(
    "ordersvc")` is empty and `search("OrderServ")` finds the file first.
  - `test_rebuilds_when_a_card_changes`: edit a card's `x-touches` → next `connect()` sees it; no change → no rebuild
    (monkeypatch the build function to count calls).
  - `test_corrupt_db_is_rebuilt`: write garbage to `DB` → `connect()` works.
  - `test_unwritable_cache_falls_back_to_memory`: monkeypatch `os.replace` to raise `PermissionError` → still answers.
  - `test_scalar_fields_are_lists` (Review Focus 3): `dependencies: WI-3` and `x-touches: api:a.py` written by hand →
    `nodes()` gives lists.
  - `test_two_processes_rebuild_at_once` (Review Focus 4): two `multiprocessing` workers call `connect()` and
    `nodes()` 20 times each after touching a card; both finish without exceptions and the final db has the change.
  - `test_uninstall_leaves_no_trace`: `DB` is under `CACHE` (assert `DB.is_relative_to(CACHE)`).
- [ ] **Step 2: Run** `uv run pytest tests/test_kanban_index.py -v` — Expected: FAIL.
- [ ] **Step 3: Implement** `index.py`.
- [ ] **Step 4: Run** — Expected: PASS; also `uv run pytest tests/test_kanban_ops.py -v` still green.
- [ ] **Step 5: Commit** `feat(board): derived SQLite index of footprints, edges and citations`.

### Task 6: The start gate, `board next` and `board waves`

**Files:**
- Modify: `.camarones/lib/kanban/ops.py` (`move`), `.camarones/lib/kanban/cli.py`
- Test: `tests/test_kanban_gate.py`, `tests/test_kanban_cli.py`

**Interfaces:**
- Consumes: `index.connect/nodes`, `deps.blocked_by/ready/waves/CycleError`.
- Produces:
  - `HUMAN = ("cli", "portal", "app")`, `AGENT = ("mcp", "harness")` in `ops.py`.
  - `class GateError(BoardError)` with `.blocked_by: list[dict]`.
  - `ops.move(item_id, status, *, before=None, after=None, by=None, surface="cli", force=False) -> dict` — only when
    the new status is `In Progress` and the card was not already there: `blocked_by(node, board, agent=surface in
    AGENT)`; non-empty and (`surface in AGENT` or not `force`) → `GateError`. A forced move calls
    `usage.record("board:move-forced:<surface>")`.
  - `ops.next_items(n: int = 3, *, story=None, epic=None, agent: bool = True) -> dict` — `{"ready": [row + "wave"],
    "waiting": [{"id", "blocked_by"}]}` limited to the story's/epic's descendants when given.
  - `ops.waves(*, story=None, epic=None) -> dict` — `{"waves": [[row…]…]}`, or `{"cycle": [ids]}`.
  - CLI: `ACTIONS` gains `"next"`, `"waves"`; flags `--force` (move), `--n` (int, default 3), `--story`. Human output:
    one `line(r)` per ready item, then `"  · WI-n: espera a WI-m"` / `"choca con WI-m en api:x"` notes in the project
    language; `--json` prints the dict.

- [ ] **Step 1: Failing tests** in `tests/test_kanban_gate.py`:
  - `test_person_is_warned_then_can_force`: WI-1 In Progress touching `api:a.py`; `move("WI-2", "In Progress")` with
    the same touch raises `GateError` whose `blocked_by == [{"id": "WI-1", "kind": "conflict", "files": ["api:a.py"]}]`;
    with `force=True` it moves.
  - `test_agents_are_always_refused`: same with `surface="mcp", force=True` → `GateError`.
  - `test_dependency_not_done_blocks`; `test_archived_dependency_does_not_block` (Review Focus 2).
  - `test_move_without_collision_is_unchanged`: a 4.x-shaped board (no touches, no dependencies), `move("WI-2", "In
    Progress")` with the default `surface="cli"` and no `force` succeeds, and the card's status, ordinal and the item's
    mirror fields are what `move` wrote before this change (assert the literal values).
  - `test_next_respects_waves_and_in_progress` and `test_waves_reports_cycles`.
  - In `test_kanban_cli.py`: `board next --json` and `board waves --json` shapes; `board move WI-2 "In Progress"`
    exits 2 with the reason on stderr and succeeds with `--force`.
- [ ] **Step 2: Run** `uv run pytest tests/test_kanban_gate.py tests/test_kanban_cli.py -v` — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the Interfaces above.
- [ ] **Step 4: Run** the two files plus `tests/test_catalog.py` — Expected: PASS (`catalog --check` still green:
  `board` keeps one positional `action`).
- [ ] **Step 5: Commit** `feat(board): start gate and conflict-free next/waves`.

### Task 7: INVEST and split proposals

**Files:**
- Modify: `.camarones/lib/stories.py`
- Create: `.camarones/templates/board/es/split.yaml`, `.camarones/templates/board/en/split.yaml`
- Test: `tests/test_stories_split.py`

**Interfaces:**
- Consumes: Task 1 text functions, `index.connect/nodes/edges/cites/groups/pages_citing`, `deps.*`.
- Produces:
  - `Story = TypedDict("Story", {"id": str | None, "as_": str, "want": str, "so": str, "criteria": list[str],
    "touches": list[str], "epic": str | None, "priority": str | None})`
  - `invest(story: Story, board: list[deps.Node], *, groups: dict[str, str], lang: str) -> dict` —
    `{"verdict": "good" | "improve" | "poor", "letters": {"I"|"N"|"V"|"E"|"S"|"T": {"ok": bool, "reason": str, "data":
    dict}}}`; rules exactly as spec §4.3; thresholds from `docs.workspace().get("stories", {}).get("small", {})` over
    the defaults `{"groups": 3, "files": 15, "repos": 2}`; `S.data` has `{"groups", "files", "repos"}` counts and,
    when it fails, `"split_by_group": [[touch…]…]`.
  - `Proposal = TypedDict("Proposal", {"key": str, "kind": "change" | "docs", "title": str, "group": str, "touches":
    list[str], "criteria": list[str], "deps": list[str], "conflicts": list[dict], "wave": int, "edited": bool})` —
    `key` is stable: `"change:<repo>:<group>"` / `"docs:<page touch>"`; `deps` hold keys of other proposals or board
    ids.
  - `split(story: Story, conn, *, lang: str) -> list[Proposal]` — spec §4.4 steps 1–5; templates from
    `templates/board/<lang>/split.yaml` (keys `change_title`, `docs_title`, `change_criterion`), project override
    `<cam-docs>/.camarones/board/split.yaml` merged key by key.
  - `analyze(story: Story, tasks: list[Proposal] | None, *, lang: str) -> dict` — `{"hints", "invest", "tasks",
    "waves", "conflicts", "cycle", "graphless": [repo…]}`; when `tasks` is given (hand-edited) it re-runs
    `deps.order/conflicts/waves` on them instead of `split`; flags `edited` tasks whose touches left the story's
    footprint with `"outside": [touch…]`. Pure apart from reading the index.

- [ ] **Step 1: Failing tests** (index fixture from Task 5, graph with groups `orders`, `payments`, `web`):
  - `test_invest_each_letter` — one case per letter passing and failing; `test_verdict_boundaries` (all pass → good;
    `empty` → poor; 3 failures → poor; 1 failure → improve).
  - `test_split_one_task_per_group_plus_docs`: touches in `orders` and `payments` plus a page citing `orders` →
    proposals `change:api:orders`, `change:api:payments`, `docs:cam-docs:docs/flows/checkout.md`.
  - `test_split_merges_two_way_groups`: graph edges both ways between `orders` and `payments` → one change task with
    both groups' files, title naming both.
  - `test_split_orders_provider_first_and_docs_last`: `web` calls `orders` → `web` task deps include the `orders` key;
    docs task waves after both.
  - `test_split_conflicts_with_open_board_items` and `test_in_progress_conflict_becomes_dependency`.
  - `test_project_template_override`.
  - `test_analyze_with_edited_tasks_recomputes_and_flags_outside`.
  - `test_analyze_without_graph_lists_graphless_repo`.
  - `test_deterministic`: `analyze` twice on the same input returns equal dicts.
- [ ] **Step 2: Run** `uv run pytest tests/test_stories_split.py -v` — Expected: FAIL.
- [ ] **Step 3: Implement** the Interfaces above.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(stories): INVEST by rules and template-based split with waves`.

### Task 8: Save, list and load stories

**Files:**
- Modify: `.camarones/lib/stories.py`
- Test: `tests/test_stories_save.py`

**Interfaces:**
- Consumes: `ops.add/update_item/locked`, `analyze`, `fingerprint`, `compose`, `parse`.
- Produces:
  - `class StoryConflict(BoardError)` (→ 409).
  - `save(story: Story, *, title: str | None, tasks: list[Proposal], base_sha: str | None, docs: Sequence[str] = (),
    lang: str, by: str | None = None, surface: str = "cli") -> dict` — returns `{"story": row, "tasks": [row…]}`;
    validation and write order as spec §4.6; proposal-key dependencies are mapped to the new ids before writing; a
    hand-made cycle → `BoardError`; existing story: description becomes `compose(...)` + `"\n\n" + rest` when `rest`.
  - `list_stories() -> list[dict]` — every non-archived `type: story`: `{"id", "title", "verdict", "progress": {"done",
    "total"}, "conflicts": [ids]}` (verdict recomputed with `invest`).
  - `item(story_id: str) -> dict` — `{"id", "title", "as_", "want", "so", "rest", "criteria": [str], "touches",
    "epic", "priority", "docs", "subtasks": [row + "wave"], "sha"}`.

- [ ] **Step 1: Failing tests**:
  - `test_save_new_story_and_tasks`: two proposals with a dependency → files exist, the second task's
    `dependencies == [<first id>]`, story `subtasks` lists both, `x-touches` set on all three, Backlog column order
    story, task 1, task 2.
  - `test_save_existing_story_keeps_title_criteria_and_notes` (Review Focus 5): story with notes `"Línea 1\nLínea 2"`
    after the clauses and one AC → after save the notes follow the clauses in order, old AC is `#1`, new AC is `#2`.
  - `test_save_story_without_clauses_puts_them_above_old_text`.
  - `test_concurrent_change_is_a_conflict`: change the file after `item()`; `save(..., base_sha=old)` with different
    clauses → `StoryConflict`; nothing else written (`tree()` before == after apart from nothing).
  - `test_invalid_task_writes_nothing`: one empty title → `BoardError`, backlog tree unchanged.
  - `test_new_file_touch_needs_existing_folder`: `api:src/new/File.java` allowed when `src/new` exists, refused
    otherwise.
  - `test_list_stories_progress_and_conflicts`.
- [ ] **Step 2: Run** `uv run pytest tests/test_stories_save.py -v` — Expected: FAIL.
- [ ] **Step 3: Implement** the Interfaces above.
- [ ] **Step 4: Run** — Expected: PASS.
- [ ] **Step 5: Commit** `feat(stories): save a story with its subtasks in one locked pass`.

### Task 9: CLI `camaron board story …`

**Files:**
- Modify: `.camarones/lib/kanban/cli.py`
- Test: `tests/test_kanban_cli.py`

**Interfaces:**
- Consumes: `stories.item/lint/invest/analyze/save`.
- Produces: action `story` with sub-verb in `args[0]` ∈ `lint`, `invest`, `split`; `args[1]` the story id;
  `--accept` (split: save every proposal as is), `--touch` (append, adds footprint entries before analysing).
  `_NEED["story"] = 2`, `_USAGE["story"] = "story lint|invest|split ID"`.

- [ ] **Step 1: Failing tests**: `board story lint WI-1 --json` returns the hints list; `board story invest WI-1
  --json` has `verdict`; `board story split WI-1 --json` lists proposals with `wave`; `--accept` creates the tasks and
  prints their ids; an unknown sub-verb exits 2 with the usage line.
- [ ] **Step 2: Run** `uv run pytest tests/test_kanban_cli.py -v` — Expected: new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/test_kanban_cli.py tests/test_catalog.py -v` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(board): story lint, invest and split from the command line`.

### Task 10: Portal API

**Files:**
- Modify: `.camarones/lib/serve.py` (`api_get`, the POST dispatcher, `kanban_post`)
- Test: `tests/test_portal_stories.py` (reuse `server`/`call` from `tests/test_portal_kanban.py`)

**Interfaces:**
- Consumes: Tasks 6–8.
- Produces the routes of spec §8.1. Bodies:
  - `POST /api/stories/analyze` `{story: Story, tasks?: [Proposal], lang?}` → `analyze` result (no token).
  - `POST /api/stories/save` `{story, title?, tasks, base_sha?, docs?}` → `save` result (token); `StoryConflict` →
    409 `{error}`; `BoardError` → 400.
  - `GET /api/stories` → `{enabled, writable, ai: {available: bool, runner, model}, lint_words: {es, en}, stories}`.
  - `GET /api/stories/item?id=` and `GET /api/stories/files?q=` → `item`, `index.search`.
  - `GET /api/kanban/next?n=&story=` and `GET /api/kanban/waves?story=` (people: `agent=False` for next).
  - `POST /api/kanban/move` accepts `force` (bool); `GateError` → 409 `{error, blocked_by}`.
  - `GET /api/kanban` rows gain `"wave"` (index in `ops.waves()`, `null` when cycled or Done) and `"blocked_by"`
    (`deps.blocked_by(..., agent=False)`, only for Backlog/Ready cards) for the Kanban badges.
  - `/api/stories/suggest` is added in Task 12.

- [ ] **Step 1: Failing tests**: save without token → 403 `token: true`; analyze without token → 200 and the backlog
  tree is unchanged; save with token → 200 and files exist; save with a stale `base_sha` → 409; bad body (missing
  `story.want`) → 400; move into a collision → 409 with `blocked_by`, then with `force: true` → 200; `GET
  /api/stories` works without token and lists stories; `GET /api/kanban/next` shape.
- [ ] **Step 2: Run** `uv run pytest tests/test_portal_stories.py -v` — Expected: FAIL.
- [ ] **Step 3: Implement** the routes.
- [ ] **Step 4: Run** it plus `tests/test_portal_kanban.py tests/test_portal_actions.py` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(portal): stories API and the move gate over HTTP`.

### Task 11: MCP read tools

**Files:**
- Modify: `.camarones/lib/mcp.py` (`TOOLS`, `HANDLERS`)
- Test: `tests/test_mcp_board.py`

**Interfaces:**
- Produces: tools `board_next` (`{"n": int, "story": str}`, both optional) → `json.dumps(ops.next_items(n, story=…,
  agent=True))`; `board_waves` (`{"story": str, "epic": str}`) → `json.dumps(ops.waves(...))`. Descriptions say: the
  only tasks an agent may start, and that agents cannot move cards.
- [ ] **Step 1: Failing tests**: `tools/list` contains both; calling `board_next` on a board with an In Progress
  conflict omits the conflicting task; no board → a plain message, not an exception.
- [ ] **Step 2: Run** `uv run pytest tests/test_mcp_board.py -v` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** it plus `tests/test_mcp_resources.py tests/test_mcp_write.py` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(mcp): board_next and board_waves for agents`.

### Task 12: Optional AI suggestions (off by default)

**Files:**
- Create: `.camarones/lib/stories_ai.py`
- Modify: `.camarones/lib/serve.py` (`POST /api/stories/suggest`)
- Test: `tests/test_stories_ai.py` (reuse the fake runner pattern of `tests/test_ask_ai.py`)

**Interfaces:**
- Consumes: `answers.model`-style route lookup (`plan._agents(..., "bounded", allow_local=True)`), `harness.evals._ask,
  _last_json`, `mcp.ask`, `index.search` to validate file names.
- Produces:
  - `enabled() -> bool` — `docs.workspace().get("stories", {}).get("ai") is True` and a runner exists.
  - `suggest(story: Story, *, what: Literal["rewrite", "criteria", "tasks"], exclude: Sequence[str] = (), lang: str)
    -> dict` — `{"rewrite": {as_, want, so} | None, "criteria": [str], "tasks": [{"title", "touches"}], "missing":
    [str], "runner", "model", "seconds"}`; touches kept only if `index.search` finds them exactly; tasks ≤ 8, titles
    ≤ 120, de-duplicated against `exclude`; `RuntimeError` with Ask-style messages when off, without runner or on
    timeout (90 s); `usage.record("stories:suggest", channel="human", hit=…)`.
  - `GET /api/stories` `ai.available` = `stories_ai.enabled()`.
- [ ] **Step 1: Failing tests**: default workspace → `enabled() is False` and `suggest` raises without calling the
  runner (the fake runner's log file is not created) even when a runner is configured; `stories: {ai: true}` → fake
  runner JSON is parsed; invented file dropped; > 8 tasks capped; broken JSON → `missing` lists the parts; timeout
  (`ASK_SLEEP`) → 503 over HTTP; suggest without token → 403.
- [ ] **Step 2: Run** `uv run pytest tests/test_stories_ai.py -v` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** it plus `tests/test_ask_ai.py` — Expected: PASS.
- [ ] **Step 5: Commit** `feat(stories): optional AI suggestions, off by default`.

### Task 13: Portal — zone, route, helpers and lint port

**Files:**
- Create: `.camarones/portal/app/src/stories.js`, `.camarones/portal/app/src/stories.test.js`
- Modify: `.camarones/portal/app/src/zones.js`, `zones.test.js`, `router.js`, `router.test.js`,
  `i18n/portal.js`
- Test: Vitest

**Interfaces:**
- Consumes: `GET /api/stories` (`lint_words`), the shared `tests/fixtures/story_lint_cases.json` (imported by relative
  path from the test).
- Produces in `stories.js`:
  - `lint(as, want, so, lang, words, touches)` → same codes and order as Python.
  - `initialDraft(item | null)` → `{as, want, so, title, epic, criteria, touches, tasks: null, step: 1}`.
  - `nextStep(draft, analysis)` → `1 | 2 | 3`; `outdated(draft, analysedSha)` → bool (uses a JS port of
    `fingerprint`'s normalisation, compared on the normalised text, not the hash).
  - `primaryLabel(draft, t)` → `t('stories.save.new', {n})` or `t('stories.save.existing', {id, n})`.
  - `loadDraft(key)`/`saveDraft(key, draft)` — localStorage wrapped in try/catch, returning `null` on any error.
- `zones.js`: `{ id: 'stories', href: '#/stories', views: [{ id: 'stories', href: '#/stories', live: true }] }` right
  after `board`; `ROUTES.stories = ['stories', 'stories']`; `router.js` `NATIVE` gains `'stories'`.
- i18n keys (es and en): `zone.stories`, `zoned.stories`, `view.stories`, `viewd.stories`, `stories.step.1..3`,
  `stories.hint.<code>` (7), `stories.verdict.good|improve|poor`, `stories.invest.I..T`, `stories.save.new`,
  `stories.save.existing`, `stories.saved`, `stories.readonly`, `stories.graphless`, `stories.conflict`,
  `stories.ai.suggest`, `kanban.wave`, `kanban.blocked`, `kanban.force`.
- [ ] **Step 1: Failing tests**: `stories.test.js` runs every row of the shared JSON through `lint` and expects the
  same codes; `nextStep`/`outdated`/`primaryLabel` cases; `saveDraft` survives a throwing `localStorage`. Update
  `zones.test.js` expectations to `['docs', 'board', 'stories', 'arch', 'plan', 'quality', 'review']` for live/app and
  no `stories` in static; `router.test.js`: `#/stories` resolves native in live.
- [ ] **Step 2: Run** `npm test` in `.camarones/portal/app` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test` — Expected: PASS; also `uv run pytest tests/test_portal_app.py -v` (i18n parity
  checks, if any) — PASS.
- [ ] **Step 5: Commit** `feat(portal): Historias zone, route and pure helpers`.

### Task 14: Portal — the Historias screen and Kanban badges

**Files:**
- Create: `.camarones/portal/app/src/Stories.jsx`
- Modify: the shell's native-view switch (where `Kanban` is mounted for `view === 'kanban'`), `Kanban.jsx`,
  `kanban.js`, `kanban.test.js`, `portal.css`; rebuild `.camarones/portal/app-build/`
- Test: Vitest (`kanban.test.js`), `tests/test_portal_app.py` (build matches source)

**Interfaces:**
- Consumes: Task 10 routes, Task 13 helpers.
- Produces:
  - `Stories.jsx` — left list + three steps as in the agreed mock-up; `analyze` called debounced 200 ms on every
    change; *Toca* uses `GET /api/stories/files`; read-only banner (`stories.readonly`) without token; toast with link
    `#/kanban?parent=<id>`; *Sugerir con IA* only when `ai.available`; Escape aborts a running suggest fetch.
  - `kanban.js`: `applyFilters(cards, {…, parent})` keeps the parent and its children; `waveOf(cards, waves)`.
  - `Kanban.jsx`: `↳ WI-n` on tasks of a story, wave badge, conflict badge for cards whose `blocked_by` is non-empty,
    a "Mover igualmente" confirm on a 409 from move that resends with `force: true`.
- [ ] **Step 1: Failing tests** in `kanban.test.js`: `applyFilters` with `parent`; `waveOf`.
- [ ] **Step 2: Run** `npm test` — Expected: FAIL.
- [ ] **Step 3: Implement** the screen and the Kanban changes following the `cofundo-design-system` skill and
  `CAMARON.md`.
- [ ] **Step 4: Run** `npm test` and `npm run build`, then `uv run pytest tests/test_portal_app.py tests/test_portal_smoke.py -v`
  — Expected: PASS.
- [ ] **Step 5: Manual check** with the sandbox: `uv run scripts/sandbox.py cli up`, open `#/stories`, write a story
  touching `owners` and `vets`, save, check the Board shows the story, its tasks and their waves.
- [ ] **Step 6: Commit** `feat(portal): Historias screen, wave and conflict badges on the board` (source and
  `app-build/` together).

### Task 15: Docs, version, e2e and sandbox

**Files:**
- Modify: `.camarones/lib/common.py` (`VERSIONS["kit"] = "4.63.0"`), `README.md` (badge + "Historias" and the gate),
  `.camarones/lib/tutorial.py` (+ regenerate `.camarones/TUTORIAL.md`), `.camarones/templates/docs/guides/tutorial.md`,
  `.camarones/templates/docs/i18n/es/guides/tutorial.md`, the Backlog.md e2e test under `tests/e2e/`
- Test: `tests/test_wizard.py`, `uv run pytest -m e2e`, sandbox

- [ ] **Step 1: Extend the e2e test**: `npx backlog.md@1.55.3` edits a story with `x-touches` and a task with
  `dependencies`; afterwards both fields are unchanged.
- [ ] **Step 2: Write the docs** (es/en): what Historias does, `board story|next|waves`, the gate and `--force`,
  `stories: {ai, small}`.
- [ ] **Step 3: Regenerate** `TUTORIAL.md` from `.camarones/`:
  `uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"`.
- [ ] **Step 4: Run** `uv run pytest -n auto` — Expected: all green; `uv run pytest -m e2e` — Expected: green (needs
  network; if unavailable, say so).
- [ ] **Step 5: Sandbox**: `uv run scripts/sandbox.py cli board story split WI-1 --json` on a story touching
  `owners`/`vets`; `board next` gives only wave 1; a harness-surface move of a conflicting task is refused (call
  `ops.move(..., surface="harness")` from `uv run python`); then `uv run scripts/sandbox.py traces` exits 0 after
  uninstall.
- [ ] **Step 6: Commit** `docs(stories): Historias, board next/waves and the start gate` (the commit body says existing
  projects keep their old tutorial copy).
