# Desktop onboarding ported onto the new desktop app — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the desktop onboarding on current `main`:
- the folder-detecting start screen in the renderer's hub mode,
- the first-run wizard as a renderer section,
- reading in the system browser,

plus the branch review's I1–I3 and the must-fix minors.

**Architecture:**
- The branch's Python work (`lib/onboard.py`, CLI flags, `/api/app/onboard/*`) is cherry-picked onto `main` and
  adapted to main's changes.
- The UI is rebuilt inside `desktop/renderer` with `@camaron/ui`: hub mode becomes the start screen, and a `#/start`
  section is the wizard.
- The Electron main process gains the hub IPC and one guard rule that sends portal addresses to the browser.

**Tech Stack:** Python 3.10+ (pytest via `uv`, xdist), Electron main/preload (CommonJS, `node --test`), React 19 +
Vite + Vitest (`desktop/renderer`, built into `desktop/renderer-build/`, committed).

**Spec:** `docs/superpowers/specs/2026-10-25-desktop-onboarding-port-design.md` (addendum). It amends
`docs/superpowers/specs/2026-10-25-desktop-onboarding-design.md`, which stays binding where the addendum is silent.
Approved screens: the branch's `.superpowers/sdd/2026-10-25-desktop-onboarding/approved-sketches.md` (copy them into
this worktree's SDD workspace at setup).

**Where:** worktree `.claude/worktrees/onboarding-port`, branch `worktree-onboarding-port`, from `main` at d190ca7.
The source branch is `worktree-onboarding` (its commits are named below). Run git with
`GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0=*`.

## Global Constraints

- macOS, Windows, Linux: `pathlib`, `encoding="utf-8"`, `newline="\n"`, processes through `lib/common.py` helpers,
  `IS_WIN`/`IS_MAC` only.
- Tests are offline and parallel-safe (AGENTS §2.2 on main): each test owns its `tmp_path`, home and ports (bind
  0). Use `@pytest.mark.serial` only when a test truly cannot run beside another.
  - Full run: `uv run pytest -n auto`. Single file: `uv run pytest tests/<file> -q`.
- Backward compatibility (AGENTS §2.3): `project.kind` absent reads `legacy`.
  - `new`, `join`, `projects`, `projects --add` and `pages --adopt` behave as on main.
  - 3.x/4.x `firstrun.json` shapes resume.
- One implementation per behaviour. The CLI wizard calls `onboard.*`, and the renderer holds no kit logic: it calls
  the server or the main process.
- `/api/app/onboard/*` and `POST /api/build` need the app token. `GET /firstlook` serves only the server-set draft
  file.
- The join token travels only in the child process's env (`CAMARONES_JOIN_TOKEN`). It never appears in argv, logs
  or output, and is never kept in UI state after a non-`auth` result.
- Every user string is in `es` and `en` (renderer `src/i18n.js` `S`). Exactly one joke: the install step's waiting
  line. No jokes in prompts, errors or the found card.
- UI uses `@camaron/ui` components and tokens (`.camarones/ui`). The approved sketches' copy is binding.
  - The start screen may use the two option icons from sketch A, as inline SVG with `aria-hidden` and
    `currentColor`. Record this exception in `.claude/skills/cofundo-design-system/CAMARON.md`.
- `desktop/renderer-build/` is committed and must match its source (CI checks it). Run `npm run build` in
  `desktop/renderer` after renderer changes.
- Kit version `4.58.0` (the next minor above main's 4.57.0; bump again if main moved on at merge time).

## Review Focus

1. **A repo directly under home.** The person picks `~/myapp`, where `myapp` is a repo sitting directly in home. The
   workspace would be `~`, so it must be refused with an explanation, never adopted. → Task 2,
   `test_a_repo_directly_under_home_is_refused`.
2. **"Inicializar git aquí" with manifests at the top and in subfolders.** Only the picked folder gets `git init`,
   not each subfolder. → Task 2, `test_git_init_prefers_the_top_folder`.
3. **A portal address from inside the app.** It must open in the browser, and the window must not navigate away.
   `/desktop` and `/desktop/…` stay in the window, and so does an `http://127.0.0.1:<other port>` address (another
   origin goes through the existing external rule). → Task 3, node test `outsideApp keeps the app and sends the
   portal out`.
4. **An existing 4.57 project with a finished first run.** Opened in the new app, it lands on Summary and never on
   `#/start`. A pre-3.3 index-only `firstrun.json` also resumes correctly. → Task 5, vitest `a finished first run
   opens on summary`.
5. **Join with a token that git accepts or refuses for a non-auth reason.** The token field and the in-memory
   token are cleared in both cases. Only an `auth` refusal keeps the field for a retry. → Task 4, vitest `the join
   token is dropped after any non-auth result`.

---

### Task 1: Port the Python core onto main

**Files:**
- Bring over: `.camarones/lib/onboard.py`, `tests/test_onboard.py`, `tests/test_onboard_api.py`,
  `tests/test_projects_cli.py`.
- Merge into main's versions: `.camarones/lib/{docs,wizard,serve,agents,appapi,catalog,projects}.py`,
  `.camarones/camarones.py`, `tests/conftest.py`, `tests/test_wizard.py`.

**Interfaces:**
- Produces: everything the branch's Tasks 1–5 produced, unchanged in name and shape.
  - From `onboard`: `inspect`, `kind_of`, `STEPS`/`LEGACY_STEPS`, `steps`, `mode`, `first_run_mode`, `resume_id`,
    `save_position`, `finish`, `firstrun_file`, `name_project`, `write_workspace`, `start`, `tool_rows`,
    `install_choice`, `install_tools(…, cancelled=None)`, `run_setup(log, cancelled=None)`, `missing_repos`,
    `arch_prompt(lang)`, `state()` (with `name`), `set_repos`, `go_to`, `arch_draft`, `arch_save`, `last_draft`,
    `done`.
  - CLI: `projects --inspect/--adopt`, plus the `taken` JSON from `--adopt --json` and from `join`/`new --no-open`.
  - `projects.Taken(ValueError)` and `agents.launch_prompt`.
  - Server: `/api/app/onboard/*` and `GET /firstlook`.

- [ ] **Step 1: Cherry-pick the branch's Python commits in order** onto `worktree-onboarding-port`:
  `4d7c854 9c1be77 c0d84e8 5e6fdf7 80143fe 99f9bce e816407 917c913`. Resolve each conflict by keeping main's
  behaviour and adding the branch's. In particular:
  - `wizard.py`: keep main's `MENU_DEFAULT`, `plan.title(...)` labels and the `arch_flow` change (`model.c4` as
    the "draft exists" marker, `quickarch.save(..., page=pages.layout() == "old")`). The branch's `arch_prompt` moves
    into `onboard.arch_prompt(lang)` *with* main's conditional `first-look.md` sentence.
  - `tests/conftest.py`: keep main's template and xdist setup, and add `"onboard"` to its module list.
  - `serve.py`: keep main's `/desktop/` routes, `app_summary`, `ui_lang` and `ready`. Add the branch's onboard routes,
    `CANCEL`, `/firstlook` and the cancel route branch. Do not bring the branch's `available` field (main has
    `ready`).
- [ ] **Step 2: Bring the Python-only hunks of three later branch commits.** Use `git checkout -p` or manual edits,
  and take no portal or desktop files:
  - `0c64bde`: `state()["name"]` and save-ai `{written, launched: false, error}`.
  - `58f5fdb`: `projects.Taken`, the `taken` JSON in `camarones.py`, and its tests in `tests/test_projects_cli.py`.
- [ ] **Step 3: Adapt `onboard.arch_save`** to `quickarch.save(model, overwrite=…, page=pages.layout() == "old")`.
  Add a test `test_arch_save_in_the_new_layout_writes_no_first_look` in `tests/test_onboard_api.py`: a new-layout
  project → `docs/architecture/model.c4` is written and `first-look.md` is not.
- [ ] **Step 4: Make the ported tests parallel-safe.** No fixed ports, no shared paths. Run each new file alone, then
  `uv run pytest -n auto`.
  - Expected: all pass except main's own baseline failures. Before blaming the port, record main's baseline by
    running the same command on `main` in a scratch worktree.
- [ ] **Step 5: Commit**, with one commit per cherry-pick as git makes them, plus
  `fix(onboard): adapt the ported core to main (pages layout, parallel tests)` for Steps 2–4.

### Task 2: I1, I2 and the small Python fixes

**Files:**
- Modify: `.camarones/lib/onboard.py`, `.camarones/camarones.py`, `.camarones/lib/catalog.py`,
  `.camarones/lib/wizard.py`.
- Test: `tests/test_onboard.py`, `tests/test_projects_cli.py`, `tests/test_onboard_api.py`.

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `onboard.is_home_or_root(path: Path) -> bool`: true when `path` resolved equals `Path.home()` resolved, or equals
    its own anchor (`C:\`, `/`). The comparison is case-insensitive on Windows.
  - `inspect(folder)`:
    - It adds `warning: "home"` when `is_home_or_root(workspace)`. A home warning wins over `no-git`.
    - A picked folder named `cam-docs` is inspected as its parent.
  - `start(folder, name)`:
    - Raises `onboard.Refused(ValueError)` with `.code == "home"` for a home warning.
    - Raises it with `.code == "no-git"` for case `code`.
    - Both run before anything is written.
  - `onboard.git_init(folder: Path) -> list[Path]`:
    - Runs `git init` in the picked folder when it has a manifest at its top. Otherwise it runs it in each
      first-level subfolder that has one (`MANIFESTS`, `*.csproj`).
    - Returns the initialised folders.
    - Raises `ValueError` when there is nothing to initialise, or when the folder already has `.git`.
  - CLI:
    - `projects --git-init DIR --json` → `{"initialised": [str]}` on stdout, exit 0.
    - `projects --adopt --json` prints `{"error": "home"|"no-git", "detail"}` on stdout and exits 1, with stderr
      unchanged in style.
    - `catalog.py` describes `--git-init` (es/en).
  - `set_repos` also rejects names containing `:` and the Windows device names `CON PRN AUX NUL COM1–COM9
    LPT1–LPT9`, case-insensitive, with or without an extension. The error is 400 `name`.
  - `wizard.retry_missing` uses `onboard.missing_repos()`, and the unused `ws_rel` import in `wizard.py` goes.

- [ ] **Step 1: Write the failing tests.** Use `isolated_env`; point `HOME`/`USERPROFILE` at a tmp folder to stand
  in for home.
  - `test_picking_home_is_refused`: `inspect(home)["warning"] == "home"`, and `start(home)` raises `Refused` with
    code `home`. Nothing is written under home.
  - `test_a_repo_directly_under_home_is_refused`: `make_repo(home / "myapp")` → `inspect(...)` gives `case ==
    "repo"` and `warning == "home"`. `start` raises `home`.
  - `test_a_filesystem_root_is_refused`: `onboard.is_home_or_root(Path(Path.cwd().anchor))` is True, and
    `is_home_or_root(tmp_path)` is False.
  - `test_code_without_git_cannot_be_started`: `start` on a `src/package.json` folder raises `Refused` with code
    `no-git`, and no `cam-docs` is created.
  - `test_git_init_prefers_the_top_folder`: the folder has `pom.xml` at the top and `web/package.json` → only the
    folder gets `.git`. A second call raises `ValueError`.
  - `test_git_init_initialises_each_code_subfolder`: `api/pom.xml` and `web/package.json`, nothing at the top → both
    get `.git`. A re-inspect gives `case == "umbrella"` with repos `api` and `web`.
  - `test_a_picked_cam_docs_folder_means_its_parent`: inspecting `ws/cam-docs` (an empty folder) equals inspecting
    `ws`.
  - `test_repo_names_reject_drive_and_device_names`: `"C:x"`, `"con"`, `"NUL.txt"`, `"com1"` → 400 `name`.
  - In `test_projects_cli.py`:
    - `test_git_init_json`: the folder initialised and the JSON lists it.
    - `test_adopt_home_and_no_git_say_so_as_json`: the error codes on stdout, exit 1.
- [ ] **Step 2: Run them; they must fail.** Run: `uv run pytest tests/test_onboard.py tests/test_projects_cli.py -q`.
- [ ] **Step 3: Implement the Produces list.** `git init` goes through `common.run(["git", "init", "-q"], cwd=…)`.
- [ ] **Step 4: Run the touched test files, then `uv run pytest -n auto`.**
- [ ] **Step 5: Commit**: `feat(onboard): refuse home as a workspace; offer git init for code without git`.

### Task 3: Electron main process — hub IPC and reading in the browser

**Files:**
- Modify: `.camarones/desktop/lib/core.cjs`, `.camarones/desktop/lib/renderer.cjs`, `.camarones/desktop/main.cjs`,
  `.camarones/desktop/preload.cjs`.
- Test: `.camarones/desktop/test/core.test.cjs`, `.camarones/desktop/test/renderer.test.cjs`.

**Interfaces:**
- Consumes: the CLI from Tasks 1–2.
- Produces:
  - Ported from the branch's `desktop/lib/core.cjs` (commits 44891ce and 58f5fdb), same names and tests:
    `inspectArgs`, `adoptArgs`, `joinArgs`, `joinFailure`, `adoptError`, `folderArg`, and `cliEnv` stripping
    `CAMARONES_JOIN_TOKEN`. `adoptError` reads the stdout JSON code (`taken|home|no-git`) and has no text regex.
  - New in `core.cjs`: `gitInitArgs(dir)` = `['projects', '--git-init', dir, '--json']`.
  - New in `renderer.cjs`: `outsideApp(url, origin) -> boolean`.
    - True when `url` has the window's origin and its path is not `/desktop` or under `/desktop/`.
    - False for another origin (the existing external rule handles that) and for unparsable input.
  - `main.cjs`:
    - The project window's `guard` calls `outsideApp`. For `will-navigate` and `setWindowOpenHandler` on such a
      URL, it prevents navigation and calls `shell.openExternal(url)`.
    - The hub IPC is `hub:lang`, `hub:list`, `hub:open`, `hub:pick` → `{dir}|{cancelled}`, `hub:inspect(dir)` →
      `{found}|{error, detail}`, and `hub:adopt({dir, name})` → `openProject(path)`|`{error, detail}`.
    - `hub:join({url, token?})` asks for the folder, unless it is an auth retry where the renderer passes
      `dir`. A token goes only through `cli(args, { env })`. A failure returns `{error, host, detail, dir}`.
    - `hub:gitInit(dir)` → `{initialised}|{error, detail}`.
    - `hub:new` and `hub:add` are removed. `cli()` gains an `env` option.
  - `preload.cjs`: `window.camaronHub = { list, open, pick, inspect, adopt, join, gitInit, lang }`.

- [ ] **Step 1: Write the failing node tests.**
  - Port the branch's core tests for the helpers above.
  - Add `gitInitArgs`.
  - Add `outsideApp keeps the app and sends the portal out`:
    - true for `http://127.0.0.1:5000/#/review` and `http://127.0.0.1:5000/raw/x.png`;
    - false for `http://127.0.0.1:5000/desktop/#/plan`, `http://127.0.0.1:5000/desktop`,
      `http://127.0.0.1:6000/#/` and `not a url`.
- [ ] **Step 2: Run** `node --test` in `.camarones/desktop`. Expected: FAIL.
- [ ] **Step 3: Implement.** Keep main's title bar, rail, `app:switch` and `app:external` untouched.
- [ ] **Step 4: Run** `node --test` and `uv run pytest tests/test_desktop.py tests/test_desktop_renderer.py -q`.
- [ ] **Step 5: Commit**: `feat(desktop): start-screen IPC; portal addresses open in the browser`.

### Task 4: The start screen in the renderer's hub mode

**Files:**
- Create: `.camarones/desktop/renderer/src/hub.js` (pure), `.camarones/desktop/renderer/src/hub.test.js`,
  `.camarones/desktop/renderer/src/Hub.jsx`.
- Modify: `.camarones/desktop/renderer/src/App.jsx` (its `Hub` is replaced by an import),
  `.camarones/desktop/renderer/src/i18n.js` (`hub.*` keys rewritten, es/en), `.camarones/desktop/renderer/src/app.css`,
  `.claude/skills/cofundo-design-system/CAMARON.md` (the icon exception line).
- Test: `hub.test.js`, `App.test.jsx`.

**Interfaces:**
- Consumes: `window.camaronHub` from Task 3.
- Produces:
  - `hub.js`:
    - `card(found) -> { badge: 'existing'|'new'|'documented', titleKey, bodyKey, dest, canContinue, warningKey?,
      action?: 'gitInit' }`. It covers every case and warning: `home` → `canContinue: false`, warning `hub.home`.
      `code` → `canContinue: false`, `action: 'gitInit'`, warning `hub.noGit`.
    - `errorKey(code) -> i18n key`, for `taken`, `home`, `no-git`, `folder`, `auth`, `denied`, `not-found`,
      `network`, `unknown` and `url`.
    - `joinStep(state, result) -> state`: the token reducer. It keeps `dir` and shows the token field only after
      `auth` with a host. Every other result clears the token and `dir`.
  - `Hub.jsx` renders the three screens from sketches A and B, plus the join form. The branch's
    `desktop/hub/hub.js` (commits 44891ce and 58f5fdb) has the full copy, in es/en; port the strings.
  - On a found card with `action: 'gitInit'`, the button "Inicializar git aquí" calls `hub.gitInit(dir)`, then
    inspects again.

- [ ] **Step 1: Write the failing tests.**
  - `hub.test.js`:
    - `card` for each case: umbrella, repo with siblings, empty, project, code, and home on top of repo.
    - `errorKey` covers every code.
    - `the join token is dropped after any non-auth result`: `joinStep` with `ok`, `taken`, `network`,
      `auth`-without-host and `auth`-with-host. Only the last keeps `token` visible and `dir`.
  - `App.test.jsx`: with `window.camaronHub` stubbed, the static markup has the heading "¿Qué quieres documentar?" and
    both option buttons, and no "Crear proyecto" or "Añadir carpeta".
- [ ] **Step 2: Run** `npm test` in `.camarones/desktop/renderer`. Expected: FAIL.
- [ ] **Step 3: Implement**, using `@camaron/ui` (`Button`, `Card`, `Field`, `Aviso`, `EmptyState`).
- [ ] **Step 4: Run** `npm test` and `npm run build`. Commit `renderer-build/` with the source.
- [ ] **Step 5: Commit**: `feat(desktop): the start screen asks what to document and accepts any folder`.

### Task 5: The first-run wizard as a renderer section

**Files:**
- Create: `.camarones/desktop/renderer/src/onboarding.js`, `.camarones/desktop/renderer/src/onboarding.test.js`,
  `.camarones/desktop/renderer/src/sections/Start.jsx`.
- Modify:
  - `.camarones/desktop/renderer/src/App.jsx`: the first-run redirect, and a full-width layout on `start`.
  - `.camarones/desktop/renderer/src/nav.js`: `start` is a known section, not listed in the nav.
  - `.camarones/desktop/lib/renderer.cjs`: `SECTIONS` gets `start`.
  - `.camarones/desktop/renderer/src/sections/Machine.jsx`: export `Tokens`.
  - `.camarones/desktop/renderer/src/i18n.js`: `ob*` keys.
  - `.camarones/desktop/renderer/src/app.css`.

**Interfaces:**
- Consumes: `/api/app/onboard/*` (Task 1) through `server(token)`, `useJob` (`hooks.js`) and Machine's `Tokens`.
- Produces:
  - `onboarding.js` is ported from the branch's `portal/app/src/onboarding.js` (commits baaabd6 and 0c64bde), with the
    same exports and tests: `stepIndex`, `canContinue`, `nextStep`, `prevStep`, `repoFromUrl`, `defaultPicks`,
    `setupChoice`, `progressOf`, `manualHints` and `errorKey`. Adapt the imports.
  - `Start.jsx` ports the branch's `Onboarding.jsx`, with the review fixes:
    - editable name and branch when adding a repo by URL;
    - the setup result is cleared when the tool picks change;
    - a draft-start error has a Retry;
    - `launched: false` counts as saved, plus a warning.
    - When it finishes, it navigates to `#/summary`.
    - "Ver portal" uses `app.openExternal(origin + '/#/')`.
  - The arch step's no-agent warning is `obAgentMissing`: es "No encuentro ese agente: el borrador está guardado;
    mejóralo luego desde el Plan." / en "I can't find that agent: the draft is saved; improve it later from the
    Plan."
  - `App.jsx` `Project`:
    - After the index loads, `srv.get('app/onboard/state')`. When `done` is false and the hash is not `#/start`,
      `location.replace('#/start')`.
    - On `start` it renders without the rail and the side nav.
    - A state fetch error keeps the normal layout and does not block.

- [ ] **Step 1: Write the failing tests.**
  - `onboarding.test.js`: the branch's cases, plus `the no-agent warning promises nothing disabled` (the key exists in
    es and en and does not contain "elige" / "pick").
  - A vitest over a pure `firstRunRoute(state, hash)` exported from `nav.js`:
    - `a finished first run opens on summary`: `done: true` → null.
    - `done: false` on `#/plan` → `#/start`.
    - `done: false` on `#/start` → null.
- [ ] **Step 2: Run** `npm test`. Expected: FAIL.
- [ ] **Step 3: Implement.** The joke line stays the only joke, as in the branch.
- [ ] **Step 4: Run** `npm test`, `npm run build` and `node --test` (for renderer.cjs).
- [ ] **Step 5: Commit**: `feat(desktop): the first-run wizard in the project window (#/start)`.

### Task 6: Docs section, Ver portal and the C4 / wiki graph builds (I3)

**Files:**
- Modify: `.camarones/desktop/renderer/src/App.jsx` (the header button, the `Docs` section moved to
  `sections/Docs.jsx`), `.camarones/desktop/renderer/src/i18n.js`, `.camarones/desktop/renderer/src/app.css`.
- Create: `.camarones/desktop/renderer/src/sections/Docs.jsx`.
- Test: `App.test.jsx`, `.camarones/desktop/renderer/src/docs.test.js` (a pure helper).

**Interfaces:**
- Consumes: `POST /api/build` with `{what: 'c4'}` or `{what: 'wiki-graph', repo}` (token-gated, existing),
  `GET tree` (repos with wikis, as the portal reads them), `useJob`, and `app.openExternal`.
- Produces:
  - The project header has a "Ver portal" button → `app.openExternal(location.origin + '/#/')`.
  - The Docs section's "Leer", "Revisar" and "Buscar" open the browser through `app.openExternal` (no `href`
    navigation).
  - The Docs section has a "Construir el explorador C4" job card with "Ver" (`origin + '/#/c4'`). It also has one
    wiki-graph card per repo with a wiki, with "Ver" (`origin + '/#/wiki/<repo>'`).
  - `docs.js` has `portalUrl(origin, hash)` and `wikiRepos(tree)`.

- [ ] **Step 1: Write the failing tests.**
  - `docs.test.js`: `portalUrl('http://127.0.0.1:5000', '#/c4') === 'http://127.0.0.1:5000/#/c4'`, and the empty hash
    gives `/#/`. `wikiRepos` lists only repos whose docs have the wiki space.
  - `App.test.jsx`: the project header markup has the Ver portal button.
- [ ] **Step 2: Run** `npm test`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npm test` and `npm run build`.
- [ ] **Step 5: Commit**: `feat(desktop): Ver portal, reading in the browser, C4 and wiki graph builds from the app`.

### Task 7: Docs, version, end to end

**Files:**
- Modify: `README.md`, `.camarones/lib/tutorial.py`, `.camarones/TUTORIAL.md` (regenerate),
  `.camarones/templates/docs/guides/tutorial.md`, `.camarones/templates/docs/i18n/es/guides/tutorial.md`,
  `.camarones/lib/common.py` (`VERSIONS["kit"] = "4.58.0"`), and the README badge.

- [ ] **Step 1: Update the user docs against main's app sections** (AGENTS §5.1):
  - the start screen (any folder, home refused, git init offered);
  - joining with a token;
  - the wizard at `#/start`;
  - landing on Resumen;
  - Ver portal and reading in the browser;
  - the C4 and wiki-graph builds in Docs;
  - the CLI flags (`--inspect`, `--adopt`, `--git-init`, the JSON codes);
  - the CLI greenfield behaviour.

  The branch's d99d96a and 248be9b texts are a starting point. Say in the commit body that existing projects keep
  their guide. In es, call the zones what the es UI calls them.
- [ ] **Step 2: Run** `uv run pytest -n auto`, `npm test` in `desktop/renderer`, `node --test` in `desktop`, and
  `uv run pytest tests/test_wizard.py -q` (TUTORIAL in sync).
- [ ] **Step 3: End to end on the sandbox** (`~/projects/camarones-sandbox`, with a throwaway HOME for the registry):
  - CLI `--inspect` on all cases, including home and code-without-git.
  - `--git-init`, `--adopt`, and `join` against a local bare clone.
  - A real `up --foreground` with an app token, driving the whole `/api/app/onboard/*` flow over HTTP, including
    cancel and retry.
  - `POST /api/build {what:'c4'}` with the token.
  - The browser portal without the token.

  Report each check, and finish with the list of Electron-window checks for a person.
- [ ] **Step 4: Commit**: `docs: the start screen and first-run wizard in the new desktop app; kit 4.58.0`.
