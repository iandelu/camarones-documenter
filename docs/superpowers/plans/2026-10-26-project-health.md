# Project Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Calidad into one project-health screen (machine, docs, code; per-repo Sonar, coverage, vulnerabilities and tech debt) shared by the desktop app and the portal, with a portal per-repo page and an optional SonarQube server read.

**Architecture:** `lib/health.py` gathers every fact without AI into one cached snapshot (`cam-docs/.cache/health.json`) and works out each area's state; `camaron health` and `GET /api/health` expose it; a shared `HealthBoard` in `.camarones/ui` draws it in the app (with actions) and in the portal (read-only). Step (c) adds a SonarQube read to the same snapshot.

**Tech Stack:** Python 3 stdlib (pathlib, xml.etree, urllib) + pytest; React 19 + Vite + Vitest (portal, desktop renderer, shared `ui`).

**Spec:** `docs/superpowers/specs/2026-10-26-project-health-design.md`

## Global Constraints

- macOS, Windows and Linux: `pathlib` only, `encoding="utf-8"` on every read/write, processes through `lib/common.py` helpers (AGENTS.md §2.1).
- TDD, offline and deterministic tests: `make_workspace` / `isolated_env` / the `kit`, `wired` fixtures; ports bound to 0 (AGENTS.md §2.2).
- No existing CLI command, flag, file, `workspace.yaml` key or frontmatter field renamed or dropped (§2.3). New only: `camaron health`, `GET /api/health`, `cam-docs/.cache/health.json`, optional `sonar.host`.
- No new dependency (stdlib HTTP and XML only); AGENTS.md §2.4 is not triggered.
- Every user-facing string in `es` and `en`; no jokes in states, errors or empty states; missing values render "—", never 0.
- Colours only from theme tokens (`--color-estado-bien|aviso|mal`, `--color-ink*`); `style.test.js` forbids raw colours.
- The portal never builds the snapshot and never runs a check; `GET /api/health` only reads.
- A Sonar token never on a command line, in a log, in the snapshot, in `--json`, or over plain http (http only for `localhost`/`127.0.0.1`).
- Thresholds: `VULN_SCAN_MAX_DAYS = 30`, `COVERAGE_MIN = 50`; Sonar reads time out at 10 s each.
- Kit version: 4.60.0 with step (a), 4.61.0 with step (c); README badge follows.
- User docs move with the code (AGENTS.md §5.1): README (Spanish), `lib/tutorial.py` + regenerated `TUTORIAL.md`, `templates/docs/guides/tutorial.md` and its `es` twin.
- Committed builds `portal/app-build/` and `desktop/renderer-build/` rebuilt and committed with their source.
- Commits: conventional (`feat(health): …`), stage only this plan's hunks (other sessions share the tree), end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

**Environment notes for this machine:** the repo needs `git -c safe.directory=* …` (owned by another Windows user); run pytest as `uv run python -m pytest -p no:cacheprovider` (the `pytest` trampoline fails); renderer tests `cd .camarones/desktop/renderer && npx vitest run`, portal and `ui` tests `cd .camarones/portal/app && npx vitest run`, desktop helpers `node --test test/core.test.cjs test/renderer.test.cjs` from `.camarones/desktop`.

## Review Focus

1. **A repo listed in `workspace.yaml` but not cloned** — its row shows "no clonado" with every figure "—"; `build()` does not fail. Test in Task 3.
2. **A huge or hostile coverage report** (DOCTYPE/ENTITY, 50 MB, truncated XML) — skipped with a per-report `error`, never parsed with entities, never read past 5 MB. Test in Task 1.
3. **`tech-debt.md` still the skeleton, or hand-edited with extra columns or Spanish headers** — placeholder rows skipped, extra columns ignored, headers matched case-insensitively in both languages. Test in Task 2.
4. **The snapshot file is corrupt or from a newer kit (`v` > 1)** — `load()` returns None and the app rebuilds; the portal shows "Aún no se ha comprobado". Test in Task 3.
5. **Sonar answers 200 with an HTML login page (SSO proxy) instead of JSON** — treated as an error ("respuesta no válida"), previous values kept. Test in Task 11.

---

## Task 0: Commit the WI-5…WI-11 fixes already in the working tree

**Files:** everything `git status` lists under `.camarones/` and `tests/` from the earlier session, plus `README.md`. **Not** the untracked `docs/research/dev-harness-requirements.md`, `docs/research/spec-v0.1-gap.md`, `docs/superpowers/plans/2026-10-25-board-1a.md`, `docs/superpowers/specs/2026-10-24-board-design.md` (another session's).

- [ ] **Step 1: Run the suites** — `uv run python -m pytest -n auto -q -p no:cacheprovider` (expected: only the 2 known Windows failures in `tests/test_install_state.py`), renderer and portal `npx vitest run` (all pass).
- [ ] **Step 2: Commit in three commits**, staging by path:
  1. `fix(app): interview mode chosen, kit plugins off per machine, Codex models from Codex` — `lib/docs.py`, `lib/serve.py`, `lib/machine.py`, `lib/trust.py`, `lib/harness/plugins.py` and their tests.
  2. `feat(app): coloured Plan board, mode chooser, golden questions launch, libraries in Calidad` — `desktop/renderer/src/**`, `desktop/renderer-build/**`, `ui/src/libs.js`, `portal/app/src/libs.js`, `portal/app-build/**`.
  3. `docs: the app's Plan, Calidad, plugins and repair; kit 4.59.0` — `README.md`, `lib/common.py`, `lib/tutorial.py`, `TUTORIAL.md`, and the spec + this plan.
- [ ] **Step 3: Verify** `git -c safe.directory=* status --short` lists only the other session's four untracked files.

---

# Step (a): core + shared screen

## Task 1: Coverage from local reports

**Files:**
- Create: `.camarones/lib/health.py` (module docstring + this task's functions)
- Test: `tests/test_health.py`

**Interfaces:**
- Produces: `coverage_reports(repo: Path) -> list[dict]` — each `{"type": "jacoco"|"lcov"|"cobertura", "path": "<repo-relative posix>", "percent": float (1 decimal), "at": iso}` or `{"type", "path", "error": str}`; newest first. `repo_coverage(reports) -> dict | None` — `{"percent", "at", "source": "report", "path"}` from the newest report without error.
- Paths (globs relative to the repo): `target/site/jacoco/jacoco.xml`, `build/reports/jacoco/**/*.xml`, `coverage/**/lcov.info`, `coverage/**/cobertura*.xml`. `MAX_REPORT_BYTES = 5_000_000`.

- [ ] **Step 1: Write failing tests** in `tests/test_health.py`:
  - `test_jacoco_report_level_line_counter`: a `jacoco.xml` with a package-level `<counter type="LINE" missed="5" covered="5"/>` and a report-level `<counter type="LINE" missed="20" covered="80"/>` → `percent == 80.0`, `type == "jacoco"`.
  - `test_lcov_sums_every_file`: `coverage/app/lcov.info` with `LF:10/LH:5` and `LF:30/LH:25` → `75.0`.
  - `test_cobertura_line_rate`: `coverage/cobertura-coverage.xml` root `line-rate="0.6234"` → `62.3`.
  - `test_reports_outside_the_known_paths_are_ignored`: `src/jacoco.xml` → `[]`.
  - `test_hostile_or_huge_reports_are_skipped` (Review Focus 2): a jacoco file containing `<!DOCTYPE` → `error`; a file over `MAX_REPORT_BYTES` → `error`; truncated XML → `error`; the other report in the same repo still parsed.
  - `test_repo_coverage_takes_the_newest_good_report`: two reports with different mtimes (set with `os.utime`), the newest broken → the older good one's percent, `source == "report"`.
- [ ] **Step 2: Run** `uv run python -m pytest tests/test_health.py -q -p no:cacheprovider` → FAIL (`ModuleNotFoundError: lib.health`).
- [ ] **Step 3: Implement** in `lib/health.py`: refuse a file whose bytes contain `<!DOCTYPE` or `<!ENTITY` before `xml.etree.ElementTree.fromstring`; jacoco = the root's direct `counter[@type="LINE"]`; lcov = sum of `LH:`/`LF:` lines; cobertura = root `line-rate` × 100; `at` from `stat().st_mtime`; sort newest first.
- [ ] **Step 4: Run** the same command → PASS.
- [ ] **Step 5: Commit** `feat(health): coverage from local JaCoCo, lcov and Cobertura reports`.

## Task 2: Tech-debt items from the docs

**Files:**
- Modify: `.camarones/lib/health.py`
- Test: `tests/test_health.py`

**Interfaces:**
- Consumes: `docs.collect()` rows (`path`, `trust`) for each source page's trust state.
- Produces: `debt_items(repos: list[str]) -> dict[str, list[dict]]` — keys are repo names plus `"_project"`; each item `{"source": "quality/tech-debt.md"|"quality/architecture-review.md", "trust": str, "item": str, "impact": "high"|"medium"|"low"|"unknown", "effort": str, "evidence": [str], "owner": str, "recommendation": str}` (absent columns → `""`).
- Header aliases (case-insensitive): item ← `item|ítem|elemento|area|área`; impact ← `impact|impacto`; effort ← `estimated effort|effort|esfuerzo|esfuerzo estimado`; evidence ← `evidence|evidencia`; owner ← `owner|responsable|dueño`; recommendation ← `recommendation|recomendación`. Impact words: `high|alto|alta` → high, `medium|medio|media` → medium, `low|bajo|baja` → low.

- [ ] **Step 1: Write failing tests:**
  - `test_debt_rows_go_to_the_repos_their_evidence_names`: `docs/quality/tech-debt.md` with rows whose Evidence is `` `api:src/A.java` `` and `` `api:x`, `web:y` `` → `api` has 2 items, `web` 1, impact normalised, `trust == "draft"`.
  - `test_architecture_review_columns`: Area · Impact · Estimated effort · Evidence · Recommendation → `item` from Area, `effort`, `recommendation` filled.
  - `test_spanish_headers_extra_columns_and_the_skeleton` (Review Focus 3): headers `Elemento | Impacto | Evidencia | Responsable | Notas`; a row `<what> | <high/medium/low and why> | …` skipped; `Notas` ignored.
  - `test_rows_naming_no_known_repo_are_project_level` → under `"_project"`.
  - `test_no_quality_pages_means_no_debt` → `{"api": [], "web": [], "_project": []}`.
- [ ] **Step 2: Run** `… tests/test_health.py -k debt` → FAIL.
- [ ] **Step 3: Implement** `debt_items`: read the first pipe table after `## Items` (tech-debt) or the first pipe table (architecture-review); split cells on unescaped `|`; skip separator rows and rows whose first cell starts with `<`; evidence = backtick-stripped `repo:path` tokens; trust from the `docs.collect()` row whose `path` is the source page.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(health): technical debt items per repo from the quality pages`.

## Task 3: The snapshot — sources, states, build and load

**Files:**
- Modify: `.camarones/lib/health.py`
- Test: `tests/test_health.py`

**Interfaces:**
- Consumes: Task 1 `coverage_reports`, `repo_coverage`; Task 2 `debt_items`; `doctor.check(log)` / `doctor.problems(result)`; `harness.freshness.states()` and `freshness.parse(ref)` (repo of each `missing`/`changed` ref); `harness.evals.load()`; `budget.standing()`; `docs.review_queue()`; `inventory.load()`; `radar.scan_repo(name, path)` (tool `id == "sonar"`, its `info`); `common.repo_dir`, `common.save_json`, `common.load_json`, `common.CACHE`.
- Produces:
  - `SNAPSHOT = CACHE / "health.json"`; `VERSION = 1`; `VULN_SCAN_MAX_DAYS = 30`; `COVERAGE_MIN = 50`.
  - `build(log=print) -> dict`; `load() -> dict | None` (None when missing, unreadable, not a dict, or `v != VERSION`); `areas(snapshot: dict, today: date | None = None) -> dict`.
  - Snapshot shape (every block may instead be `{"error": str}`):
    ```
    {"v": 1, "at": iso,
     "machine": {"at", "missing": [str], "drift": int},
     "docs": {"at", "stale": [{"path", "repos": [str]}], "suspect": [{"path", "repos"}],
              "evals": {"total": int, "confirmed": int}, "context": {"total", "budget", "over"}, "review": int},
     "inventory": {"at": iso | None, "scanned": bool},
     "repos": {name: {"cloned": bool, "libraries": int, "vulns": {severity: int}, "vulnerable": [{"name", "version", "severity", "id", "cve", "fixed"}],
                      "sonar": {"used": bool, "project", "organization", "host", "link"},
                      "coverage": {"percent", "at", "source", "path"} | None, "reports": [...], "debt": [...]}},
     "debt_project": [...],
     "areas": {"machine"|"docs"|"code": {"state": "ok"|"warn"|"bad", "figures": [{"key", "n"}], "next": {"key", "row"} | None}},
     "repo_state": {name: "ok"|"warn"|"bad"},
     "verdict": [{"key", "n"}]}
    ```
  - Reason keys (the UI translates them): `machine.missing`, `machine.drift`, `machine.unchecked`, `docs.stale`, `docs.suspect`, `docs.context`, `docs.noEvals`, `docs.review`, `code.vulnHigh`, `code.vulnMedium`, `code.noScan`, `code.oldScan`, `code.lowCoverage`, `code.highDebt` (step c adds `code.gateFailed`). Row ids: `doctor`, `drift`, `fresh`, `evals`, `context`, `review`, `blocks`, `ab`, `repos`, `libs`.

- [ ] **Step 1: Write failing tests:**
  - `test_areas_follow_the_rules` (parametrized over hand-built snapshots): missing tool → machine `bad`; drift only → `warn`; stale page → docs `bad`; suspect / over budget / `confirmed == 0` / review > 0 → `warn`; a `high` or `critical` vuln → code `bad`; `medium` → `warn`; `inventory.scanned is False` → `warn` with `code.noScan`; scan 31 days old (with `today`) → `code.oldScan`, 30 days → not; coverage 49.9 → `code.lowCoverage`, 50.0 → not; a `high` debt item → `code.highDebt`; all clean → three `ok` and `verdict == []`.
  - `test_next_action_is_the_first_reason`: docs with stale and review → `next == {"key": "docs.stale", "row": "fresh"}`.
  - `test_build_writes_a_snapshot_the_api_can_load` (fixture `wired`): `build()` → `load()` equal, `v == 1`, every repo of the workspace present.
  - `test_one_failing_source_does_not_stop_the_rest`: monkeypatch `budget.standing` to raise → `docs.context == {"error": ...}`, `areas` still computed, `machine` present.
  - `test_a_repo_not_cloned_is_listed_with_nothing_known` (Review Focus 1): delete one repo folder → `cloned is False`, `coverage is None`, `libraries == 0`, no exception.
  - `test_load_refuses_corrupt_or_newer_snapshots` (Review Focus 4): `"{"` → None; `{"v": 2}` → None.
  - `test_the_doctor_record_matches_the_snapshot`: after `build()`, `doctor.checked()["result"]` is the one the `machine` block came from.
- [ ] **Step 2: Run** `… tests/test_health.py` → the new tests FAIL.
- [ ] **Step 3: Implement** `build` (each source in its own `try/except Exception` → `{"error": str(e)}`), `load`, `areas`; per-repo state = worst of its vulns, coverage and debt by the same rules; verdict = the reasons of non-`ok` areas in area order.
- [ ] **Step 4: Run** `… tests/test_health.py` → PASS.
- [ ] **Step 5: Commit** `feat(health): the project health snapshot and its state rules`.

## Task 4: `camaron health`, the catalog and `GET /api/health`

**Files:**
- Modify: `.camarones/camarones.py` (parser next to `inventory`; `cmd_health`; dispatch), `.camarones/lib/catalog.py` (`"health": _e("app", "check", "Salud del proyecto: máquina, docs y código", "Project health: machine, docs and code")`), `.camarones/lib/serve.py` (GET `health`), help text at the top of `camarones.py`.
- Test: `tests/test_health.py`, `tests/test_catalog.py` (already checks parser ↔ catalog)

**Interfaces:**
- Consumes: Task 3 `build`, `load`.
- Produces: CLI `health [--json] [--refresh]`; `GET /api/health` → `{"snapshot": <snapshot> | null}`.

- [ ] **Step 1: Write failing tests:**
  - `test_cli_health_builds_once_and_prints_the_verdict`: no snapshot → `health` exits 0, creates `SNAPSHOT`, stdout names the three areas; second run without `--refresh` does not rebuild (mtime unchanged).
  - `test_cli_health_json_is_the_snapshot`: `health --json` → `json.loads(stdout)["v"] == 1`.
  - `test_cli_health_refresh_rebuilds`: mtime changes.
  - `test_api_health_reads_and_never_builds` (server fixture as in `tests/test_portal_pipeline.py`): no snapshot → `{"snapshot": null}` and still no file; after `build()` → the snapshot.
- [ ] **Step 2: Run** `… tests/test_health.py tests/test_catalog.py` → FAIL.
- [ ] **Step 3: Implement** `cmd_health(a)` (text output in the machine language via the CLI's existing language helper; one line per area `✔|!|✖ <Area>: <reasons>` and a per-repo table: repo · Sonar · cobertura · vulns · deuda); add `health` to `PANELS.quality` in `desktop/renderer/src/catalog.js` so it is not duplicated under "Todos los comandos".
- [ ] **Step 4: Run** the two test files and `uv run --script .camarones/camarones.py catalog --check` → PASS / exit 0.
- [ ] **Step 5: Commit** `feat(health): camaron health and GET /api/health`.

## Task 5: The shared `HealthBoard`

**Files:**
- Create: `.camarones/ui/src/health.js` (pure helpers), `.camarones/ui/src/health.jsx` (component), `.camarones/ui/src/health.test.js`
- Modify: `.camarones/ui/i18n/index.js` (strings), `.camarones/ui/src/ui.css` (board styles, theme tokens only), `.camarones/ui/src/index.js` (export `HealthBoard`)

**Interfaces:**
- Consumes: the snapshot shape (Task 3).
- Produces: `HealthBoard({ snapshot, actions, links, repoHref, onRefresh, refreshing })` — `actions: { [rowId]: () => ReactNode }` (app), `links: { [rowId]: href }` (portal), `repoHref(repo) -> string`, `onRefresh` absent in the portal (no "Comprobar todo"). Helpers: `verdictText(snapshot, t) -> string`, `repoRow(name, repo, state, t) -> { name, sonar, coverage, vulns, debt, state }` (strings, "—" for unknown), `rowsFor(area, snapshot) -> [{ id, state, figure }]`, `fmtAgo(iso, now, t)`.
- Shared string keys: `hb.verdictOk`, `hb.checked`, `hb.refresh`, `hb.area.machine|docs|code`, `hb.state.ok|warn|bad` (machine: "Lista", docs: "Al día", code: "Sano"; warn "Revisar"; bad "Riesgo"), one `hb.reason.<key>` per Task 3 reason key, one `hb.row.<id>` + `hb.rowWhat.<id>` per row id, table headers `hb.col.repo|sonar|coverage|vulns|debt`, `hb.full` ("Ver completo →"), `hb.notCloned`, `hb.never` ("Aún no se ha comprobado: ábrelo en la app o ejecuta camaron health").

- [ ] **Step 1: Write failing tests** in `ui/src/health.test.js`:
  - `verdictText` lists the reasons with their numbers; all `ok` → `hb.verdictOk`.
  - `repoRow` for a repo without Sonar, coverage or debt → `sonar === 'no'`, `coverage === '—'`, `debt === '—'` (never `'0'`); not cloned → every figure `'—'` and `hb.notCloned`.
  - `rowsFor('docs', s)` returns the six doc rows in spec order (`fresh`, `evals`, `context`, `review`, `blocks`, `ab`), with `error` rows carrying the message.
  - Every `hb.*` key used by `health.jsx` exists in both `en` and `es` (same scan as the renderer's `i18n.test.js`).
- [ ] **Step 2: Run** `cd .camarones/portal/app && npx vitest run ../../ui/src/health.test.js` → FAIL.
- [ ] **Step 3: Implement** the helpers and the component: verdict + checked line; three tiles (state colour from `--color-estado-*`, two figures, next action → `actions[row]` in the app or `links[row]` in the portal, nothing if neither); tabs remembered in `localStorage` under `cu.health.tab` (try/catch); rows; Código's per-repo table with `repoHref` links.
- [ ] **Step 4: Run** the portal Vitest (it includes `../../ui/**`) → PASS.
- [ ] **Step 5: Commit** `feat(ui): HealthBoard, the shared project health screen`.

## Task 6: The app's Calidad on the board

**Files:**
- Modify: `.camarones/desktop/renderer/src/sections/Quality.jsx`, `.camarones/desktop/renderer/src/i18n.js`, `.camarones/desktop/renderer/src/app.css` (only what the moved controls need), `.camarones/desktop/renderer-build/**`
- Test: `.camarones/desktop/renderer/src/i18n.test.js` (keys), `.camarones/desktop/renderer/src/states.test.js` if it renders sections

**Interfaces:**
- Consumes: Task 5 `HealthBoard`; Task 4 `GET /api/health` and the `health` catalog command (`--refresh`).
- Produces: none for later tasks.

- [ ] **Step 1: Write a failing test**: `quality.test.js` — a pure `boardActions(rowIds)` map exists for exactly `doctor, drift, fresh, evals, context, blocks, ab, libs` (the rows whose controls the app owns; `review` is a link, not an action).
- [ ] **Step 2: Run** renderer `npx vitest run src/quality.test.js` → FAIL.
- [ ] **Step 3: Implement**: on mount `GET health`; `snapshot === null` → run `health --refresh` (quiet job) then reload; "Comprobar todo" → `health --refresh`; each existing card (Doctor, Fresh, Evals, Ab, Context, Blocks, Libs) becomes the body a row's "Abrir" expands (same code, moved); after any of their jobs ends, a quiet `health --refresh`; `repoHref = (r) => '../#/health/' + encodeURIComponent(r)`; `review` row links `../#/review`; "Todos los comandos" stays last.
- [ ] **Step 4: Run** renderer `npx vitest run` and `npm run build` → PASS, `renderer-build` updated.
- [ ] **Step 5: Commit** `feat(app): Calidad is the project health board`.

## Task 7: The portal's Salud view

**Files:**
- Create: `.camarones/portal/app/src/Health.jsx`
- Modify: `.camarones/portal/app/src/router.js` (`NATIVE` += `health`), `.camarones/portal/app/src/zones.js` (Calidad views: `{ id: 'health', href: '#/health', live: true }` first; `ROUTES.health = ['quality', 'health']`), `.camarones/portal/app/src/Native.jsx`, `.camarones/portal/app/src/i18n/portal.js` (`view.health` / `viewd.health`), `.camarones/portal/app-build/**`
- Test: `.camarones/portal/app/src/router.test.js`, `zones.test.js`

**Interfaces:**
- Consumes: Task 5 `HealthBoard`; `GET /api/health`.
- Produces: `Health({ arg })` — `arg === ''` the board; Task 9 adds the per-repo page for `arg = <repo>`.

- [ ] **Step 1: Write failing tests:** `resolve('#/health', live)` → `{ kind: 'native', view: 'health', arg: '' }`; in static mode → home; `locate('#/health')` → `{ zone: 'quality', view: 'health' }`; the Calidad zone's first live view is `health`.
- [ ] **Step 2: Run** portal `npx vitest run src/router.test.js src/zones.test.js` → FAIL.
- [ ] **Step 3: Implement** `Health.jsx`: fetch `health`; `snapshot === null` → `hb.never`; else `HealthBoard` with `links = { fresh: '#/review', review: '#/review', libs: '#/libs', context: '#/kpis', evals: '#/kpis' }`, `repoHref = (r) => '#/health/' + encodeURIComponent(r)`, no `actions`, no `onRefresh`.
- [ ] **Step 4: Run** portal `npx vitest run` and `npm run build` → PASS.
- [ ] **Step 5: Commit** `feat(portal): Salud, the project health view of Calidad`.

## Task 8: Ship step (a)

**Files:** `README.md`, `.camarones/lib/tutorial.py`, `.camarones/TUTORIAL.md`, `.camarones/templates/docs/guides/tutorial.md`, `.camarones/templates/docs/i18n/es/guides/tutorial.md`, `.camarones/lib/common.py` (`"kit": "4.60.0"`); board card WI-2 in `cam-docs/backlog`.

- [ ] **Step 1: Docs**: README — the Calidad row of the app table (verdict, three areas, per-repo table), Salud in the portal's view list, `camaron health` in the command list, the version badge; `lib/tutorial.py` es + en where it lists Calidad; regenerate `TUTORIAL.md` (command in AGENTS.md §5.1); the two command-guide templates gain `camaron health` (commit body says existing projects keep their copy).
- [ ] **Step 2: Full suites** → pytest (only the 2 known Windows failures), renderer, portal, desktop helpers green.
- [ ] **Step 3: Sandbox end to end**: `uv run scripts/sandbox.py cli health --refresh`; open the app UI against the sandbox (as in the WI-5…11 checks) — tiles, verdict, per-repo table, row "Abrir" controls; drop a JaCoCo fixture into a sandbox repo's `target/site/jacoco/` and see coverage; the portal's `#/health` read-only.
- [ ] **Step 4: Commit** `docs: project health in the app and the portal; kit 4.60.0`; move WI-2 to In Review (`board move WI-2 "In Review"` with `CAMARONES_ROOT` = the camaron-dev `cam-docs`).

---

# Step (b): the portal's per-repo page

## Task 9: `#/health/<repo>` and `#/libs/<repo>`

**Files:**
- Create: `.camarones/portal/app/src/healthRepo.js` (pure), `.camarones/portal/app/src/healthRepo.test.js`
- Modify: `.camarones/portal/app/src/Health.jsx` (repo page when `arg`), `.camarones/portal/app/src/Libs.jsx` (initial `repo` filter from `arg`), `.camarones/portal/app/src/router.test.js`, `.camarones/portal/app/src/i18n.js` (page strings), `.camarones/portal/app-build/**`, `README.md`; board: a new card under WI-1 for this step (create with `board add story … --epic WI-1`), moved to In Review at the end.

**Interfaces:**
- Consumes: the snapshot (Task 3: `repos[name]`, `repo_state`, `docs.stale|suspect[].repos`, `debt_project`).
- Produces: `repoPage(snapshot, name) -> { state, sonar, reports, coverage, vulnerable (worst first), debt: { 'quality/tech-debt.md': [...], 'quality/architecture-review.md': [...] }, pages: [{ path, state }] } | null` (null: unknown repo).

- [ ] **Step 1: Write failing tests:** `repoPage` for an unknown repo → null; vulnerable sorted critical > high > medium > low; debt grouped by source; `pages` = stale and suspect pages whose `repos` include it; router `#/health/api` → `{ view: 'health', arg: 'api' }`; `#/libs/api` → `{ view: 'libs', arg: 'api' }`.
- [ ] **Step 2: Run** portal `npx vitest run src/healthRepo.test.js src/router.test.js` → FAIL.
- [ ] **Step 3: Implement** the page (header with state and links: Sonar dashboard, `#/docs/repos/<repo>/index.md`, `#/libs/<repo>`; four blocks: Calidad del código, Vulnerabilidades with osv.dev links, Deuda técnica (each evidence `repo:path` linked the way the portal's pages already link their `x-sources`), Documentación de este repo) with the spec §5 empty-state copy verbatim; unknown repo → "No existe ese repo" + link to `#/health`; `Libs` sets `f.repo = arg` on mount.
- [ ] **Step 4: Run** portal `npx vitest run`, `npm run build`, sandbox check of one repo page → PASS.
- [ ] **Step 5: Commit** `feat(portal): one health page per repo`.

---

# Step (c): the SonarQube server read

## Task 10: SonarQube tokens in the keychain

**Files:**
- Modify: `.camarones/lib/creds.py` (kind `sonarqube`), `.camarones/lib/serve.py` (`/api/app/creds` accepts it), `.camarones/desktop/renderer/src/sections/Machine.jsx` (type option "SonarQube"; host prefill from `#/machine?host=`), `.camarones/desktop/renderer/src/i18n.js`
- Test: `tests/test_creds.py` (or the existing creds tests file — `grep -l "creds" tests/*.py`), `tests/test_machine.py`

**Interfaces:**
- Produces: `creds.api_base(host, "sonarqube") -> "https://<host>"` (or `http://` for `localhost`/`127.0.0.1` only); `creds.verify(host, "sonarqube", token)` → `GET /api/authentication/validate` with Basic `token:` → `(True, "")` when `{"valid": true}`; `creds.sonar_get(host, token, path, params) -> dict` (10 s timeout; raises `SonarError(reason)` on non-JSON, 401/403, 404, timeout).

- [ ] **Step 1: Write failing tests** against a fake Sonar `ThreadingHTTPServer` on port 0: valid token saved; `{"valid": false}` refused; `sonar_get` raising `SonarError("token no válido")` on 401, `"proyecto no encontrado"` on 404, `"sin conexión"` on timeout, `"respuesta no válida"` on 200 `text/html` (Review Focus 5); an `http://sonar.example.com` host refused before any request; the token absent from the server's logged URL and from `hosts.json`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** in `creds.py` with `urllib` (Basic auth header from `base64` of `token:`); the Máquina Tokens type select gains `<option value="sonarqube">SonarQube</option>`.
- [ ] **Step 4: Run** pytest files and renderer Vitest → PASS.
- [ ] **Step 5: Commit** `feat(creds): SonarQube tokens in the keychain, https only`.

## Task 11: Read Sonar into the snapshot

**Files:**
- Modify: `.camarones/lib/health.py` (Sonar block in `build`, `code.gateFailed` in `areas`), `.camarones/lib/docs.py` only if the workspace reader needs to pass the new optional `sonar` key through (it must tolerate its absence)
- Test: `tests/test_health_sonar.py`

**Interfaces:**
- Consumes: Task 10 `creds.get(host)`, `creds.sonar_get`, `SonarError`; radar's `sonar` info (`project`, `organization`, host); `workspace.yaml` `sonar: {host}`.
- Produces: `repos[name].sonar.server = {"at", "gate": "OK"|"WARN"|"ERROR"|None, "coverage", "bugs", "vulnerabilities", "security_hotspots", "code_smells", "debt_minutes", "ratings": {"maintainability", "reliability", "security"}}` and `repos[name].sonar.error`; `repos[name].coverage` prefers Sonar (`source: "sonar"`); `METRICS = "coverage,bugs,vulnerabilities,security_hotspots,code_smells,sqale_index,sqale_rating,reliability_rating,security_rating"`.

- [ ] **Step 1: Write failing tests** with the fake server and a fake keychain: happy path fills `server` and `gate`; `ERROR` gate → code `bad` with `code.gateFailed`; host resolution order: repo `sonar.host.url` > SonarCloud for `organization` > `workspace.yaml` `sonar.host`; no token → `server` absent, `error` absent, row shows "Conectar SonarQube" (a `connect: true` flag); a failing read keeps the previous snapshot's `server` values with their `at` and adds `error`; one repo failing leaves the other's values; `load()` + `--json` output contain no token string; reads happen only in `build()` (patch `sonar_get` to fail the test if called from `load()` or `GET /api/health`).
- [ ] **Step 2: Run** `… tests/test_health_sonar.py` → FAIL.
- [ ] **Step 3: Implement** in `build()` after the radar read: resolve host, skip when no key or no token, two `sonar_get` calls per repo (`/api/measures/component`, `/api/qualitygates/project_status`), merge with `load()`'s previous values on `SonarError`.
- [ ] **Step 4: Run** → PASS, and `tests/test_health.py` still green.
- [ ] **Step 5: Commit** `feat(health): read coverage, issues, debt and the quality gate from SonarQube`.

## Task 12: Show Sonar on screen and ship step (c)

**Files:**
- Modify: `.camarones/ui/src/health.js`, `.camarones/ui/src/health.jsx`, `.camarones/ui/src/health.test.js`, `.camarones/ui/i18n/index.js`, `.camarones/portal/app/src/Health.jsx`, `.camarones/portal/app/src/healthRepo.js` (+ test), `.camarones/desktop/renderer/src/sections/Quality.jsx`, both builds, `README.md`, `.camarones/lib/tutorial.py`, `.camarones/TUTORIAL.md`, `docs/research/tooling-candidates.md` (M5 → done), `.camarones/lib/common.py` (`"kit": "4.61.0"`); board: a new card under WI-1 for step (c), In Review at the end.

**Interfaces:**
- Consumes: Task 11's `sonar.server`, `sonar.error`, `sonar.connect`, `coverage.source`.

- [ ] **Step 1: Write failing tests:** `repoRow` shows the gate word and Sonar's coverage with "Sonar" as source; a repo with `connect: true` exposes a `connect` action id; `repoPage` lists the nine Sonar figures with `debt_minutes` formatted as hours/days (`'2 d 3 h'`); a `sonar.error` renders its reason and the values' date.
- [ ] **Step 2: Run** portal Vitest → FAIL.
- [ ] **Step 3: Implement** the screen changes; the app's `connect` action opens `#/machine?host=<host>` with the Tokens type preset to SonarQube; docs per spec §9 (token, `sonar.host` key) and the version bump.
- [ ] **Step 4: Run** all suites; sandbox check with the fake Sonar server pointed at by `sonar.host` (a throwaway script under the scratchpad, not committed) → PASS.
- [ ] **Step 5: Commit** `feat(health): SonarQube figures in Calidad and the repo pages; kit 4.61.0`.
