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
- Run: `uv run pytest` (all but e2e) · `uv run pytest -m e2e` (clones real repos). A change is done when the suite is
  green; say so with the output, or say what failed.

### 2.3 Backward compatibility (3.x)

- Any project created by any **3.x** kit must keep opening and working with the new kit, without manual steps.
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
| `.camarones/lib/` | `common` (paths, versions, processes), `wizard`, `install`, `env`, `plan`, `docs`, `quality`, `quickarch`, `migrate`, `upgrade`, `uninstall`, `mcp`, `serve`… |
| `.camarones/templates/` | files copied into projects (`AGENTS.md`, docs skeleton, i18n) — changes here reach old projects: see 2.3 |
| `.camarones/portal/` | live/static portal |
| `tests/` | pytest suite; `pyproject.toml` holds dev deps only |
| `scripts/sandbox.py` | real-repo test bench (Spring PetClinic) |

## 5. Working here

- Code, comments, commit messages and these docs are in English; user-facing strings in `es` + `en`.
- Conventional commits (`feat(scope): …`, `fix(scope): …`), small and focused.
- Other agent sessions may be editing the tree in parallel: stage and commit only your own hunks.
