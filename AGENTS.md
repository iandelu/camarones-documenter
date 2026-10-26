# Camarón kit — rules for agents working on this repo

This repo is the **kit itself** (wizard + CLI in `.camarones/`), not a documented project. `.camarones/CONVENTIONS.md`
and `PLAYBOOK.md` are rules the kit ships to *other* projects; the rules below are for changing the kit.

## 1. Goal

Improve, automate and standardise how AI documents software projects. Camarón is a **project brain**: one versioned
place (`cam-docs/`) where code, architecture, domain and decisions are explained for humans and agents alike.

**Priority order when choosing what to build:**

1. **Installing gives value almost without AI.** A fresh install sets up the documentation tooling and generates a
   logical base from static analysis only (repo detection, briefs skeleton, code graph, `arch-draft` C4, plan, portal).
   No model call, no paid account needed to get there.
2. **Then AI completes it:** interviews, drafting, debugging the model, improving the architecture, keeping it current.
3. Everything the AI adds stays reviewable and traceable (`x-sources`, draft → confirmed).

If a change only works when an agent is available, ask whether a non-AI first step can deliver part of it.

## 2. Non-negotiables for every change

### 2.1 macOS, Windows and Linux — always

Every change must work on all three. CI (`.github/workflows/tests.yml`) runs the suite on each; a red OS is a red build.

- Paths: `pathlib` only; never build paths with `/` or `\\` strings. Compare paths resolved, not as text.
- Files: always pass `encoding="utf-8"`; write text with LF (`newline="\n"` when it matters). `.gitattributes` fixes
  line endings per type (`*.cmd` CRLF, everything else LF) — respect it for new file types.
- Processes: go through the helpers in `lib/common.py` (`run`, `out`, `which`); no `shell=True`, no bash-only or
  cmd-only syntax inside Python. Windows needs `.cmd`/`.exe` resolution — the helpers handle it.
- Branch on `IS_WIN` / `IS_MAC` from `lib/common.py`, never on `sys.platform` strings scattered around.
- Launchers come in pairs: `camaron.cmd` ↔ `camaron.command`, `camarones.cmd` ↔ `camarones.command`,
  `install-global.cmd` ↔ `install-global.sh`. Change one, change its twin in the same commit.
- Symlinks/junctions, file locks, long paths and case-insensitive filesystems differ per OS: test the fallback.

### 2.2 TDD

- Write or extend the failing test first, then the code. Bug fix → a test that reproduces it.
- Before touching untested behaviour, lock it with a characterization test (see `tests/`).
- Tests are offline and deterministic: use `tests/fixtures/builder.py` (`make_workspace`) and the `isolated_env`
  fixture from `tests/conftest.py`; never touch the real `~/.camarones`. Network tests go under `tests/e2e/` with the
  `e2e` marker.
- Run: `uv run pytest -n auto` (all but e2e, one worker per core; leave `-n` out for a single file) ·
  `uv run pytest -m e2e` (clones real repos). A change is done when the suite is green; say so with the output, or say
  what failed.
- Tests run side by side, so each one owns its `tmp_path`, home and ports (bind port 0). `make_workspace` copies a
  per-process template, so it is cheap; never share state through module globals or fixed paths. A test that truly
  cannot run beside another one gets `@pytest.mark.serial`: all of them go to one worker, one at a time.
- **Sandbox for end-to-end checks.** If the sandbox project exists (`$CAMARONES_SANDBOX`, else
  `~/projects/camarones-sandbox`, with the Spring PetClinic repos), use it to verify a change end to end with this
  checkout's kit, beyond the unit suite: `uv run scripts/sandbox.py cli <command>` (or `open` for the wizard),
  then `traces` after uninstall flows (exit 0 = nothing left behind). `reset` restores the pinned repos without
  network. Never run the kit against a real project to test it. If the sandbox is missing, `reset` creates it
  (first run clones from GitHub); say so rather than skipping silently. The desktop app opened from this checkout
  (`uv run --script .camarones/camarones.py app`) has the same bench under Kit dev (`lib/kitdev.py`).

### 2.3 Backward compatibility (3.x and 4.x)

- Any project created by any **3.x or 4.x** kit must keep opening and working with the new kit, without manual steps.
- Pre-3.0 layouts are handled by `camaron migrate` (`lib/migrate.py`); do not break that path.
- Never rename or drop a CLI command, flag, `workspace.yaml` key, frontmatter field (`x-sources`, `x-owner`,
  `x-confirmed`, `x-translation-of`…), `plan.yaml`/`.state.json` field or file location without: reading the old form,
  converting it automatically and idempotently, and a test that starts from the old form.
- Keep old names as aliases (e.g. `camarones` → `camaron`) instead of removing them.
- Documents written by humans or confirmed by humans are never rewritten by a migration.
- Bump `VERSIONS["kit"]` in `lib/common.py` when behaviour visible to projects changes.

### 2.4 New tools: quick win first

Before adding any external tool (npm package, binary, MCP server, Python dependency), check it against **all** of:

1. **Real value, no overlap** — solves a gap the kit has today and does not duplicate a tool already integrated.
2. **Installs on macOS, Windows and Linux** via uv / pinned npm / pinned binary, no admin rights, no manual steps.
3. **Low integration cost** — integrated and tested in one session; optional and degrades gracefully if it fails.
4. **Local and licence-compatible** — code never leaves the machine; licence allows internal use.

If it fails one, do not add it: record it and the reason in `docs/research/tooling-candidates.md`. If it passes,
pin its version in `VERSIONS` and make install idempotent.

## 3. Voice: the intern shrimp

The wizard and CLI must be easy: one clear next step per screen, sensible defaults, `help` everywhere, no jargon the
user has not seen yet. Camarón talks like **your intern shrimp you sent off to document things**: eager, witty,
self-aware about being small.

- Clean humour: sea and shrimp wordplay, intern life ("I'll peel this repo for you"), no risqué double meanings.
- It must read natural, never forced: at most one joke per screen, and only where the user is waiting or succeeded.
- **No jokes** in errors, warnings, prompts that ask for a decision, anything destructive (`uninstall`), or `--json`/CI
  output. There, be short and precise.
- Every user-facing string exists in `es` and `en` (`T` in `lib/wizard.py`); the joke must work in both languages —
  adapt it, don't translate it literally.

## 4. Repo map

| Path | What |
|---|---|
| `.camarones/camarones.py` | entry point (uv inline script; its header lists runtime deps) |
| `.camarones/lib/` | `common` (paths, versions, processes), `wizard`, `install`, `env`, `plan`, `docs`, `quality`, `quickarch`, `migrate`, `upgrade`, `uninstall`, `mcp`, `serve`, `install_state` (what the kit wrote on this machine: trust, drift, `repair`), `budget` (`doctor --context`), `history` (git mining), `removed`, `answers` (Ask's AI answer), `kitdev` (the desktop app's bench in a kit checkout: sandbox, pytest, npm, node --test), `machine` (settings, the Machine panel), `doctor` (prerequisites, pinned tools and drift as data, each with the command that fixes it; the last check kept for the app), `agents` (an interactive agent session on a unit or the docs update, in its own terminal window: the wizard and the desktop app), `catalog` (where each CLI command lives: portal / desktop app / CLI; `catalog --check` keeps it in sync with the parser), `exporters`, `review`, `hooks`… |
| `.camarones/lib/harness/` | harness core ([RFC](docs/research/harness-refactor.md)): `ctx` (project paths as a value), `events` (run log), `ports` (adapter interfaces), `routing` (which runner does each tier), `pipeline` (YAML plans → units), `locks` (cross-process file locks: plan.yaml, wiki runs), `worktrees` (a unit's own cam-docs worktree in `<workspace>/.cw/<n>`), `integrate` (merge a unit's worktree back: main first into the branch, gates, then a merge that cannot conflict), `scheduler` (parallel runs: worktree units side by side, one in-place unit at a time, integration before dependents), `runs`/`kpis` (what runs did and cost, team roll-ups), `evals` (golden questions), `ab` (with vs without cam-docs), `drafts` (AI draft vs confirmed edits) |
| `.camarones/lib/pipelines/` | the plans as data: `units.yaml` (unit types), `full.yaml`, `quick.yaml`; `plan.blueprint()` expands them |
| `.camarones/lib/plugins/` | the kit's own plugins (`plugin.yaml` manifests, e.g. `gemini`); `harness/plugins.py` loads them and a project's `.camarones/plugins/` |
| `.camarones/lib/adapters/` | pluggable adapters; `runners/` holds the agent CLIs (`claude`, `codex`, `opencode`, command templates such as Gemini) behind the `Runner` port; autopilot, the wizard and wiki generation launch agents only through it |
| `.camarones/templates/` | files copied into projects (`AGENTS.md`, docs skeleton, i18n) — changes here reach old projects: see 2.3 |
| `.camarones/portal/` | `app/` the portal, React + Vite, `npm` only in the kit repo: `src/shell/` (header, sidebar, the hash router of `src/router.js`), `src/views/` (one per address, with its pure helpers and tests), `src/content/doc.js` (the Markdown renderer), `src/core.js` (docs index, language, theme; strings in `src/i18n/`); built into `app-build/` (committed, served at `/`; CI fails if it does not match its source). UI work follows the `cofundo-design-system` skill (`.claude/skills/`) and its `CAMARON.md` |
| `.camarones/ui/` | the kit both apps share: `theme/` (tokens, fonts, published as `theme/`), `src/` (base components, `cmdform.js` the catalog's forms, `result.js` a --json result's shape; imported as `@camaron/ui`), `i18n/`; no build of its own |
| `.camarones/desktop/` | the desktop app (`camaron app`, `lib/desktop.py` installs its pinned Electron into `~/.camarones/desktop`): `main.cjs` (one window per project on that project's server, started with an app token; the rail switches it in place), `preload.cjs`, `lib/core.cjs` and `lib/renderer.cjs` (pure helpers, `node --test "test/*.test.cjs"` in CI on every OS), `renderer/` the app's own UI (React + Vite on `.camarones/ui`, Vitest) built into `renderer-build/` (committed, served by each project's server at `/desktop/`; CI fails if it does not match its source). No kit logic here: the app's sections run catalog commands through `lib/appapi.py`, and its Board (`g b`) moves and adds cards with that token; the portal is the reader and runs no machine action (the app's Docs builds the C4, generates each wiki and its graph and answers Ask with AI, all behind that token); the portal it opens in the browser gets a per-session portal token that only writes the board |
| `tests/` | pytest suite; `pyproject.toml` holds dev deps only |
| `scripts/sandbox.py` | real-repo test bench (Spring PetClinic) |

## 5. Working here

- Code, comments, commit messages and these docs are in English; user-facing strings in `es` + `en`.
- Conventional commits (`feat(scope): …`, `fix(scope): …`), small and focused.
- Other agent sessions may be editing the tree in parallel: stage and commit only your own hunks.

### 5.1 README and tutorial move with the code

Any change a user can notice (command, flag, wizard screen, default, workflow, output, portal view) updates the user
docs **in the same commit**:

- `README.md` (Spanish): the feature description, commands and examples; the version badge when `VERSIONS["kit"]`
  changes.
- The tutorial, in `es` and `en`:
  - `lib/tutorial.py` (the wizard's tutorial pages). Regenerate `.camarones/TUTORIAL.md` from it; `test_wizard.py`
    fails if they differ. From `.camarones/`:
    `uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"`
  - The command guide shipped to projects: `templates/docs/guides/tutorial.md` and its twin
    `templates/docs/i18n/es/guides/tutorial.md`. Templates are copied once, so existing projects keep their copy;
    say so in the commit when the change matters to them.

If a change has nothing a user can notice, say so in the commit body instead of skipping the docs silently.
