# Desktop onboarding wizard and documenting-only project window — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The desktop app opens on a "What do you want to document?" start screen that accepts any folder or the
team's docs repo, runs the CLI's first run as an interactive wizard in the project window, and leaves a project
window for documenting while "View portal" opens the browser.

**Architecture:** A new `lib/onboard.py` holds folder detection, the first-run state and the step bodies that the
CLI wizard and the app share (moved out of `lib/wizard.py`). The CLI gains `projects --inspect/--adopt` for the hub,
and `lib/serve.py` gains `/api/app/onboard/*` (token only) for a new React `Onboarding` view at `#/start`. `zones.js`
narrows mode `app` to next/plan/review/board/taller, and the legacy router opens portal-only routes in the browser.

**Tech Stack:** Python 3.10+ (pytest via `uv`), Electron main/preload (CommonJS, `node --test`), React 19 + Vite +
Vitest, legacy portal scripts.

**Spec:** `docs/superpowers/specs/2026-10-25-desktop-onboarding-design.md`

**Before Task 1:** `main` has uncommitted work by another session in `desktop/` (hub title bar, `main.cjs`,
`preload.cjs`, `core.cjs`), `portal/app*/legacy/*` and the tutorial. Ask the user to have it committed first, then
work in a worktree `.claude/worktrees/onboarding` (branch `worktree-onboarding`) from that commit. Run all git
commands with `git -c safe.directory=*` (the repo is owned by another Windows user).

## Global Constraints

- macOS, Windows, Linux: `pathlib`, `encoding="utf-8"`, `newline="\n"` on writes. Processes only through
  `lib/common.py` helpers. Branch on `IS_WIN`/`IS_MAC` only.
- Backward compatible: `project.kind` absent reads `legacy`. `new`, `join` and `projects --add` keep their
  behaviour and flags. A 3.x/4.x `firstrun.json` (`{step, name, done, mode}`, or index-only) resumes as before.
- One implementation per behaviour. The CLI wizard calls `onboard.*` for everything §3–4 of the spec defines.
- `/api/app/onboard/*` answers 403 `{"app": true}` without the app token, like every `/api/app/*`.
- Every user string exists in `es` and `en`. There is one joke only, on the install step's waiting line. Prompts,
  errors and the detection card carry none (AGENTS §3).
- UI follows the `cofundo-design-system` skill (`.claude/skills/`) and `CAMARON.md`. The hub uses
  `portal/app-build/theme/tokens.css`. The aurora gradient is gone.
- `portal/app-build/` is committed and must match its source: run `npm run build` in `portal/app` after portal
  changes.
- Tests are offline. Use `make_workspace` and `isolated_env`, and never the real `~/.camarones`.
- Kit version `4.52.0`.

## Review Focus

1. The person picks their home folder or a drive root (`C:\`, `/`): `inspect` must not walk the whole disk. The
   manifest search goes to depth 1 only, and the case is `empty` or `code` — Task 1
   `test_inspect_looks_one_level_down_only`.
2. The picked folder is inside an existing project's `cam-docs/` (for example `cam-docs/docs`): the case is
   `project` for that docs root, and nothing nested is created — Task 1 `test_inspect_inside_cam_docs_is_the_project`.
3. The folder name has spaces, accents or uppercase (`Mi Proyecto Ñandú`): the name keeps the folder's text, the
   `id` is a safe slug, and `adopt` does not nest a second folder — Task 2 `test_start_keeps_a_human_name`.
4. The app closes during the setup job and reopens: the wizard resumes at `setup`, not `done`, and the CLI agrees —
   Task 2 `test_state_written_by_the_app_resumes_the_cli`, Task 7 vitest `resumes at the saved step`.
5. A greenfield project with zero repos opens on "Next step" after the wizard: `plan.sync()` and the next-unit query
   must not raise — Task 3 `test_greenfield_without_repos_sets_up_and_plans`.

---

### Task 1: Folder detection — `onboard.inspect`

**Files:**
- Create: `.camarones/lib/onboard.py`
- Modify: `.camarones/lib/docs.py` (`detect_repos` gets a `workspace` parameter)
- Modify: `tests/conftest.py` (add `"onboard"` to `MODULES`)
- Test: `tests/test_onboard.py`

**Interfaces:**
- Produces:
  - `docs.detect_repos(workspace: Path | None = None) -> list[dict]` (None → `WORKSPACE`; rows unchanged).
  - `onboard.MANIFESTS: tuple[str, ...]` = `("pom.xml", "build.gradle", "build.gradle.kts", "package.json",
    "pyproject.toml", "go.mod", "Cargo.toml", "pubspec.yaml", "composer.json", "Gemfile")`, plus any `*.csproj`.
  - `onboard.inspect(folder: Path) -> dict` with keys `case` (`project|repo|umbrella|code|empty`), `kind`
    (`legacy|greenfield`), `workspace: str`, `docs_root: str`, `name: str`, `repos: list[dict]`,
    `siblings: list[dict]`, `warning: str` (`""` or `"no-git"`).
  - `onboard.kind_of(ws: dict) -> str` → `ws["project"].get("kind") or "legacy"`.

- [ ] **Step 1: Write the failing tests** in `tests/test_onboard.py`, using `isolated_env` and
  `fixtures.builder.make_repo`/`make_workspace` under `tmp_path`, and importing `lib.onboard` through `load_kit` on a
  throwaway root (as the `kit` fixture does):
  - `test_inspect_umbrella_is_legacy`: `make_workspace` without `cam-docs` (delete it) → `case == "umbrella"`,
    `kind == "legacy"`, `workspace == str(ws)`, `docs_root == str(ws / "cam-docs")`, `{r["name"] for r in repos} ==
    {"api", "web", "worker"}`, `name == "demo"`.
  - `test_inspect_a_repo_uses_its_parent`: pick `ws / "api"` → `case == "repo"`, `workspace == str(ws)`,
    `[r["name"] for r in repos] == ["api"]`, `{r["name"] for r in siblings} == {"web", "worker"}`.
  - `test_inspect_a_repo_whose_parent_is_a_project`: `make_workspace` (with `cam-docs`), pick `ws / "api"` →
    `case == "project"`, `docs_root == str(ws / "cam-docs")`.
  - `test_inspect_existing_project`: picking `ws` and picking `ws / "cam-docs"` both give `case == "project"`, and
    `kind == "greenfield"` when `workspace.yaml` has `project.kind: greenfield`.
  - `test_inspect_inside_cam_docs_is_the_project`: pick `ws / "cam-docs" / "docs"` (create it) → `case == "project"`.
  - `test_inspect_code_without_git`: folder with `src/package.json` only → `case == "code"`, `kind == "legacy"`,
    `warning == "no-git"`.
  - `test_inspect_empty_is_greenfield`: an empty folder → `case == "empty"`, `kind == "greenfield"`, `repos == []`.
  - `test_inspect_looks_one_level_down_only`: `a/b/pom.xml` (depth 2) → `case == "empty"`.
  - `test_inspect_writes_nothing`: a snapshot of the folder tree before and after is equal, for each case above.
  - `test_kind_absent_reads_legacy`: `kind_of({"project": {}}) == "legacy"`.

- [ ] **Step 2: Run them to verify they fail**

  Run: `uv run pytest tests/test_onboard.py -q`
  Expected: FAIL, `ModuleNotFoundError: lib.onboard`.

- [ ] **Step 3: Implement `docs.detect_repos(workspace=None)` and `onboard.inspect` / `onboard.kind_of`.**
  `project` detection uses `harness.ctx.find_project_marker` walking up from `folder`, and also
  `folder / CAM_DIR / ".camarones/workspace.yaml"`. Read `workspace.yaml` with `yaml.safe_load` for `kind`.
  `has_repos` comes from `lib/projects.py`. `name` is the workspace folder's `.name`.

- [ ] **Step 4: Run them to verify they pass**

  Run: `uv run pytest tests/test_onboard.py tests/test_wizard.py -q`
  Expected: PASS (`test_wizard.py` checks that `detect_repos()` without an argument is unchanged).

- [ ] **Step 5: Commit**

  `git add .camarones/lib/onboard.py .camarones/lib/docs.py tests/conftest.py tests/test_onboard.py`
  `git commit -m "feat(onboard): detect what a picked folder is (project, repo, umbrella, code, empty)"`

### Task 2: First-run state shared by the CLI and the app — name, start, steps

**Files:**
- Modify: `.camarones/lib/onboard.py`, `.camarones/lib/wizard.py` (`fr_name`, `first_run`, `fr_repos`,
  `first_run_mode`, `resume_step`), `.camarones/lib/docs.py` (`save_workspace` delegates)
- Test: `tests/test_onboard.py`, `tests/test_wizard.py`

**Interfaces:**
- Consumes: `onboard.inspect`, `onboard.kind_of` (Task 1).
- Produces:
  - `onboard.WS_HEADER: str` (the header `docs.save_workspace` writes today, moved here).
  - `onboard.write_workspace(ws_file: Path, ws: dict) -> None`; `docs.save_workspace(ws)` calls it with `ws_file()`.
  - `onboard.name_project(ws: dict, name: str, fallback: str) -> dict`: sets `name` (stripped, or `fallback`), `id`
    (lowercase, non-alnum → `-`, stripped), `canonical_language` default `"en"`, `translations` default `["es"]`.
    Same values as today's `fr_name`.
  - `onboard.firstrun_file(root: Path) -> Path` → `Ctx.for_root(root).cache / "firstrun.json"`.
  - `onboard.steps(mode: str, kind: str) -> tuple[str, ...]`: `new`+`legacy` → `("name", "repos", "tools", "setup",
    "stack", "arch", "intro")`; `new`+`greenfield` → `("name", "repos", "tools", "setup", "intro")`; `join` →
    `("tools", "setup", "intro")`.
  - `onboard.first_run_mode(state, shared_ready, local_ready) -> str` (moved verbatim; `wizard.first_run_mode`
    stays as an alias).
  - `onboard.save_position(root: Path, step: str, mode: str) -> None`: writes `{"step": STEPS.index(step), "name":
    step, "done": False}` plus `"mode": "join"` when `mode == "join"`. Same shape as `first_run` writes today.
  - `onboard.finish(root: Path, steps_count: int) -> None`: writes `{"step": steps_count, "done": True}`.
  - `onboard.start(folder: Path, name: str | None = None) -> Path`: §3 of the spec. It returns the docs root and
    is idempotent.

- [ ] **Step 1: Characterization tests first** in `tests/test_wizard.py`. Lock today's behaviour before moving
  it:
  - `test_first_run_mode_table`: the five rows of `first_run_mode`'s docstring.
  - `test_fr_name_writes`: through `fake_wizard`, answer `"Mi Proyecto"` → `workspace.yaml` has `name == "Mi
    Proyecto"`, `id == "mi-proyecto"`, `canonical_language == "en"`, `translations == ["es"]`.
  - `test_resume_index_only_firstrun`: `{"step": 2}` (pre-3.3) resumes at `LEGACY_STEPS[2]`.

  Run: `uv run pytest tests/test_wizard.py -q -k "first_run_mode_table or fr_name_writes or resume_index"`
  Expected: PASS against the unchanged code.

- [ ] **Step 2: Write the failing tests** in `tests/test_onboard.py`:
  - `test_steps_by_mode_and_kind`: the three tuples above.
  - `test_start_umbrella`: `start(ws)` → returns `ws / "cam-docs"`, `workspace.yaml` has `project.kind ==
    "legacy"`, repos `api, web, worker`. `firstrun.json` has `{"name": "repos", "done": False}`, and
    `projects.load()` lists it.
  - `test_start_a_repo_preselects_only_it`: `start(ws / "api")` → repos `== ["api"]`.
  - `test_start_empty_is_greenfield`: `project.kind == "greenfield"`, `repos == []`.
  - `test_start_is_idempotent`: two calls → same root and an identical `workspace.yaml` byte for byte.
  - `test_start_on_a_project_writes_nothing`: on an existing project, `workspace.yaml` and `firstrun.json` are
    unchanged and the result is its docs root.
  - `test_start_keeps_a_human_name`: folder `Mi Proyecto Ñandú` → `name == "Mi Proyecto Ñandú"`, `id ==
    name_project({"project": {}}, "Mi Proyecto Ñandú", "x")["project"]["id"]`, and the docs root is
    `<folder>/cam-docs`, with no nested folder.
  - `test_start_writes_what_the_cli_name_step_writes`: compare `start`'s `project` block, without `kind`, with
    `fr_name`'s from Step 1.
  - `test_state_written_by_the_app_resumes_the_cli`: `save_position(root, "setup", "new")`, then
    `wizard.resume_step(load_json(firstrun_file(root)))` returns `STEPS.index("setup")`. With `mode="join"` the saved
    state makes `first_run_mode` return `"join"`.

- [ ] **Step 3: Run them to verify they fail**

  Run: `uv run pytest tests/test_onboard.py -q`
  Expected: FAIL, `AttributeError: module 'lib.onboard' has no attribute 'steps'`.

- [ ] **Step 4: Implement the Produces list in `onboard.py`.** `start` uses `projects.adopt(Path(workspace),
  name)`. Then it writes `workspace.yaml` with `write_workspace(Ctx.for_root(root).ws_file, ws)` and the state with
  `save_position(root, "repos", "new")`, because the module globals point at another project.

- [ ] **Step 5: Wire the CLI wizard to it.**
  - `fr_name` calls `onboard.name_project`, then sets `ws["project"].setdefault("kind",
    onboard.inspect(WORKSPACE)["kind"])`.
  - `first_run` takes its `ids` from `onboard.steps(mode, onboard.kind_of(ws))` and saves through
    `onboard.save_position`/`finish`.
  - `fr_repos` disables "continue" with `r_need` only when the kind is `legacy`.
  - `JOIN_STEPS` and `first_run_mode` in `wizard.py` become aliases of the onboard ones.

- [ ] **Step 6: Run the suite**

  Run: `uv run pytest tests/test_onboard.py tests/test_wizard.py -q`
  Expected: PASS, including the Step 1 characterization tests.

- [ ] **Step 7: Commit**

  `git commit -m "feat(onboard): one first-run state for the CLI and the app; greenfield may start with no repos"`

### Task 3: Tools and setup step bodies

**Files:**
- Modify: `.camarones/lib/onboard.py`, `.camarones/lib/wizard.py` (`tool_rows`, `fr_tools`, `fr_setup`,
  `arch_prompt`), `.camarones/lib/agents.py`
- Test: `tests/test_onboard.py`, `tests/test_wizard.py`

**Interfaces:**
- Produces:
  - `onboard.tool_rows() -> list[dict]`: moved from `W.tool_rows`, same keys (`id, label, ok, kind, rec, sys, found,
    note`).
  - `onboard.install_choice(rows: list[dict], choice: str, picked: list[str] | None = None) -> tuple[list[str],
    list[str]]`: `(system, components)` for `choice` in `all|pick|none`. These are the three branches of today's
    `fr_tools`, moved unchanged.
  - `onboard.install_tools(system: list[str], components: list[str], log) -> list[str]`: `env.set_components`, then
    `env.install_prereq` for each one, then `ensure_path()`. Returns the system tools that failed.
  - `onboard.run_setup(log) -> bool`: `env.init_templates(name)`, `env.setup(log=log)`, `plan.sync()`, and
    `plan.set_status("setup", "done", "first run")` when it succeeds.
  - `onboard.missing_repos() -> list[str]`: repos with a URL and no `.git` (from `fr_setup`).
  - `onboard.arch_prompt(lang: str) -> str`: moved from `W.arch_prompt`.
  - `agents.launch_prompt(prompt: str, agent: str, lang: str = "es") -> dict`: a public wrapper of
    `_open(prompt, agent, lang, resume=False)`.

- [ ] **Step 1: Characterization test** `test_tool_rows_shape` in `tests/test_wizard.py`. Monkeypatch
  `env.prerequisites`, `env.tool_ok` and `env.components`, then assert the rows of `W().tool_rows()`. Keep the same
  assertions for `onboard.tool_rows()` in Step 2. Run: `uv run pytest tests/test_wizard.py -q -k tool_rows_shape`,
  expected PASS.

- [ ] **Step 2: Write the failing tests** in `tests/test_onboard.py`:
  - `test_install_choice_all_skips_a_second_agent`: rows with `claude.ok == True`, `codex.ok == False` → `"all"`
    excludes `codex` from `system`, and `components == env.ALL_COMPONENTS`.
  - `test_install_choice_pick_and_none`: `pick` splits `picked` into system and components. `none` returns `([],
    env.components())`.
  - `test_install_tools_reports_failures`: monkeypatch `env.install_prereq` to fail for `"docker"` → it returns
    `["docker"]`.
  - `test_greenfield_without_repos_sets_up_and_plans` (on the `kit` fixture with `repos: []` and `kind:
    greenfield`, `env.setup` monkeypatched to `True`): `run_setup` returns `True`, `plan.load()` loads, and
    `plan.available(plan.load())` does not raise.
  - `test_arch_prompt_names_the_architecture_folder`: `"docs/architecture" in arch_prompt("es")`.

- [ ] **Step 3: Run them to verify they fail**, with `uv run pytest tests/test_onboard.py -q`.

- [ ] **Step 4: Implement the Produces list.** `W.tool_rows`, `fr_tools`, `fr_setup` and `arch_prompt` call these.
  The prompts and screens stay the same. If the greenfield test shows that `plan.sync()` with zero repos raises, fix
  that in `lib/plan.py`: a `for_each: repos` yields no nodes, and a `needs: ["x:*"]` with no match is satisfied.

- [ ] **Step 5: Run** `uv run pytest -q` (whole suite, not e2e). Expected: PASS.

- [ ] **Step 6: Commit**

  `git commit -m "refactor(onboard): tools, setup and the C4 prompt shared by the wizard and the app"`

### Task 4: CLI — `projects --inspect` and `projects --adopt`

**Files:**
- Modify: `.camarones/camarones.py` (the `projects` parser and its branch around lines 399 and 467),
  `.camarones/lib/catalog.py`, `.camarones/lib/appapi.py` (`HUB`)
- Test: `tests/test_projects_cli.py` (create), `tests/test_catalog.py`

**Interfaces:**
- Consumes: `onboard.inspect`, `onboard.start`.
- Produces:
  - `camaron projects --inspect DIR [--json]` prints `inspect(DIR)` as JSON (it requires `--json`; without it,
    one line per field).
  - `camaron projects --adopt DIR [--name NAME] [--json]` prints `{"path": docs_root}`. Errors go to stderr, and
    the exit code is 1.
  - `appapi.HUB == {"new", "join", "switch", "projects"}`, so the Taller never runs these.
  - `join URL FOLDER --no-open` with `CAMARONES_JOIN_TOKEN` in its environment uses that token when plain git is
    refused. In `_team`, the `ask` is `lambda host, again: None if again else os.environ.get("CAMARONES_JOIN_TOKEN")`
    when there is no TTY, and the token is never put on the command line. When access fails with `--no-open`, it
    prints `{"error": reason, "host": host, "detail": detail}` to stdout and exits 1. `reason` comes from
    `projects.reach(url)`: one of `auth`, `denied`, `not-found`, `network` or `unknown`.

- [ ] **Step 1: Write the failing tests:**
  - `test_inspect_json`: run the CLI as a subprocess on an umbrella (`sys.executable camarones.py projects
    --inspect <ws> --json`, `CAMARONES_ROOT` unset) → `json.loads(stdout)["case"] == "umbrella"`.
  - `test_adopt_json_then_list`: `--adopt <ws> --name shop --json` → `path` ends with `cam-docs`, and `projects
    --json` lists it with `name == "shop"`.
  - `test_adopt_refuses_a_non_empty_cam_docs`: `cam-docs/` with a stray file and no `.git` → exit 1, and stderr
    contains `cam-docs`.
  - `test_projects_add_unchanged`: `--add` on a folder without `cam-docs` still exits 1 with the old message.
  - `test_join_no_open_says_why_as_json`: monkeypatch `projects.reach` to return `("auth", "401")` and
    `projects.connect` to return `False`, then run in-process with `--no-open` → stdout JSON has `error == "auth"`
    and a `host`, and the exit code is 1.
  - `test_join_token_comes_from_the_environment`: with `CAMARONES_JOIN_TOKEN=t0k`, the `ask` handed to
    `projects.connect` returns `"t0k"` the first time and `None` when `again` is true.
  - In `test_catalog.py`: `catalog --check` exits 0.

- [ ] **Step 2: Run them to verify they fail**, with `uv run pytest tests/test_projects_cli.py -q`.

- [ ] **Step 3: Implement.** Add `pj.add_argument("--inspect", type=Path)`, `--adopt` (`type=Path`) and `--name` to
  the parser. The branches go before `a.add`. Wrap `ValueError` the same way `_team` does. Describe the new flags
  in `catalog.py` (es/en) so `--check` passes.

- [ ] **Step 4: Run** `uv run pytest tests/test_projects_cli.py tests/test_catalog.py tests/test_app_api.py -q`.
  Expected: PASS.

- [ ] **Step 5: Commit**

  `git commit -m "feat(projects): --inspect and --adopt, the desktop start screen's way in"`

### Task 5: Server — `/api/app/onboard/*`

**Files:**
- Modify: `.camarones/lib/serve.py` (`api_app_get`, `do_POST`, and a `GET /firstlook` route), `.camarones/lib/onboard.py`
- Test: `tests/test_onboard_api.py` (create; reuses the `app_server`/`call` helpers, moved into `tests/conftest.py`
  or imported from `test_app_api`)

**Interfaces:**
- Consumes: Tasks 1–3, `serve.start_job(kind, label, fn)`, `radar.scan`, `radar.set_stack`, `wizard.scan_repos`,
  `quickarch.draft/save`, `agents.launch_prompt`.
- Produces (JSON; every route needs the app token):
  - `GET /api/app/onboard/state` → `onboard.state()`: `{"mode", "kind", "steps": [...without "name"], "step":
    str, "done": bool, "repos": [...], "found": [...]}`.
  - `POST /api/app/onboard/step {"id"}` → `save_position`, then returns `state()`. An unknown id is a 400.
  - `POST /api/app/onboard/repos {"repos": [{name, url, branch, kind}]}`: it validates (name required and unique,
    url optional, `branch` default `"main"`, `kind` default `"service"`), saves and returns `state()`. A legacy kind
    with zero repos is a 400 `{"error": "repos"}`.
  - `GET /api/app/onboard/tools` → `{"rows": tool_rows(), "required_ok": bool}`.
  - `POST /api/app/onboard/setup {"system": [...], "components": [...]}`: a job of kind `onboard:setup`. The log
    has a line `"[n/total] …"` per setup step (`total = env.setup_steps() + len(system)`). Its result is
    `{"failed": [...], "missing": missing_repos(), "ok": bool}`.
  - `POST /api/app/onboard/scan`: a job `onboard:scan` running `scan_repos`. `GET /api/app/onboard/stack` →
    `radar.scan()` reduced to `{repo: {stack, detected_stack}}`. `POST /api/app/onboard/stack {"repo", "text"}` →
    `radar.set_stack`.
  - `POST /api/app/onboard/arch {"action": "draft"}`: a job `onboard:arch` whose result is `{"repos",
    "datastores", "brokers", "relations", "valid", "html": bool}`. The model is kept in `onboard.LAST_DRAFT`.
    `{"action": "save", "overwrite": bool}` → `{"written": [...], "exists": bool}`. If `model.c4` exists and
    `overwrite` is false, nothing is written and the answer is `{"exists": true}`. `{"action": "save-ai", "agent",
    "lang"}` saves first, then calls `agents.launch_prompt(onboard.arch_prompt(lang), agent, lang)`.
  - `POST /api/app/onboard/done`: `finish`, then `env.checkpoint_commit("first setup")`.
  - `GET /firstlook` (no token: read-only, like the docs) serves `LAST_DRAFT["html"]` when it exists, else 404.

- [ ] **Step 1: Write the failing tests:**
  - `test_onboard_routes_need_the_token` (parametrized over every route above): with no token → 403 and
    `body["app"] is True`.
  - `test_state_and_step_round_trip`: `step {"id": "tools"}` → `state["step"] == "tools"`, and `firstrun.json`
    agrees.
  - `test_repos_validation`: a duplicate name → 400. Legacy with `[]` → 400 `repos`. Greenfield with `[]` → 200.
  - `test_setup_job_logs_progress` (`env.setup` and `env.install_prereq` monkeypatched): the job ends `done`, at
    least one log line matches `^\[\d+/\d+\]`, and `result["ok"] is True`.
  - `test_arch_save_asks_before_overwriting`: with `docs/architecture/model.c4` present, `save` without overwrite
    → `{"exists": True}` and the file is unchanged.
  - `test_server_starts_on_a_fresh_docs_root`: `onboard.start(empty_folder)`, then `camarones.py up --foreground
    --port 0` with `CAMARONES_APP_TOKEN` prints a `{"ready": true, "port": …}` first line within 30 s (the same
    pattern as `test_up_with_an_app_token_says_its_port`).

- [ ] **Step 2: Run them to verify they fail**, with `uv run pytest tests/test_onboard_api.py -q`.

- [ ] **Step 3: Implement `onboard.state()` and the routes.** The handlers stay thin: parse, call `onboard.*`,
  and return JSON. Jobs go through `start_job` with `fn(log)` returning `{"rc": 0|1, "result": …}`.

- [ ] **Step 4: Run** `uv run pytest tests/test_onboard_api.py tests/test_app_api.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

  `git commit -m "feat(serve): the app's onboarding endpoints, token only"`

### Task 6: Zones — the app window documents

**Files:**
- Modify: `.camarones/portal/app/src/zones.js`
- Test: `.camarones/portal/app/src/zones.test.js`

**Interfaces:**
- Produces:
  - Zones `docs`, `arch` and `quality` get `portal: true`. A new zone `{ id: 'next', href: '#/next', views: [{ id:
    'next', href: '#/next', app: true }] }` is first in `ZONES`. `ROUTES.next = ['next', 'next']` and
    `ROUTES.start = ['next', 'next']`.
  - `zonesFor('app', index)` → ids `['next', 'plan', 'board', 'review', 'taller']`. `live` and `static` are unchanged
    (`next` is app-only).
  - `export function portalOnly(hash: string): boolean`: true for addresses whose route maps to a `portal: true`
    zone (`#/docs…`, `#/doc…`, `#/wiki…`, `#/wikis`, `#/c4…`, `#/code…`, `#/data`, `#/libs`, `#/kpis`, `#/ci`,
    `#/arch`, `#/quality`).

- [ ] **Step 1: Write the failing vitest cases:** `app mode shows only the documenting zones`, `live and static
  modes are unchanged` (snapshot the ids from before the change), `portalOnly flags reading routes` (true for
  `#/docs/overview.md`, `#/c4`, `#/kpis`; false for `#/plan`, `#/review`, `#/kanban`, `#/generate`, `#/next`,
  `#/start`).

- [ ] **Step 2: Run** `npm test -- zones` in `.camarones/portal/app`. Expected: FAIL.

- [ ] **Step 3: Implement.** `available()` hides `portal` zones' views when `mode === 'app'`.

- [ ] **Step 4: Run** `npm test`. Expected: PASS.

- [ ] **Step 5: Commit**

  `git commit -m "feat(portal): the app window keeps next, plan, board, review and taller"`

### Task 7: Onboarding view at `#/start`

**Files:**
- Create: `.camarones/portal/app/src/onboarding.js` (pure step model), `.camarones/portal/app/src/onboarding.test.js`,
  `.camarones/portal/app/src/Onboarding.jsx`
- Modify: `.camarones/portal/app/src/Native.jsx`, `.camarones/portal/app/src/i18n.js` (keys `ob*` in `en` and `es`),
  `.camarones/portal/app/src/styles.css`, `.camarones/portal/app/public/legacy/app.js` (route `start`, first-run
  redirect)

**Interfaces:**
- Consumes: Task 5 routes; `useJob` (`src/useJob.js`) for the setup, scan and arch jobs; `getJSON`/`postJSON`.
- Produces:
  - `onboarding.js`:
    - `stepIndex(state) -> number`.
    - `canContinue(stepId, data) -> { ok: boolean, reason: string }`. The i18n key in `reason` is:
      - `obNeedRepo` for legacy repos with zero ticked.
      - `obNeedRequired` for tools with a required tool still missing.
      - `obSetupFailed` for setup that did not succeed.
    - `nextStep(state) -> string | 'done'`.
    - `prevStep(state) -> string | null`.
  - `Native` renders `Onboarding` for view `start`. The legacy router adds `start` to its native views when `RUNS`.
    After `appInfo`, it fetches `app/onboard/state`, and when `done` is false and the hash is not `#/start`, it calls
    `location.replace('#/start')`.

- [ ] **Step 1: Write the failing vitest cases** in `onboarding.test.js`:
  - `resumes at the saved step`.
  - `legacy needs a repo, greenfield does not`.
  - `required tools block continue`.
  - `join has three steps`.
  - `back from the first shown step is null`.
  - `after intro comes done`.

- [ ] **Step 2: Run** `npm test -- onboarding`. Expected: FAIL.

- [ ] **Step 3: Implement `onboarding.js`, then `Onboarding.jsx`** with the screens of the approved sketches:
  - A step indicator, then one panel per step: `repos`, `tools`, `setup` (progress bar from `[n/total]` lines, live
    log, Cancel through `/api/app/jobs/<id>/cancel`), `stack`, `arch` and `intro`.
  - `arch` shows its counts as repos, datastores + brokers and relations. "View diagram" calls
    `APP.openExternal(origin + '/firstlook')`. An existing model asks before it is overwritten.
  - `intro` has the buttons "Go to the next step" (`#/next`) and "View portal".
  - Footer with Back and Continue. Continue is disabled with `reason` shown next to it.
  - The install step's waiting line is the one joke, with its own wording in `es` and `en`. A setup that ends with
    `missing` repos shows the token form from `TallerPanels` (credentials) and Retry.

- [ ] **Step 4: Run** `npm test` and `npm run build` (in `portal/app`). Expected: PASS, and `app-build/` updated.

- [ ] **Step 5: Commit**, including `portal/app-build/`.

  `git commit -m "feat(portal): the first-run wizard in the app window (#/start)"`

### Task 8: Next step home, View portal, portal-only links

**Files:**
- Create: `.camarones/portal/app/src/Next.jsx`
- Modify: `.camarones/portal/app/src/Native.jsx`, `.camarones/portal/app/src/i18n.js`,
  `.camarones/portal/app/public/legacy/app.js` (header buttons, `routeNow`, the landing view),
  `.camarones/portal/app/index.html` (two header buttons `#view-portal`, `#projects`), `.camarones/portal/app/public/legacy/app.css`
- Test: `.camarones/portal/app/src/styles.test.js` (the header markup), vitest for `Next`'s pure part if one is
  split out

**Interfaces:**
- Consumes: `portalOnly` (Task 6), `AgentLaunch({ unit })`, `getJSON('pipeline')` (what `Pipeline.jsx` reads:
  units with `id`, `status`, `runner`, `available`), `getJSON('review')`'s count, `APP.openExternal`, `APP.hub`.
- Produces:
  - In mode `app`, `#/` and an unknown address go to `#/next` instead of `showStart()`.
  - `#view-portal` (shown only when `RUNS`) → `APP.openExternal(location.origin + '/#/')`. `#projects` → `APP.hub()`.
  - In `routeNow`, when `RUNS && window.CamaronZones.portalOnly(location.hash)`: `APP.openExternal(location.origin +
    '/' + location.hash)`, then `history.back()`, or `location.replace('#/next')` when there is no history. It never
    renders a portal-only view in the app.

- [ ] **Step 1: Write the failing tests:**
  - In `styles.test.js`, `the app header has View portal and Projects`: the built `index.html` contains
    `id="view-portal"` and `id="projects"`.
  - A vitest `next unit is the first available` over a pure `pickNext(units)` exported from `Next.jsx`, a module
    sibling `next.js` if JSX import is awkward. It picks the first `available` unit that is not `doing`, and the
    `doing` one comes first.

- [ ] **Step 2: Run** `npm test`. Expected: FAIL.

- [ ] **Step 3: Implement.** `Next.jsx` shows the next unit card with `AgentLaunch`, a "Another unit" link to
  `#/pipeline`, and the review count card linking to `#/review`. Before wiring the count, check the field names of
  `/api/pipeline` and of the review endpoint `showReview()` uses in `legacy/app.js`. The app menu keeps "Open in the
  browser" unchanged.

- [ ] **Step 4: Run** `npm test` and `npm run build`. Expected: PASS.

- [ ] **Step 5: Commit**

  `git commit -m "feat(portal): the app lands on Next step; View portal opens the browser"`

### Task 9: Desktop start screen

**Files:**
- Modify: `.camarones/desktop/hub/index.html`, `.camarones/desktop/hub/hub.js`, `.camarones/desktop/hub/hub.css`,
  `.camarones/desktop/main.cjs` (`handlers`), `.camarones/desktop/preload.cjs`, `.camarones/desktop/lib/core.cjs`
- Test: `.camarones/desktop/test/core.test.cjs`

**Interfaces:**
- Consumes: `projects --inspect/--adopt` (Task 4), `join --no-open` (unchanged).
- Produces:
  - `core.inspectArgs(dir) -> string[]` = `['projects', '--inspect', dir, '--json']`, and `core.adoptArgs(dir, name)
    -> string[]` = `['projects', '--adopt', dir, '--json']` plus `['--name', name]` when `name` is a non-empty string
    that does not start with `-`.
  - IPC `hub:pick` (folder dialog → `{dir}` or `{cancelled: true}`). `hub:inspect(dir)` → `{found}` or `{error}`.
    `hub:adopt({dir, name})` → `openProject(path)` or `{error}`.
  - `hub:join({url, token?})` keeps its flow with the new copy. A `token` goes to the CLI only as
    `CAMARONES_JOIN_TOKEN` in the child's environment (`cli(args, { env })`). A failure returns the CLI's JSON
    (`{error, host, detail}`). On `auth` the page shows the reason in plain words and a token field for `host`, then
    calls `join` again with the token. `hub:new` and `hub:add` are removed, along with their preload methods.
  - `window.camaronHub` = `{ list, open, pick, inspect, adopt, join, lang }`.

- [ ] **Step 1: Write the failing node tests:**
  - `inspectArgs`.
  - `adoptArgs drops a name that looks like an option`.
  - `adoptArgs with no name`.

- [ ] **Step 2: Run** `node --test` in `.camarones/desktop`. Expected: FAIL.

- [ ] **Step 3: Implement the helpers and IPC, then the hub page** with the approved sketch:
  - A title bar, the heading "¿Qué quieres documentar?" / "What do you want to document?", and the lede.
  - Two option rows: "Elegir carpeta" (primary) and "Unirme a la documentación de mi equipo", whose help text
    names the docs repo and says it is not the code's.
  - Recent projects.
  - A "what I found" card per `case`, with a badge, a sentence, the destination path, the `no-git` warning, an
    editable name, "Change folder" and "Continue".
  - No `.aurora-bg`, no `.hero`. All strings live in `S.es`/`S.en`.

- [ ] **Step 4: Run** `node --test`. Expected: PASS.

- [ ] **Step 5: Manual check:** `uv run --script .camarones/camarones.py app` from the worktree. Pick an umbrella,
  a single repo, an empty folder and an existing project. Each one reaches the right card, and Continue opens
  `#/start` (or `#/next` for a finished project).

- [ ] **Step 6: Commit**

  `git commit -m "feat(desktop): a start screen that asks what to document and accepts any folder"`

### Task 10: Docs, version, end to end

**Files:**
- Modify: `README.md`, `.camarones/lib/tutorial.py`, `.camarones/TUTORIAL.md` (regenerated),
  `.camarones/templates/docs/guides/tutorial.md`, `.camarones/templates/docs/i18n/es/guides/tutorial.md`,
  `.camarones/lib/common.py` (`VERSIONS["kit"] = "4.52.0"`), the README version badge

- [ ] **Step 1: Update the user docs** (AGENTS §5.1):
  - The README's desktop app section: start screen, wizard, View portal.
  - `tutorial.py` pages for the app's first run.
  - The command guide gets `projects --inspect/--adopt`.
  - Regenerate `TUTORIAL.md` with the command in AGENTS §5.1.

- [ ] **Step 2: Run** `uv run pytest -q` and `npm test` (portal) and `node --test` (desktop). Expected: all PASS
  (`test_wizard.py` checks `TUTORIAL.md`).

- [ ] **Step 3: End to end on the sandbox.** Run `uv run scripts/sandbox.py reset`, then open the app from this
  checkout and check:
  - Pick the sandbox's umbrella and go through the full legacy first run to "Next step".
  - "View portal" opens the system browser on the portal.
  - A docs link in Review opens the browser.
  - Closing the app at the setup step and reopening it resumes there.
  - `uv run scripts/sandbox.py cli` is the CLI wizard (`open`). It sees the same step.
  - A join run against a local bare clone of a project's `cam-docs`.

  Report each check that passes or fails, with what was seen.

- [ ] **Step 4: Commit**

  `git commit -m "docs: the desktop app's start screen and first-run wizard; kit 4.52.0"`
