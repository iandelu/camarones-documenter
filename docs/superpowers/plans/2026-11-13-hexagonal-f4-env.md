# Hexagonal refactor F4 (env.py) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `.camarones/lib/env.py` (2022 lines: 133 functions, 2 classes and 38 constants, 173 names) into nine
adapters behind `typing.Protocol` ports and eight use-case modules in `lib/app/`, reached through a `Services` value
built once per process by `lib/bootstrap.py`. `env.py` ends as a facade, and nothing a user can notice changes.

**Architecture:** Task 1 adds the composition root (`bootstrap.build()`), the process's services holder
(`lib/app/services.py`), the `ports` package, `CliContext.services`, `Request.services` and the tests that track the
split. Tasks 2–10 move one adapter each, plus its port. Tasks 11–19 move env's orchestration into `lib/app/` (and its
CI install into `lib/ci.py`). Each move is verbatim, and every caller and test is retargeted in the same task. Outside
the new modules, kit code reaches a moved name only through `services`, never by importing its module. That keeps
the allowlist from growing and the new modules out of the import cycle. Task 20 makes `env.py` a facade with layer
`facade`.

**Tech Stack:** Python ≥ 3.10 stdlib (`dataclasses`, `typing.Protocol`, `types.ModuleType`, `inspect`, `ast`),
pytest + pytest-xdist. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-12-hexagonal-refactor-design.md` (§2, §3 row `env.py`, §4.4, §5, §6 row F4,
§7, §8). Read it first, then the F3 plan's P1, P9–P11 (`docs/superpowers/plans/2026-11-13-hexagonal-f3-http.md`) and
F2's P1, P6, P11 (`docs/superpowers/plans/2026-11-12-hexagonal-f2-cli.md`), which this plan builds on.

## Decisions this plan takes

The spec leaves these open, or contradicts itself on them. Each decision is final for F4.

| # | Decision | Why |
|---|---|---|
| P1 | A port is a `typing.Protocol` in `lib/ports/<port>.py`. Its members are exactly the functions and constants that code outside the adapter uses, with today's signatures (defaults written `= ...`). An adapter is a **module** of functions moved verbatim, not a class: a module satisfies a Protocol structurally (PEP 544). A conformance test checks that every member exists, with the same parameter names, kinds and has-a-default | Moves stay verbatim and tests keep patching module functions. There is no wrapper layer, and the port still pins the contract |
| P2 | F4 introduces `lib/bootstrap.py`. Its `build(**overrides) -> Services` builds the process's services (each port's adapter module, each use-case module), installs them and returns them; an override replaces one field (tests pass fakes). Builds happen only at process entries: `interfaces.cli.main.main()` (every `camarones.py` run: commands, `up --foreground`, `mcp`, hooks, the merge driver), the preamble of `harness.integrate._kit` (kit code run in a unit's tree in its own process: the `check` and `arch-validate` gates, `docs.collect`, `plan.prompt`) and `tests/conftest.py::load_kit` | Spec D4 and §4.4. F2's P1 and F3's P1 deferred `services` to "when bootstrap.py exists". Under §2, app and interfaces code can reach an adapter only through bootstrap. `_kit` never goes through `main()`, and `docs.check()` will reach `old_wikis` through services |
| P3 | The services live in `lib/app/services.py`. It defines `Services`, `install(s) -> Services` (called by bootstrap only) and `current() -> Services`, which raises `RuntimeError("services not built: lib.bootstrap.build() runs first")` before an install. `Services` declares its fields as class annotations: adapter fields typed by their Protocol, use-case fields typed `types.ModuleType`. It resolves each field on first read from a provider (a function in `bootstrap.py` that imports the module and returns it), then caches it; `__setattr__` raises. The holder imports only `lib.ports` | The function modules in `app/` (doctor, onboard, trust, uninstall, install_state, migrate, reset, hooks, plan, docs, agents, c4edit, `harness.*`) call env today, and turning them into use cases is F5–F7's job. A holder with a single setter keeps F4 mechanical. If the holder imported a use-case module, it would pull that module into the import cycle (P4). Resolving lazily keeps start-up as it is: importing env and what it pulls in costs ~195 ms here, which `camaron version` and `help` never paid. The provider's import sits inside a function, which archscan still counts, so bootstrap's dependencies stay visible |
| P4 | **Access rule.** Outside the new modules, kit code reaches a moved name only through services: commands use `cli.services.<field>.<name>`, routes `req.services.<field>.<name>`, everything else `services.current().<field>.<name>` (with `from lib.app import services`, or relative in a module that uses relative imports). Inside the new modules, an adapter imports another adapter, and a new app module imports another new app module, directly; a new app module reaches an adapter through services. Exceptions: names that move into `core/` or `lib/ports` (`WIKI_STAMP`, `WIKI_LOCK`, `stream`, `Log`) or into `lib/ci.py` are imported directly. `test_moved_code_is_reached_through_services` enforces the rule | The cycle records only go down, and `env` sits in the largest cycle (52 modules) until Task 20. A new app module imports `docs`. If a cycle member imported it directly, it would join the cycle and the record would grow (simulated: 57 at the end with direct imports, against 43 with this rule; ledger below). §4.4 has `Services` carry the use cases anyway. The runtime coupling (`docs` → the wiki's `old_wikis`, say) is still there, and F5–F7 remove it when those modules become use cases with ports |
| P5 | **Where §3's row and §2's rule disagree, §2 wins.** An adapter imports nothing from `app`, `docs` included, so a function whose body (or any helper that moves with it) calls an app module goes to the app side. No function body is split in F4. The §3 names that stay app-side: `build_c4`, `graph`, `build_graphs` (app/viewers), `install_graphify_skill`, `write_agent_config`, `write_codex_mcp`, `prerequisites`, `java_info` (app/setup), every `wiki_*` name except the engine's `wiki_open`, `wiki_close`, `wiki_workdir` and `wiki_lock`, plus `openwiki_generate`, `wire_openwiki`, `_WikiRun` and `WikiAbort` (app/wiki), `docker_up`, `docker_down`, `compose_cmd` (app/portal), and `checkpoint_commit` (app/share). `openwiki_installed` goes to prereqs | D3: the allowlist only shrinks, and every adapter that imported `docs` would add a line (`adapters.likec4 -> docs`…). Five such lines did not fit the budget (the simulation's first draft). F5 turns `docs` into ports (`DocStore`), after which a use case can pass the values in and these names can move into their adapters (F7). `write_codex_mcp` writes through `_own_file`, and its only caller is `write_agent_config`. `checkpoint_commit` and `share` call each other through the `_sharing` flag, so they share a module. `tool_ok` needs `openwiki_installed`, and keeping both in prereqs avoids a prereqs ↔ openwiki import cycle |
| P6 | App-side homes: §3's `app/setup`, `app/templates`, `app/share`, `app/export_site`, `app/portal`, plus three more. `app/components.py` holds the project's chosen components, shared by setup, viewers, wiki and export. `app/viewers.py` is env's "portal: viewers (C4, code graph, wiki graphs)" section, used by setup, export and the routes. `app/wiki.py` is §4.4's `GenerateWiki`. `detect_forge` and `install_ci` go into `lib/ci.py`, which already reads `env.detect_forge`. `WIKI_STAMP` and `WIKI_LOCK` go to `core/paths.py`, `stream` to `core/process.py`, `Log` to `lib/ports/__init__.py` | Together they keep the new app modules acyclic among themselves (components ← templates ← viewers ← setup ← wiki ← export_site). Constants that a domain or legacy app module reads (`harness.ledger` reads `WIKI_STAMP`; `reset` and `uninstall` read `WIKI_LOCK`) become legal from every layer. `stream` is a process helper (AGENTS.md §2.1). Moving `WIKI_STAMP` pays `harness.ledger -> env` |
| P7 | Order: adapters by dependency and risk (os_open, likec4, fs_links, agent_config, prereqs, graphify, openwiki, docker, git checkpoint), then app modules by dependency (components, templates, viewers, setup, share, wiki, portal, export_site, ci), then the facade. §6's "setup, templates, share, export_site, portal" is reordered, because setup imports templates and viewers, and export imports the wiki | A new module never imports env for a name not moved yet. os_open has no dependencies and proves the pattern first. fs_links (Windows junctions, §8) comes before openwiki, which uses it |
| P8 | Names do not change: `_unlink`, `_linked`, `_is_link`, `_merge`, `_sharing` keep their leading underscore in their new homes, and ports list them as members | A rename would be a change hidden inside a move (spec §1) |
| P9 | During the transition, env imports nothing back for compatibility. Each task retargets every caller and test of the names it moves, and Task 20's facade restores every old `lib.env.<name>` at once. Until then, `lib.env.<moved>` is an `AttributeError` | For env (app layer), re-importing an adapter name is a violation (`env -> adapters.likec4`), so compatibility imports would grow the allowlist. No shipped template, plugin or script imports `lib.env` (checked: `grep -rn "lib\.env\|from lib import" .camarones --include=*.py --include=*.yaml --include=*.yml --include=*.md --include=*.cmd --include=*.command --include=*.sh`, outside `lib/`). Other sessions port such calls on rebase (Global Constraints) |
| P10 | A move keeps function bodies verbatim. The only edits: a call to a moved name goes through services, or through a direct import inside the new modules (P4); `Log` comes from `lib.ports`; kit imports in new modules are absolute (`from lib import docs`, F2's P11), and module-level imports stay module-level while imports inside a function stay inside (F3's P10); comments and docstrings that name `env.X` name its new home. Logger names do not change | Each diff stays reviewable as a move |
| P11 | Tests patch where the code under test looks the name up (AGENTS.md §5). The test namespace gains `kit.services` (built in `load_kit`), so `kit.env.X` becomes `kit.services.<field>.X` and `monkeypatch.setattr(kit.env, "X", …)` becomes `monkeypatch.setattr(kit.services.<field>, "X", …)`: each field is the module itself. String forms `"lib.env.X"` become `"lib.<home>.X"`. A patch of a name env had only imported (`env.run`, `env.which`, `env.IS_WIN`, `env.cli_cmd`, `env.load_json`) moves to the module whose function the test exercises. `kit.wizard.env` patches move to the adapter. Core and `lib/ci.py` homes come from `importlib.import_module` | Patches keep landing on the module that runs the code. `test_no_test_reaches_a_moved_name_through_env` catches what the facade guard cannot see while env is not yet a facade |
| P12 | `tests/fixtures/archscan.py` gains the layer `facade`: it may import every layer, and no layer may import it. Task 20 sets `env: facade` in `layers.yaml` | Under any real layer, a facade that re-exports adapters and use cases breaks the rule (env as `app` → 9 adapter lines). The kit's own code never goes through a facade anyway (the read check, P4). F5's `docs.py` and `plan.py` facades will need the same layer |
| P13 | The facade re-exports every name env.py defines today, plus `pid_alive` and `git_failure` (env's two declared re-exports). It does not re-export the core names env merely imports (`ROOT`, `run`, `which`, `CACHE`…: `lib.common` has them). `__facade__ = "lib.app and lib.adapters"`; `tests/test_env_split.py`'s `HOME` names each home | F3's rule ("every public name the module defined"). The guard names the defining module from `__module__` for functions; for constants it falls back to the facade string |
| P14 | `CliContext` gains `services: Services \| None = None` and `Request` gains the same field. The annotations are imported under `TYPE_CHECKING`, so loading the registry still imports nothing outside `lib.interfaces.cli` (F2's P6, `test_loading_the_registry_imports_nothing_outside_the_cli`). `main()` and `server.Handler.answer` fill them from `services.current()` | The F2 and F3 debt. Commands and routes receive services as the spec's §4.1 and §4.2 show |
| P15 | Port names: `Launcher` (os_open), `DiagramEngine` (likec4), `FileLinks` (fs_links), `AgentConfig` (agent_config), `Toolchain` (prereqs), `CodeIndexer` (graphify), `WikiEngine` (openwiki), `ContainerRuntime` (docker), `Vcs` (git checkpoint; it grows in F5 with `adapters/git/repos.py` and `worktrees.py`). The spec's names (§3, last paragraph) where it gives one | — |

## Name map

Every name env.py defines, by home. Task 1 transcribes this table into `HOME` in `tests/test_env_split.py`. Members of
a port (P1) are **in bold**; the other names are internal to the adapter, or read only by tests through the module.

| Home (`.camarones/lib/…`) | Task | Services field · port | Names |
|---|---|---|---|
| `ports/__init__.py` | 1 | — | `Log` |
| `adapters/system/os_open.py` | 2 | `launcher` · `Launcher` | **`open_url`**, **`open_new_terminal`** |
| `adapters/likec4.py` | 3 | `diagrams` · `DiagramEngine` | **`arch_dir`**, **`arch_validate`**, **`arch_start`**, `C4_VIEW_RE`, `C4_TITLE_RE`, **`c4_views`** |
| `adapters/fs_links.py` | 4 | `links` · `FileLinks` | **`LINKS`**, `LOCAL_ONLY`, **`KIT_IMPORT`**, `_append_lines`, `git_exclude`, **`_is_link`**, **`_linked`**, **`_unlink`**, **`link`**, `_points_at`, `_inside`, **`workspace_off`**, `_raw`, **`_merge`**, **`drop_kit_import`**, **`merged_links`**, **`link_repo_wiki`** |
| `adapters/agent_config.py` | 5 | `agent_config` · `AgentConfig` | **`camarones_mcp`**, **`likec4_mcp`**, `CODEX_MCP_START`, `CODEX_MCP_END`, **`CODEX_MCP_RE`**, **`codex_block`**, **`GRAPHIFY_SECTION`**, **`without_graphify_hooks`**, `claude_config`, **`repo_mcp_entry`**, **`repo_mcp_registered`**, **`wire_repo_mcp`**, **`unwire_repo_mcp`** |
| `adapters/prereqs.py` | 6 | `toolchain` · `Toolchain` | **`node_major`**, **`install_prereq`**, **`tool_version`**, **`npm_global`**, `npm_global_version`, **`openwiki_installed`**, **`tool_ok`** |
| `adapters/graphify.py` | 7 | `code` · `CodeIndexer` | **`repo_graph`**, **`graph_repo`** |
| `adapters/openwiki.py` | 8 | `wiki_engine` · `WikiEngine` | `PROVIDER_KEYS`, **`openwiki_credentials`**, **`openwiki_wired`**, **`OPENWIKI_INSTALL`**, `OPENWIKI_REPO_FILES`, **`wiki_open`**, **`wiki_close`**, **`wiki_workdir`**, **`wiki_lock`** |
| `core/paths.py` | 8 | — | `WIKI_STAMP`, `WIKI_LOCK` |
| `adapters/docker.py` | 9 | `containers` · `ContainerRuntime` | **`docker_ready`**, **`image_context`** |
| `adapters/git/checkpoint.py` | 10 | `vcs` · `Vcs` | `CHECKPOINT_PATHS`, **`checkpoint_paths`** |
| `app/components.py` | 11 | `components` | `KIT_TOOLS`, `EXTRAS`, `ALL_COMPONENTS`, `components`, `set_profile`, `set_components` |
| `app/templates.py` | 12 | `templates` | `TEMPLATES`, `KIT_DOCS`, `KIT_DOCS_STAMP`, `_real`, `_own_file`, `fill`, `kit_skill_files`, `skill_files`, `RENDERED_SKILLS`, `_real_skills_dir`, `_rendered_entry`, `write_kit_skills`, `init_templates`, `ensure_agents_import`, `_kit_doc_files`, `_sha`, `edited_kit_docs`, `sync_kit_docs`, `refresh_block` |
| `app/viewers.py` | 13 | `viewers` | `VIEWERS`, `build_c4`, `code_graphs`, `build_graphs`, `graph`, `newest`, `repo_changed_at`, `viewers` |
| `app/setup.py` | 14 | `setup` | `JVM_MARKERS`, `jvm_repos`, `java_info`, `prerequisites`, `install_tools`, `POINTER_START`, `POINTER_END`, `write_codex_mcp`, `install_graphify_skill`, `write_agent_config`, `refresh_agent_config`, `wire_repo`, `add_repo_pointer`, `wire_one`, `wire_umbrella`, `setup_steps`, `setup`, `link_workspace`, `unlink_agent_config` |
| `app/share.py` | 15 | `share` | `AUTO_SHARE`, `SHARED`, `_sharing`, `auto_share`, `set_auto_share`, `sync_status`, `docs_remote`, `set_remote`, `_remote_host`, `_git_said`, `_ident`, `share`, `_shared`, `_stderr`, `board_repair`, `checkpoint_commit` |
| `app/wiki.py` | 16 | `wiki` | `ENGINE_HELP`, `wiki_engines`, `wire_openwiki`, `wiki_engine_help`, `wiki_pages`, `WIKI_LINK_RE`, `wiki_nav`, `WIKI_SCOPE`, `wiki_scope`, `stamp_wiki`, `wiki_old`, `old_wikis`, `STARTER_MARK`, `COVERAGE`, `starter_brief`, `wiki_brief_kind`, `wiki_brief_ready`, `wikis`, `wiki_prompt`, `WikiAbort`, `ENGINE_DOWN`, `_WikiRun`, `openwiki_generate`, `wiki_graph` |
| `core/process.py` | 16 | — | `stream` |
| `app/portal.py` | 17 | `portal` | `SERVE_PID`, `serve_local`, `serve_editor`, `portal_url`, `portal_token`, `stop_local`, `project_id`, `compose_cmd`, `docker_up`, `docker_down` |
| `app/export_site.py` | 18 | `export_site` | `forge_edit_base`, `export_site`, `portal` (the alias), `portal_steps`, `writable` |
| `ci.py` | 19 | — | `detect_forge`, `install_ci` |

`services.current().portal` is the module `app/portal.py`, and `services.current().export_site.portal` is env's old
`portal` alias of `export_site`.

## Allowlist and cycle ledger

These are the expected numbers, from a simulation of the import graph after each task (archscan's edges, env's
per-function imports, every caller retargeted per P4). `tests/test_architecture.py` is the authority: set the records
to what it measures, and if a record would grow, a caller imported a new module directly (P4). Today: 130 violations,
`largest_cycle` 52, `cycle_modules` 54.

| Task | Violations | Allowlist lines | `largest_cycle` · `cycle_modules` |
|---|---|---|---|
| 1–2 | 130 → 130 | — | 52 · 54 |
| 3 likec4 | 130 → 130 | — | 51 · 53 (`c4edit` leaves the cycle) |
| 4–5 | 130 → 130 | — | 51 · 53 |
| 6 prereqs | 130 → 130 | — | 50 · 52 (`desktop` leaves) |
| 7 | 130 → 130 | — | 50 · 52 |
| 8 openwiki | 130 → **129** | − `harness.ledger -> env` (WIKI_STAMP from `core.paths`) | 50 · 52 |
| 9–13 | 129 → 129 | — | 50 · 52 |
| 14 setup | 129 → 129 | `env -> binaries` → `app.setup -> binaries`; `machine -> env` → `machine -> app.services` | 50 · 52 |
| 15 share | 129 → 129 | `env -> creds` → `app.share -> creds`; `env -> kanban` → `app.share -> kanban` | 50 · 52 |
| 16 wiki | 129 → 129 | `env -> adapters.runners`, `env -> harness.events`, `env -> quickarch`, `env -> radar` → `app.wiki -> …` (same four) | 50 · 52 |
| 17 | 129 → 129 | — | 50 · 52 |
| 18 export_site | 129 → 129 | `env -> codemap` → `app.export_site -> codemap` | 44 · 48 (`app.portal_views`, `adr`, `adr_doc`, `adr_pack`, `history`, `sourcelinks` leave) |
| 19 ci | 129 → 129 | — | 43 · 47 (env's last cycle ties go) |
| 20 facade | 129 → 129 | `oversize` drops `env` | 43 · 47 |

The renamed lines point at adapters that have no port yet (`binaries`, `creds`, `kanban`, `codemap`, `quickarch`,
`radar`, `harness.events`, `adapters.runners`: §3 moves them in F5 and F7). `machine` is an adapter that reads
`setup_steps`.

## CI baseline: `main` is red

CI run 43473600368 (`c28457b`, the F3 push) failed in three places:
- `pytest (windows-latest)`: `tests/test_githooks.py::test_commit_drops_claude_trailer_and_generated_line`
  (already red in runs 43418183911 and 43412049123, before F3)
- `pytest (macos-latest)`: `tests/test_yamlio.py::test_without_libyaml_it_reads_with_pure_python`
  (`AttributeError: CSafeLoader`; red before F3 too)
- `portal` `npm test`: `src/modes.test.js` fails on `.camarones/portal/app/src/api.js`. F3's comment there
  ("routes declared Access.APP…", commit 715c080) matches the test's forbidden `\bAPP\b`.

So F4 cannot meet §6's "green on macOS, Windows and Linux" literally until these are fixed. Until then, a task counts
as green when CI shows no failure outside this list; locally on Windows, the suite shows no failure outside the known
five (four likec4 tests without the binary, plus `test_githooks`). The `api.js` comment is F3's and is a one-line fix.
It should land on `main` before Task 1, but as its own change, not inside F4.

## Global Constraints

- macOS, Windows and Linux: `pathlib` only, `encoding="utf-8"` on every read and write, processes through
  `lib/core/process.py`, `IS_WIN`/`IS_MAC` instead of `sys.platform` (AGENTS.md §2.1).
- No new dependency of any kind.
- Nothing a user notices: `tests/snapshots/cli.json` and `tests/snapshots/routes.json` stay byte-identical, and so do
  outputs, exit codes, files written and their contents. Code moves verbatim, with only P10's edits.
- `tests/architecture/allowlist.yaml`: the number of `violations` never grows; lines are renamed as the ledger says.
  `largest_cycle` and `cycle_modules` are only ever lowered, to what the test measures. Each commit body states the
  violation count before → after and the two cycle records.
- P4's access rule, without exceptions beyond the ones it lists.
- Facades: explicit imports (never `import *`), `__facade__`, and `__all__` listing every imported name. No module reads
  a facade's re-export at call time.
- env.py is split, not moved: it stays at its path as the facade, so no `git mv`. Each commit body names the env.py
  line ranges it moves (at `c28457b`: templates 23–221, prerequisites 224–301, pinned tools 304–347, components
  350–429, wiring 432–858, code graph 861–898, C4 901–916, viewers 919–1022, OpenWiki 1025–1480, export 1483–1609,
  Docker and portal 1612–1760, CI 1763–1798, checkpoints 1801–1867, share 1870–2022), so `git log -L` can follow
  them. No module name differs from another in its package only by case.
- No `VERSIONS["kit"]` bump. Conventional commits (`refactor(env): …`, `test(env): …`), and every body ends with
  "Nothing a user notices." (AGENTS.md §5.1). No `Co-Authored-By` or "Generated with" line: this repo's `.githooks`
  are not installed in worktrees, so write messages without them. Stage only this plan's files, because other
  sessions edit the tree in parallel.
- `uv run pytest -n auto` from the repository root is green (see the CI baseline) before every commit. On this Windows
  machine the suite takes ~4.5 minutes, so run it in the background. Run Python only through `uv run` from the worktree:
  Windows App Control blocks executables created under `%TEMP%`.
- If `main` changes `lib/env.py`, or a branch calls a moved `env.X`, port the change into its new home on rebase.
- Code and comments in English, comments only for a non-obvious *why*.

## Review Focus

- **A process that runs kit code without services.** `camarones.py` runs (the server's handler threads, `camaron mcp`,
  hooks, `board merge-driver`) go through `main()`; a unit's gates run through `harness.integrate._kit`. A missing build
  would turn any env call into `RuntimeError` → Task 1's `test_the_cli_entry_builds_the_services`,
  `test_kit_code_run_in_another_tree_has_services` and `test_a_request_carries_the_processs_services`.
- **Windows junctions in fs_links** (§8). `_linked` must still see a junction made by `mklink /J`, and `_unlink` must
  still remove it without following it → Task 4's `test_a_junction_is_linked_and_unlinked_without_following_it`,
  plus the whole suite on this Windows machine and the `pytest (windows-latest)` job before merge.
- **Old import paths after F4.** `from lib.env import init_templates` and `lib.env.WikiAbort` must be the very objects
  their homes define → Task 20's `test_the_facade_re_exports_every_env_name` (identity, every name).
- **A stale patch through env mid-phase.** Env is no facade until Task 20, so the guard cannot refuse
  `monkeypatch.setattr(kit.env, "<moved>", …)`, and such a test passes while patching nothing →
  `test_no_test_reaches_a_moved_name_through_env` (Task 1, kept green by every task).
- **Auto-share re-entering itself.** `share()` sets `_sharing` around its own checkpoint, and `checkpoint_commit` must
  read that same module global, or every share would push twice → Task 15's
  `test_share_does_not_auto_share_from_its_own_checkpoint`.

## File map (end state)

```
.camarones/lib/bootstrap.py              PROVIDERS, build(**overrides) -> Services: the composition root
.camarones/lib/app/services.py           Services, install(), current()
.camarones/lib/ports/__init__.py         Log
.camarones/lib/ports/                    launcher, diagram_engine, file_links, agent_config, toolchain, code_indexer,
                                         wiki_engine, container_runtime, vcs   (one Protocol each)
.camarones/lib/adapters/system/          __init__.py (docstring), os_open.py
.camarones/lib/adapters/                 likec4.py, fs_links.py, agent_config.py, prereqs.py, graphify.py, openwiki.py,
                                         docker.py
.camarones/lib/adapters/git/             __init__.py (docstring), checkpoint.py
.camarones/lib/app/                      components.py, templates.py, viewers.py, setup.py, share.py, wiki.py,
                                         portal.py, export_site.py
.camarones/lib/ci.py                     + detect_forge, install_ci
.camarones/lib/core/paths.py             + WIKI_STAMP, WIKI_LOCK
.camarones/lib/core/process.py           + stream
.camarones/lib/env.py                    facade (layer `facade`)
tests/test_services.py, tests/test_env_split.py
```

---

### Task 1: Ports, services and the composition root; the split's tests

**Files:**
- Create: `.camarones/lib/ports/__init__.py`, `.camarones/lib/app/services.py`, `.camarones/lib/bootstrap.py`,
  `tests/test_services.py`, `tests/test_env_split.py`
- Modify: `.camarones/lib/interfaces/cli/registry.py`, `.camarones/lib/interfaces/cli/main.py`,
  `.camarones/lib/interfaces/http/messages.py`, `.camarones/lib/interfaces/http/server.py`,
  `.camarones/lib/harness/integrate.py` (`_kit`'s preamble), `.camarones/lib/env.py`
  (`Log` from `lib.ports`), `.camarones/lib/uninstall.py`, `.camarones/lib/mcp.py`, `.camarones/lib/docs.py`,
  `.camarones/lib/onboard.py`, `.camarones/lib/reset.py`, `.camarones/lib/install_state.py`,
  `.camarones/lib/interfaces/http/routes/analysis.py`, `tests/conftest.py`, `tests/fixtures/archscan.py`,
  `tests/test_architecture.py`, and the tests that read env's imported names

**Interfaces:**
- Produces:
  - `lib/ports/__init__.py`: a docstring ("what the app needs from the outside world, as typing.Protocol: one module per
    port; an adapter module satisfies it") and `Log = Callable[[str], None]`.
  - `lib/app/services.py`: `class Services` with `__init__(self, providers: Mapping[str, Callable[[], object]])`,
    `__getattr__(self, name: str) -> object` (a declared field: its provider's result, cached; anything else:
    `AttributeError`), and `__setattr__` raising `AttributeError`. No field annotations yet: each later task adds one.
    Plus the module global `_current: Services | None = None`, `install(s: Services) -> Services` (sets it) and
    `current() -> Services` (P3's message when it is None).
  - `lib/bootstrap.py`: `PROVIDERS: dict[str, Callable[[], object]]` (`{}` for now; each later task adds a function
    `_<field>()` that imports its module inside and returns it), and `build(**overrides) -> Services`. `build` raises
    `TypeError("unknown service: <name>")` for an override that is not a declared field, and
    `RuntimeError("no provider for <field>")` for a declared field missing from `PROVIDERS`; it wraps each override as
    a provider returning it, installs, returns.
  - `CliContext.services` and `Request.services` (P14); `main._parse_and_run` passes `bootstrap.build()`'s result;
    `server.Handler.answer` passes `services.current()`.
  - `harness.integrate._kit`: its code preamble gains `from lib import bootstrap` and `bootstrap.build()`, after the
    `sys.path` line (a string, run in the child process).
  - `kit.services` in the test namespace (`load_kit` calls `bootstrap.build()` after importing `MODULES`).
  - `archscan.ALLOWED["facade"]` (every layer); no layer lists `facade`.
  - `tests/test_env_split.py`: `ENV_NAMES: frozenset[str]` (the 173 names env.py defines at this commit: top-level
    `def`, `class` and assignment targets; generated once with `ast`, pasted as a literal),
    `REEXPORTS = {"pid_alive", "git_failure"}`, `HOME: dict[str, str]` (the Name map; values are dotted modules under
    `lib`, `ci` for `lib/ci.py`), `MOVED: set[str] = {"ports"}`, `NEW: set[str]` (the Name map's `adapters.*` and
    `app.*` homes).

- [ ] **Step 1: Write the failing tests.**
  - `tests/test_services.py`:
    - `test_current_before_a_build_says_how_to_get_one`: with `kit`, `monkeypatch.setattr(svc, "_current", None)`
      (`svc = importlib.import_module("lib.app.services")`); `pytest.raises(RuntimeError, match="lib.bootstrap.build")`.
    - `test_build_installs_what_it_returns`: `s = kit.bootstrap.build()` (add `"bootstrap"` to conftest's `MODULES`);
      `svc.current() is s`.
    - `test_the_cli_entry_builds_the_services`: reset `_current` to None; `main(["version"])` returns 0; `svc.current()`
      is a `Services`.
    - `test_a_command_that_needs_no_env_code_imports_none`: `purge_kit_modules()`, then
      `import_module("lib.interfaces.cli.main").main(["version"])`; no module of `NEW` (`lib.<name>` for each name in
      `tests/test_env_split.py`'s `NEW`) is in `sys.modules`. Every later task's modules are covered, because `NEW`
      lists them all from the start.
    - `test_kit_code_run_in_another_tree_has_services`: with `kit`,
      `harness.integrate._kit(kit_ctx, "from lib.app import services\nprint(json.dumps(type(services.current()).__name__))")`
      prints `"Services"` (`kit_ctx` is `lib.core.paths.CTX`).
    - `test_build_refuses_an_unknown_service`: `pytest.raises(TypeError, match="unknown service: nope")` from
      `kit.bootstrap.build(nope=object())`.
    - `test_a_command_gets_the_services`: patch `lib.interfaces.cli.middleware.dispatch` to capture its `Invocation`;
      `main(["version"])`; `inv.cli.services is svc.current()`.
    - `test_a_request_carries_the_processs_services`: as `tests/test_http_server.py` does (patch
      `lib.interfaces.http.router.load` with a declared GET `/api/zz` returning
      `json_response({"same": req.services is svc.current()})`, served through `http_probe`) → `{"same": true}`.
  - `tests/test_env_split.py`:
    - `test_every_env_name_has_one_home`: `set(HOME) == ENV_NAMES`.
    - `test_moved_names_live_in_their_home`: for each name whose home is in `MOVED`,
      `hasattr(import_module(f"lib.{home}"), name)`. If the home is under `adapters` or `app`, or is `ci`, then also
      `name not in vars(import_module("lib.env"))`. For a `ports` or `core.*` home, env may import the name for its
      remaining code, and then it is the same object. Task 20 turns the env check into identity.
    - `test_moved_code_is_reached_through_services`: from `archscan.edges(archscan.modules(KIT_DIR))`, no edge
      `(a, b)` with `b in NEW` unless `a in NEW`, or `a == "bootstrap"`, or `a == "env"` once `lib.env` has
      `__facade__` (Task 20). An app module of `NEW` importing an adapter of `NEW` already fails the layer test.
    - `test_no_test_reaches_a_moved_name_through_env`: over `tests/**/*.py` text, matches of
      `(?<![\w.])(?:kit\.)?(?:\w+\.)?env\.([A-Za-z_]\w*)` and `lib\.env\.([A-Za-z_]\w*)` whose name is in `HOME` and
      whose home is in `MOVED` → `[]` (file:line in the message).
    - `test_only_the_cli_entry_imports_bootstrap`: the only kit module with an edge to `bootstrap` is
      `interfaces.cli.main` (`_kit`'s preamble is a string, run in a child process); the only call to `install(`
      outside `app/services.py` is in `bootstrap.py` (`ast`).
  - `tests/test_architecture.py`: `test_a_facade_layer_module_imports_anything_and_nothing_imports_it`:
    `archscan.violations({("f", "a"), ("f", "x"), ("x", "f")}, {"f": "facade", "a": "adapters", "x": "app"}) == {("x", "f")}`.

- [ ] **Step 2: Run to verify they fail.**
  Run: `uv run pytest tests/test_services.py tests/test_env_split.py tests/test_architecture.py -v`
  Expected: FAIL (`ModuleNotFoundError: lib.app.services`, `lib.bootstrap`; `KeyError: 'facade'`).

- [ ] **Step 3: Implement** the Produces list. `messages.py` and `registry.py` import `Services` only under
  `TYPE_CHECKING`. `env.py` replaces its `Log = Callable[[str], None]` with `from .ports import Log`. Then retarget the
  reads of names env only imports, which no later task moves: `uninstall.py`'s `Log = env.Log` → `from .ports import
  Log`; `mcp.py` `env.CACHE` → `core.paths`; `docs.py` `env.cli_cmd` → `core.paths`; `onboard.py` `env.VERSIONS` →
  `lib.common`; `reset.py` and `uninstall.py` `env.pid_alive` → `core.locks`; `install_state.py` `env.run`, `env.which`
  → its own `run`, `which` imported from `core.process` (`env.components` stays until Task 11);
  `routes/analysis.py` `env.which` → `which` from `core.process`. Tests that read `env.KIT`, `env.GRAPHS`, `env.Path`,
  `env.VERSIONS`, `env.git_failure`, `env.load_json`, `env.save_json` read the defining module; tests that patch
  `env.run` or `env.which` to steer `install_state` or the analysis routes patch `lib.install_state` and
  `lib.interfaces.http.routes.analysis`. Patches of `env.run`, `env.which`, `env.IS_WIN` or `env.cli_cmd` that steer
  env's own functions stay until those functions move.

- [ ] **Step 4: Run to verify they pass.**
  Run: `uv run pytest tests/test_services.py tests/test_env_split.py tests/test_architecture.py tests/test_cli_registry.py tests/test_http_server.py tests/test_cli_snapshot.py tests/test_routes_snapshot.py -n auto`
  Expected: PASS; violations 130 → 130; records 52 · 54.

- [ ] **Step 5: Full suite and commit.** `uv run pytest -n auto`, then stage the files above and commit
  `feat(app): ports, the services holder and bootstrap for env's split; nothing moves yet`. In the body: what
  `Services` is for, the violation count and records, and "Nothing a user notices."

---

### Adapter move procedure (Tasks 2–10)

Each adapter task applies these steps to its row of the Adapters table. In what follows, `A` is the adapter module,
`P` its port module and Protocol, and `f` the Services field.

- [ ] **Step 1: Tests first.** Add `A`'s home (and any `core.paths` home of the row) to `MOVED` in
  `tests/test_env_split.py`. Task 2 writes `tests/test_services.py::test_each_adapter_provides_its_port`, which covers
  every later port by itself: for every annotation of `Services` whose type (from `typing.get_type_hints`) is a
  Protocol, the module `bootstrap.build()` resolves there has every member of the Protocol (functions defined in its
  body, annotated attributes). For a function, `inspect.signature` gives the same parameter names, kinds and
  has-a-default as the Protocol's method without `self`. Run `uv run pytest tests/test_env_split.py tests/test_services.py -v`.
  Expected: FAIL (the names are still in env).
- [ ] **Step 2: Port.** Create `lib/ports/P.py`: a docstring naming the external tool and what the app asks of it, and
  `class P(Protocol)` with the row's members (P1), annotated with `Log` from `lib.ports`.
- [ ] **Step 3: Move.** Create `A` with the row's names, verbatim and in env's order (P10), with the imports their
  bodies use. Delete them from env.py. Annotate `f: P` on `Services`; in `bootstrap.py`, add `def _f():` (imports `A`
  inside, returns it) and `"f": _f` to `PROVIDERS`.
- [ ] **Step 4: Retarget callers.** Every caller in the row's "Callers" column, env's remaining code included, now
  calls `services.current().f.<name>` (commands: `cli.services.f.<name>`; routes: `req.services.f.<name>`). A caller
  that imported env only for these names drops that import. Comments and docstrings that name `env.<name>` name `A`.
- [ ] **Step 5: Retarget tests** (P11): the row's tests, then
  `uv run pytest tests/test_env_split.py::test_no_test_reaches_a_moved_name_through_env` to find what is left. A test
  that builds a `Request` or a `CliContext` by hand passes `services=kit.services`. A test that runs kit code in a
  child process of its own builds services first (`from lib import bootstrap; bootstrap.build()`), as `_kit` does.
- [ ] **Step 6: Run.**
  `uv run pytest tests/test_env_split.py tests/test_services.py tests/test_architecture.py tests/test_cli_snapshot.py tests/test_routes_snapshot.py <row tests> -n auto`.
  Expected: PASS, with the ledger's numbers (lower `largest_cycle` and `cycle_modules` to what the test reports). If the
  sandbox exists (AGENTS.md §2.2; `reset` creates it, and if you do that, say so), run the row's sandbox command:
  `uv run scripts/sandbox.py cli <command>`. Its output must match `main`'s.
- [ ] **Step 7: Full suite and commit.** `uv run pytest -n auto`. Stage `A`, `P`, `env.py`, `services.py`,
  `bootstrap.py`, the retargeted modules and tests, and the allowlist, then commit
  `refactor(env): <adapter> moves to adapters/<path> behind ports/<port>.py`. The body lists the moved names and env.py
  line ranges, the violation count and records before → after, and ends with "Nothing a user notices."

| Task | Adapter (`A` · `P` · `f`) | Port members (`P`) | Callers to retarget | Tests to run and retarget · sandbox |
|---|---|---|---|---|
| 2 | `adapters/system/os_open.py` (+ `adapters/system/__init__.py`, docstring) · `launcher.Launcher` · `launcher` | `open_url(url: str) -> None`; `open_new_terminal(cmd: list[str], cwd: Path) -> bool` | `wizard` (`open_url` ×4, `open_new_terminal` ×2), `agents`, `kitdev` | `test_launch_argv` (`kit.wizard.env` → `kit.services.launcher`), `grep -rln "open_url\|open_new_terminal" tests`. Also write `test_an_override_replaces_one_port`: `kit.bootstrap.build(launcher=fake)`; `svc.current().launcher is fake`; the other fields keep their defaults · none (it opens windows) |
| 3 | `adapters/likec4.py` · `diagram_engine.DiagramEngine` · `diagrams` | `arch_dir() -> Path`; `arch_validate() -> tuple[bool, str]`; `arch_start() -> None`; `c4_views() -> list[dict]` | `c4edit`, `commands/check`, `commands/machine`, `app/portal_views`; `harness/integrate.py`'s `GATE_SCRIPT["arch-validate"]` (a code string: `from lib.app import services` and `services.current().diagrams.arch_validate()`); env: `setup`, `build_c4`, `viewers`, `portal_steps`, `export_site` | `test_c4_edit`, `test_c4_fragments`, `test_portal_data`, `test_integrate` (the gate) (the likec4-binary tests stay failing for that reason only) · `cli arch-validate` |
| 4 | `adapters/fs_links.py` · `file_links.FileLinks` · `links` | `LINKS: tuple[str, ...]`; `KIT_IMPORT: str`; `_is_link(p: Path) -> bool`; `_linked(p: Path) -> bool`; `_unlink(p: Path) -> None`; `link(dst: Path, target: Path, log: Log = ...) -> bool`; `workspace_off(n: str) -> str \| None`; `_merge(n: str, log: Log) -> bool`; `drop_kit_import(claude_md: Path) -> bool`; `merged_links(names: tuple[str, ...] = ...) -> list[Path]`; `link_repo_wiki(name: str, log: Log = ...) -> None` | `exporters`, `harness.ab`, `install_state`, `migrate`, `uninstall`; env: `write_kit_skills`, `link_workspace`, `unlink_agent_config`, `wire_repo`, `wiki_open`, `wiki_close`, `openwiki_generate`; `tests/conftest.py` (`wire_project`, `copy_wired`) | Before Step 1, add `test_a_junction_is_linked_and_unlinked_without_following_it` to `test_wiring` against `kit.env` (Windows only, `skipif(not IS_WIN)`): make a junction `p` to a folder `t` holding `keep.txt` with `cmd /c mklink /J`; `_linked(p)` and `_is_link(p)` are true; after `_unlink(p)`, `p` is gone and `t/keep.txt` is still there. It passes today on this machine, and Step 5 retargets it. Then `test_wiring`, `test_uninstall`, `test_install_state`, `test_agent_trust`, `test_plan_wiki` (`_is_link`), and `test_exporters` if it links. The whole suite runs on this Windows machine, and the `pytest (windows-latest)` job must show no new failure before merge (§8) · `cli doctor`, then `uv run scripts/sandbox.py uninstall`, `traces` (exit 0), `reset` |
| 5 | `adapters/agent_config.py` · `agent_config.AgentConfig` · `agent_config` | `CODEX_MCP_RE: re.Pattern[str]`; `GRAPHIFY_SECTION: re.Pattern[str]`; `camarones_mcp() -> dict`; `likec4_mcp() -> dict`; `codex_block(servers: dict) -> str`; `without_graphify_hooks(data: dict) -> dict`; `repo_mcp_entry(name: str) -> dict \| None`; `repo_mcp_registered(name: str) -> bool`; `wire_repo_mcp(name: str, log: Log = ...) -> bool`; `unwire_repo_mcp(name: str) -> bool` | `trust`, `install_state`, `uninstall`, `migrate`; env: `write_codex_mcp`, `write_agent_config`, `wire_repo` | `test_repo_mcp` (its `env.which`/`env.run` patches → `kit.services.agent_config`), `test_wiring`, `test_agent_config_links` (`CODEX_MCP_START` from the module), `test_agent_trust` · `cli trust` |
| 6 | `adapters/prereqs.py` · `toolchain.Toolchain` · `toolchain` | `node_major() -> int`; `install_prereq(name: str, log: Log = ...) -> bool`; `tool_version(name: str) -> str`; `npm_global(pkg: str, log: Log) -> None`; `openwiki_installed() -> bool`; `tool_ok(name: str) -> bool` | `desktop` (its module-level `from .env import node_major` becomes the call site's `services.current().toolchain.node_major()`), `doctor`, `onboard`, `commands/check`, `wizard`; env: `prerequisites`, `install_tools`, `wiki_engines`, `wiki_engine_help` (`env -> binaries` stays: `install_tools`) | `test_wiki_from_portal`, `test_doctor*`, `test_onboard`, `test_onboard_api`, `test_check*` (`grep -rln "install_prereq\|tool_ok\|tool_version\|openwiki_installed\|node_major" tests`) · `cli doctor` |
| 7 | `adapters/graphify.py` · `code_indexer.CodeIndexer` · `code` | `repo_graph(name: str) -> Path`; `graph_repo(name: str) -> bool` | `mcp`, `wizard`; env: `wire_repo`, `graph`, `build_graphs` | `grep -rln "repo_graph\|graph_repo" tests` · `cli graph` |
| 8 | `adapters/openwiki.py` · `wiki_engine.WikiEngine` · `wiki_engine`; `WIKI_STAMP`, `WIKI_LOCK` → `core/paths.py` | `OPENWIKI_INSTALL: list[list[str]]`; `openwiki_credentials() -> bool`; `openwiki_wired(host: str) -> bool`; `wiki_open(repo: str, log: Log = ...) -> None`; `wiki_close(repo: str, log: Log = ...) -> bool`; `wiki_workdir(repo: str, log: Log = ...) -> AbstractContextManager[None]`; `wiki_lock(repo: str) -> AbstractContextManager[None]` | `commands/generate`, `uninstall`, `reset`, `install_state`, `harness.ledger` (`WIKI_STAMP` from `core.paths`: pays its line); env: `wiki_engines`, `wire_openwiki`, `wire_umbrella`, `openwiki_generate`, `wiki_scope`, `stamp_wiki`. `A` imports `_is_link` and `link_repo_wiki` from `adapters.fs_links` | `test_plan_wiki`, `test_locks`, `test_uninstall`, `test_wiki_from_portal`, `test_ledger` · `cli status` |
| 9 | `adapters/docker.py` · `container_runtime.ContainerRuntime` · `containers` | `docker_ready() -> tuple[bool, str]`; `image_context() -> Path` | `wizard`; env: `docker_up`, `export_site` | `grep -rln "docker_ready\|image_context" tests` · `cli portal` (builds the image context; Docker not needed) |
| 10 | `adapters/git/checkpoint.py` (+ `adapters/git/__init__.py`, docstring) · `vcs.Vcs` · `vcs` | `checkpoint_paths() -> list[str]` | env: `checkpoint_commit`, `sync_status` | `test_evals`, `test_plugin_versions`, `test_structure` (`CHECKPOINT_PATHS` from `kit.services.vcs`) · `cli checkpoint "f4 sandbox"` |

---

### App move procedure (Tasks 11–19)

The same seven steps as the adapter procedure, with these differences:
- No port. In Step 1, the row's home goes into `MOVED`, and Step 2 is skipped.
- In Step 3, `Services` gains the annotation `f: ModuleType` and `PROVIDERS` gains `"f": _f`. Task 19 adds no field,
  because its home is `lib/ci.py`: callers import it directly.
- In the new module, a call to an adapter name goes through `services.current()`, and a call to a name of an earlier
  app task goes through a direct import of that module (P4).
- Commit `refactor(env): <family> moves to app/<module>.py`.

| Task | Home · `f` | Callers to retarget | Allowlist | Tests to run and retarget · sandbox |
|---|---|---|---|---|
| 11 | `app/components.py` · `components` | `hooks`, `install_state` (`env.components` ×3), `routes/onboard`, `migrate`, `onboard`, `commands/machine` (`set_profile`); env: `install_tools`, `refresh_agent_config`, `wire_repo`, `wire_umbrella`, `setup_steps`, `setup`, `build_graphs`, `viewers`, `wiki_engines`, `wiki_engine_help`, `export_site` | — | `test_onboard` (`ALL_COMPONENTS`, `KIT_TOOLS`/`EXTRAS` patches), `test_plan_wiki`, `test_portal_data` (`set_components`), `test_diagrams` (`set_profile`), `test_onboard_api` · `cli status` |
| 12 | `app/templates.py` · `templates` | `guide`, `reset`, `plan` (`sync_kit_docs`), `trust` (`kit_skill_files`), `install_state` (`skill_files`), `onboard`, `commands/machine`, `commands/projects` (`init_templates`); env: `refresh_agent_config`, `wire_umbrella`, `write_agent_config`, `write_codex_mcp` (`_real`, `_own_file`); `tests/conftest.py::wire_project`. `write_kit_skills` calls `services.current().links._unlink` | — | the `init_templates` tests (`test_agent_config_links`, `test_agent_trust`, `test_coding_workflow_skills`, `test_guide`, `test_kanban_ops`, `test_structure`, `test_sync`, `test_team_repo`, `test_usage`, `test_wiring`, `test_workspace_keys`), `test_team_skills` (`write_kit_skills`, `RENDERED_SKILLS`, `skill_files`), `test_questionnaire` (`KIT_DOCS_STAMP`), `test_agent_guidance` · `cli docs reset --templates` is destructive: run `cli status` and `cli check` |
| 13 | `app/viewers.py` · `viewers` | `routes/analysis` (`build_c4`, `build_graphs`, `viewers`), `routes/files` (`VIEWERS`, `code_graphs`), `app/portal_views` (`code_graphs`), `commands/analyze` (`graph`); env: `setup`, `wikis`, `wiki_graph`, `export_site` | — | `test_portal_smoke`, `test_c4_fragments`, `test_http_contract`, `test_portal_data` (`VIEWERS`, `build_c4`, `graph`, `repo_changed_at` patches) · `cli graph` |
| 14 | `app/setup.py` · `setup` | `doctor`, `onboard`, `commands/check`, `commands/machine`, `commands/skills`, `commands/team`, `wizard`, `machine` (`setup_steps`), `hooks` (`write_agent_config`), `install_state`, `migrate` (`wire_umbrella`), `trust` (`unlink_agent_config`), `uninstall` (`POINTER_*`: its module-level `POINTER_RE` becomes `_pointer_re()`, built at its one use from `services.current().setup`, because module import runs before any build); `tests/conftest.py` (`write_agent_config`, `link_workspace`, `add_repo_pointer`) | `env -> binaries` → `app.setup -> binaries`; `machine -> env` → `machine -> app.services` | `test_wizard` (`setup` patches), `test_workspace_keys`, `test_wiring`, `test_agent_trust`, `test_agent_config_links`, `test_uninstall`, `test_install_state`, `test_onboard`, `test_onboard_api`, `test_machine` · `cli doctor`, `cli trust` |
| 15 | `app/share.py` · `share` | `harness.scheduler`, `commands/generate`, `commands/team`, `routes/docs`, `routes/team`, `onboard`, `reset`, `wizard`; env: `openwiki_generate`; `tests/conftest.py::wire_project` (`checkpoint_commit`) | `env -> creds` → `app.share -> creds`; `env -> kanban` → `app.share -> kanban` | `test_team_repo`, `test_sync`, `test_kanban_repair`, `test_integrate`, `test_scheduler`, `test_usage`, `test_docs_reset`, `test_pr_propose`, `test_team_skills`. Before Step 1, add `test_share_does_not_auto_share_from_its_own_checkpoint` to `test_team_repo` against `kit.env`: a bare repo in `tmp_path` as origin, `set_auto_share(True)`, a pending page, and `share` wrapped in a counter with `monkeypatch.setattr`; one `share()` call counts 1. It passes today, and Step 5 retargets it to `kit.services.share` · `cli checkpoint "f4 sandbox"` |
| 16 | `app/wiki.py` · `wiki`; `stream` → `core/process.py` (`app/wiki.py` imports it by name, so tests patch `lib.app.wiki.stream`) | `commands/generate` (`except cli.services.wiki.WikiAbort`), `routes/analysis`, `wizard`, `app/portal_views` (`wiki_engines`, `wiki_engine_help`), `docs` (`old_wikis`); env: `export_site`, `portal_steps` | `env -> adapters.runners`, `env -> harness.events`, `env -> quickarch`, `env -> radar` → `app.wiki -> …` | `test_plan_wiki`, `test_wiki_from_portal`, `test_portal_data` (`wikis`, `wiki_nav`, `wiki_graph`), `test_launch_argv`, `test_diagrams` (`wiki_prompt`) · `cli wiki --help` and `cli status` |
| 17 | `app/portal.py` · `portal` | `commands/machine`, `wizard`, `uninstall` (`project_id`, `docker_down`) | — | `test_portal_kanban` (`portal_url`, `serve_editor`), the `docker_down` patches (`grep -rln docker_down tests`) · `cli up` → `/` answers 200 → `cli down` |
| 18 | `app/export_site.py` · `export_site` | `commands/machine`, `commands/team`, `wizard` (`portal`, `portal_steps`) | `env -> codemap` → `app.export_site -> codemap` | `test_portal_data` (`export_site`), `test_portal_smoke` · `cli portal` |
| 19 | `ci.py` (no field) | `wizard` (`detect_forge`, `install_ci`), `commands/team`, `routes/analysis` (`install_ci`); `ci.py`'s own `env.detect_forge` becomes a local call | — | `test_ci`, `test_ci_view` · `cli ci --help` |

---

### Task 20: `env.py` becomes a facade

**Files:**
- Modify: `.camarones/lib/env.py`, `tests/architecture/layers.yaml`, `tests/architecture/allowlist.yaml`,
  `tests/test_env_split.py`, `tests/conftest.py`, `AGENTS.md`

**Interfaces:**
- Consumes: every home of the Name map.
- Produces: `lib/env.py` = a docstring ("env's helpers moved to lib/adapters and lib/app; tests/test_env_split.py HOME
  names each home; this path stays for old imports"), explicit imports of every `HOME` name from its home plus
  `pid_alive` (`lib.core.locks`) and `git_failure` (`lib.projects`), `__facade__ = "lib.app and lib.adapters"`, and
  `__all__` listing them (P13).

- [ ] **Step 1: Tests first.** In `tests/test_env_split.py`, `MOVED` now holds every home.
  `test_moved_names_live_in_their_home`'s env check becomes `test_the_facade_re_exports_every_env_name`: for each name
  in `HOME`, `getattr(lib.env, n) is getattr(import_module(f"lib.{HOME[n]}"), n)`, and the same for `REEXPORTS`. Add
  `test_env_is_a_facade`: `lib.env.__facade__` is set, `set(lib.env.__all__) == set(HOME) | REEXPORTS`, and
  `archscan.layer_of("env", archscan.load_layers()) == "facade"`. Run
  `uv run pytest tests/test_env_split.py -v`. Expected: FAIL.
- [ ] **Step 2: The facade.** Write env.py as Produces says (`test_facades_hold_only_imports_and_literals` checks its
  shape). Set `env: facade` in `layers.yaml`. Remove `"env"` from conftest's `MODULES`, so that no test reaches the
  facade by accident (`test_env_split.py` imports it explicitly).
- [ ] **Step 3: Allowlist.** Run `uv run pytest tests/test_architecture.py`. `oversize` drops `env`; the violations are
  129; set `largest_cycle` and `cycle_modules` to what the test measures (ledger: 43 · 47).
- [ ] **Step 4: Docs.** In AGENTS.md §4, the `.camarones/lib/` row says `env` (facade of `adapters/` and `app/`); the
  `lib/adapters/` row adds likec4, openwiki, graphify, docker, agent_config, prereqs, fs_links, `system/os_open` and
  `git/checkpoint`, each in a few words. New rows: `.camarones/lib/ports/` ("what the app needs from the outside world,
  one `typing.Protocol` per adapter; an adapter module satisfies it"), `.camarones/lib/app/` ("use cases: components,
  templates, viewers, setup, share, wiki, portal, export_site, portal_views; `services` the process's adapters and use
  cases") and `.camarones/lib/bootstrap.py` ("the composition root: builds the services once per process, in
  `interfaces/cli/main.py`"). In AGENTS.md §5, after the facade line, add: "Code outside `lib/adapters` and `lib/app`
  reaches an adapter or a use case through `services` (`cli.services`, `req.services`,
  `lib.app.services.current()`), never by importing it; `tests/test_env_split.py` checks it." The guides name no env
  module (`grep -n "lib/env\|env\.py" .camarones/templates/docs/guides/*.md .camarones/templates/docs/i18n/es/guides/*.md`
  prints nothing): say so in the commit body.
- [ ] **Step 5: Run, then the sandbox.**
  `uv run pytest tests/test_env_split.py tests/test_services.py tests/test_architecture.py tests/test_cli_snapshot.py tests/test_routes_snapshot.py -n auto`,
  then `uv run pytest -n auto`. Expected: PASS. If the sandbox exists: `cli doctor`, `cli status`, `cli graph`,
  `cli portal`, `cli up` (with `/`, `/api/tree` and `/desktop/` answering as on `main`), `cli down`.
- [ ] **Step 6: Commit** `refactor(env): env.py is a facade over its adapters and use cases` (violations 129 → 129,
  the cycle records, "Nothing a user notices.").

---

### Task 21: The living docs of camaron-dev

**Files:** pages under `cam-docs/docs/` of the camaron-dev workspace (`C:/Users/aneri/projects/personal/camaron-dev/cam-docs`,
outside this repo) that name `lib/env.py` or `env.<function>`.

- [ ] **Step 1:** Follow the `cam-docs-update` skill. Run `grep -rln "env\.py\|lib/env\|env\.\(setup\|share\|openwiki_generate\|export_site\|checkpoint_commit\)" cam-docs/docs`.
  On a `draft` page, point to the new module. A `confirmed` page gets a `propose_edit`, never a direct rewrite.
- [ ] **Step 2:** Run `camaron check` from the workspace: no new error. Commit in `cam-docs` with
  `docs: the kit's env.py is split into adapters and use cases`.
