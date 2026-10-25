# Desktop onboarding wizard and a documenting-only project window — design

Pieces A and B of "the desktop app's onboarding is strange". Piece C (a plan for projects with no code yet,
"greenfield") gets its own spec; this one only detects and records that kind.

## 1. Intent

Today the desktop app's hub (`desktop/hub/`) shows an aurora-gradient header and three buttons. "Create project" asks
for a name plus an optional "team's cam-docs repo" URL that reads like the code repo's URL. "Add folder" fails on a
folder without `cam-docs/`. Creating a project runs `new --no-open` and opens the portal: none of the CLI's first-run
steps (`name → repos → tools → setup → stack → arch → intro`, `lib/wizard.py`) ever run, so the app looks like it does
nothing. The project window then embeds the whole portal, so reading docs and doing the documenting work are mixed.

This piece:

1. **Replaces the hub with a start screen** that asks "What do you want to document?" and offers three ways in:
   pick a folder, join the team's documentation, or a recent project.
2. **Detects what the picked folder is**: it already has `cam-docs/`, it is a single repo, it is an umbrella folder of
   repos (legacy, there is code), or it has no code (greenfield). Any folder works; the project takes the folder's
   name.
3. **Runs the first run as an interactive wizard in the project window**: repos, tools, install and setup with live
   progress, stack, C4 draft, done. It is the CLI wizard's flow, sharing its saved position (`firstrun.json`), so a
   run started in the app can continue in the terminal and the other way round.
4. **Makes the project window the place to document**: next step, plan, review, board and Taller. Docs,
   architecture and quality are read in the portal, which "View portal" opens in the system browser.

**Anti-goals — a failure even if it works:** a URL field that can be read as either the docs repo or a code repo;
a folder picked by the person that ends with an error and no project; kit logic re-implemented in Electron or in the
browser; a 3.x/4.x project whose first run changes or restarts when opened in the new app; the portal embedded in the
project window again.

## 2. User flow

1. **Start screen** (hub window, no gradient: the title bar, a heading, a short lede):
   - **Pick a folder** — "The folder of your code (one repo or several), or an empty one if there is no code yet."
   - **Join my team's documentation** — "Your team already has a `cam-docs` repo. Paste its URL: it is the
     documentation's repo, not the code's." Then a folder picker for where it goes.
   - **Recent** — registered projects (`projects --json`), "Open" per row; rows not on disk say so.
2. **What I found** (same window, after picking a folder): one card with the detected case, where `cam-docs/` will
   live, and the project name (the folder's name, editable). Buttons: "Change folder", "Continue".
3. **Project window, wizard** (`#/start`): a step indicator and one step per screen, "Back" / "Continue". The steps
   depend on the mode (§4). Each step that runs something shows its live log and a progress bar, and can be cancelled.
4. **Done**: "Go to the next step" (lands on the project home) and "View portal".

Opening a project whose first run is finished goes straight to the project home. Opening one whose first run is
unfinished resumes the wizard at its saved step.

## 3. Folder detection — `lib/onboard.py`

`inspect(folder: Path) -> dict`, pure apart from reading the disk and `git remote`/`rev-parse`. Cases, first match
wins:

| Case | Test | Workspace | Kind |
|---|---|---|---|
| `project` | `folder/.camarones/workspace.yaml` (folder is a docs root), or `folder/cam-docs/.camarones/workspace.yaml` | that docs root's workspace | as recorded (absent = `legacy`) |
| `repo` | `folder/.git` exists | `folder.parent` | `legacy` |
| `umbrella` | `projects.has_repos(folder)` | `folder` | `legacy` |
| `code` | no git, but a manifest at the top or one level down (`pom.xml`, `build.gradle(.kts)`, `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `*.csproj`, `pubspec.yaml`, `composer.json`, `Gemfile`) | `folder` | `legacy`, plus `warning: "no-git"` |
| `empty` | none of the above | `folder` | `greenfield` |

For `repo`, an existing `folder.parent/cam-docs` that is a project turns the case into `project`.

Returns `{case, kind, workspace, docs_root, name, repos: [...docs.detect_repos rows for workspace], siblings: [...]
(repo case: the other repos in the parent), warning}`. `name` is the workspace folder's name. Never writes.

`start(folder, name) -> Path`: runs `inspect`, then `projects.adopt(workspace, slug(name))` (already idempotent and
already registers the project). It writes `workspace.yaml` exactly as the CLI's `fr_name` step does (name, id,
`canonical_language`, `translations`), adds `project.kind`, preselects the detected repos (the `repo` case: only the
picked repo), and saves `firstrun.json` at step `repos`. On `project` it only registers and returns the docs root,
writing nothing.

`fr_name`'s workspace writing moves into `onboard.name_project(ws, name)` and the CLI wizard calls it too: one
implementation.

**New `workspace.yaml` key:** `project.kind: legacy | greenfield`. If it is absent, the kit reads `legacy`, so 3.x/4.x
projects are unchanged. The CLI wizard writes it too, from `inspect(WORKSPACE)` in its name step. Its repos step then
allows zero repos when the kind is `greenfield`, and `r_need` applies only to `legacy`.

## 4. Wizard steps and shared state

The step ids stay the CLI's (`STEPS` in `lib/wizard.py`), so `firstrun.json` (`{step, name, done, mode}`) means the
same thing to both. `onboard.steps(mode, kind)` is the single source of the list, and the CLI's `first_run` uses it as
well:

| Mode / kind | Steps |
|---|---|
| `new`, `legacy` | `name`* · `repos` · `tools` · `setup` · `stack` · `arch` · `intro` |
| `new`, `greenfield` | `name`* · `repos` (optional, may stay empty) · `tools` · `setup` · `intro` |
| `join` | `tools` · `setup` · `intro` |

\* `name` is done on the start screen in the app. The app's wizard begins at the next step, while the CLI still
shows it.

`first_run_mode` (`wizard.py`) moves to `onboard` unchanged and decides `new` / `join` / `done` for both front ends.

Step contents (app). Each one calls the same `env`/`docs`/`radar`/`quickarch` functions as the CLI step:

- **repos** — the detected repos, checked. "Add a code repo" takes a URL, name and branch (as `add_url` does).
  Remove. `legacy` needs at least one repo; `greenfield` does not.
- **tools** — `onboard.tool_rows()` (moved out of `W.tool_rows`: prerequisites + kit tools + extras, each with
  `ok/kind/rec`). Required tools cannot be unticked. "Install recommended" is the default, and the person may pick.
  If a required tool is still missing after install, the step says to reopen the app (`env` cannot see a new `PATH`
  from inside the running process, same as the CLI's `reopen`).
- **setup** — one job: install the picked system tools (`env.install_prereq`), `env.set_components`,
  `env.init_templates`, `env.setup`, `plan.sync`, `plan.set_status("setup", "done")`. Progress uses
  `env.setup_steps()`. Repos that fail to clone show the CLI's token flow (`creds`), then "Retry".
- **stack** — `radar` scan, a table repo → stack, edit one (the `stack` command), "Looks right".
- **arch** — `quickarch.draft()`: counts (containers, relations, external systems), "View diagram" (the generated
  HTML in the browser), "Save draft", "Save and improve with AI" (saves, then `lib/agents.py` opens the agent session
  in its terminal window as the Taller does), "Skip". An existing `model.c4` asks before it is overwritten.
- **intro** — done screen, `firstrun.json` `done: true`, `env.checkpoint_commit("first setup")`.

Only one joke: the install step's waiting line (es/en adapted, AGENTS §3). Prompts, errors and the detection card
carry none.

## 5. How the app runs it

The hub keeps doing only what it needs before a project exists. Everything else is the project's server, as the
Taller already is.

**CLI (new, additive):**
- `projects --inspect DIR --json` → `onboard.inspect`.
- `projects --adopt DIR [--name NAME] --json` → `onboard.start`, prints `{"path": docs_root}`.
- `new` and `join` keep their behaviour and flags.

Both are in `lib/catalog.py` with verdict `app`, zone `projects`, and are added to `appapi.HUB`, like `new`/`join`.

**Hub (`desktop/hub/`, `main.cjs`):** a rewrite of `index.html`/`hub.js`/`hub.css` to the start and "what I found"
screens. The aurora block goes, and the title bar from the current uncommitted work stays. IPC changes:
`hub:inspect(dir)` (after the folder dialog) and `hub:adopt({dir, name})` → `openProject(path)`. `hub:join` keeps its
flow with the new copy. `hub:new` and `hub:add` go, because "Pick a folder" covers both. The CLI keeps `new` and
`projects --add`.

**Server (`lib/serve.py`, app token only):** `/api/app/onboard` endpoints, a thin layer over `lib/onboard.py`:
- `GET state` → `{mode, kind, steps, step, done, repos, found}`.
- `POST step {id}` → saves the position (Back/Continue).
- `POST repos {repos}` → validates and saves `workspace.yaml`.
- `GET tools` → `tool_rows()`.
- `POST setup {system, components}` → a job (`appapi.stream_job`, so it has a live log and can be cancelled), whose
  log lines carry the step counter for the bar.
- `GET/POST stack`.
- `POST arch {action: draft|save|save-ai, overwrite}`.
- `POST done`.

The server must start on a docs root that only has an empty `cam-docs/` and a `workspace.yaml`: a test covers it.

**Portal (`portal/app/src/`):** a new `Onboarding.jsx` view at `#/start`, available in mode `app` only, built with
the cofundo design system like the Taller. The legacy router sends the app to `#/start` when `state.done` is false.

## 6. The project window documents; the browser reads

In mode `app`, `zones.js` shows only **Next step** (a new home, `#/next`), **Plan**, **Review**, **Board** and
**Taller**. `docs`, `arch` and `quality` get `portal: true` and are hidden in `app`. They stay unchanged in `live` and
`static`.

- **Next step** (`#/next`): the plan's next available unit with "Start session with <agent>" (the existing
  `AgentLaunch`), "Another unit", and a card with the review count. It is the app's landing view.
- **View portal**: a header button in mode `app`. It calls `app:external(origin + '/#/')`, which is the same server
  without the token, so it is read-only. The application menu's "Open in the browser" stays.
- **Links to portal-only routes** (a doc link inside Review, a ⌘K entry, an old `#/docs/...` address): in mode `app`
  the router opens them in the browser through `app:external` and does not navigate.
- **"Projects"**: a header button that opens the start screen (`app:hub`, which already exists).

The browser portal lives while the project window is open, as today. `camaron up` stays the way to serve it on its
own.

## 7. Errors

- Folder dialog cancelled: nothing changes.
- `inspect` on an unreadable folder: one plain line on the start screen, and the screen stays.
- `adopt` refused (for example a non-empty `cam-docs/` that is not a project): the CLI's message, with
  "Change folder".
- Join: the `projects.connect`/`git_failure` reasons (denied, auth, not found, network) in plain words, with the token
  prompt when the reason is auth.
- Setup job fails: the job log stays, with "Retry". "Continue" is disabled with the reason (as `fr_setup` does).
- Install of a system tool fails: the manual hint from `prerequisites()[k]["hint"]`, as the CLI shows.

## 8. Testing (TDD, AGENTS §2.2)

- **pytest** (`tests/test_onboard.py`, `make_workspace` + `isolated_env`):
  - `inspect` for each case in §3, including a repo whose parent already has `cam-docs`, and code without git.
  - `start` is idempotent and writes the same `workspace.yaml` as the CLI's name step.
  - `project.kind` absent reads `legacy`.
  - `steps(mode, kind)` returns the lists in §4.
  - A `firstrun.json` written by the app resumes the CLI at the same step, and the other way round.
  - A zero-repo greenfield project passes `setup` and `plan.sync` without errors.
  - The server starts on a fresh docs root.
  - The `/api/app/onboard/*` endpoints refuse requests without the token.
  - `catalog --check` passes with the new flags.
- **Characterization first**: lock `first_run_mode`, `fr_name`'s writes and `tool_rows` before they move.
- **node --test** (`desktop/test/core.test.cjs`): any new pure helper in `core.cjs`.
- **vitest**: `zones.js` in mode `app` (only next/plan/review/board/taller, and portal-only routes flagged). The
  onboarding step model (which step, Back/Continue, disabled reasons).
- **End to end**: the sandbox (`scripts/sandbox.py`) with the app opened from this checkout. Run all four detection
  cases, a full legacy first run on PetClinic, a join, and "View portal" opening the browser.
- macOS, Windows and Linux in CI, as always.

## 9. Docs and version

- `README.md` (es): the desktop app section (start screen, wizard, View portal).
- Tutorial: `lib/tutorial.py`, then regenerate `TUTORIAL.md`. `templates/docs/guides/tutorial.md` and its es twin
  describe the new `projects --inspect/--adopt`. Existing projects keep their copy.
- `VERSIONS["kit"]` → 4.52.0.

## 10. Out of scope

- The greenfield plan (pipeline, units, interviews for design-first): spec C. Until then a greenfield project gets
  the plan `plan.sync` builds with zero repos.
- Changing the CLI wizard's screens: it only shares `onboard` functions and the state, plus the greenfield rule for
  zero repos (§3).
- Serving the browser portal after the app closes.
