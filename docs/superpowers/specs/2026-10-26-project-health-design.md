# Project health: one Calidad screen for the app and the portal, with tech debt and SonarQube — design

Board: epic WI-1 (desktop UX pass, dogfooding), card WI-2 "Rediseñar la página Calidad: bonita e intuitiva", grown by
the user's request to cover technical debt and SonarQube per repo and to share the screen with the portal.

## 1. Intent

The desktop app's Calidad section is a stack of unrelated cards (doctor, context budget, golden questions, A/B,
libraries, stale pages, generated blocks) with no hierarchy: you cannot tell at a glance how the project is, nor what to
do first. It mixes three jobs — is **this machine** ready, can we **trust the docs**, is **the code** healthy — and says
nothing about technical debt or SonarQube, which teams already use.

This piece turns Calidad into **one project-health screen**:

- A verdict line and three area tiles (Máquina, Documentación, Código), each with a state, two figures and one next
  action.
- Per repo: whether it uses SonarQube, its coverage, its vulnerabilities and its technical debt (what the docs record
  and, when connected, Sonar's measure).
- The same screen in the desktop app (with actions) and in the portal (read-only), plus a per-repo page in the portal
  that "Ver completo →" opens.

**Done when:** opening Calidad in the app or the portal tells you within a few seconds what is wrong, in which repo,
and what to click next — with no AI and no Sonar server needed for that first answer.

**Anti-goals — a failure even if it works:** the portal running checks on every visit; numbers that differ between the
app and the portal; a Sonar token on a command line, in a log, in the snapshot or sent over plain http; a 3.x/4.x
project that needs a manual step; a missing figure shown as 0 instead of "—".

### 1.1 Decisions taken with the user (2026-10-26)

| Question | Decision |
|---|---|
| What is Calidad for | Overall project health: machine, docs and code, each scored with its next action |
| Where Sonar data comes from | Both, files first: offline detection and local coverage now; the server read as a later step of the same epic |
| What "deuda técnica" shows | Both, per repo: what the docs record (`tech-debt.md`, `architecture-review.md`) and Sonar's debt when connected |
| App ↔ portal | Same shared screen; the portal is read-only and has a per-repo detail page; "Ver completo" opens it |
| Approach | One cached health snapshot behind both apps (§2), built in order (a) core + shared screen, (b) portal per-repo page, (c) Sonar server read |

## 2. Approach: one health snapshot

`lib/health.py` gathers every fact without AI, works out each area's state, and writes one snapshot. The CLI, the API
and both apps read that snapshot, so the app and the portal always show the same numbers and the portal never runs a
check.

Rejected: each app composing existing commands in the browser (the portal cannot run commands; the two would drift);
an endpoint that computes on every request (the stale-pages check takes seconds on a big project; the portal would
re-run it on every visit).

## 3. The snapshot — `lib/health.py`

### 3.1 Functions

- `build(log=print) -> dict` — reads every source (§3.2), computes `areas` (§3.3), writes the snapshot and returns it.
  Step (c) adds the Sonar read here (§7).
- `load() -> dict | None` — the last snapshot, or None when never built.
- `areas(snapshot) -> dict` — pure: the three area states, their figures, their next action and the verdict. Tested
  on its own.

Stored in `CACHE / "health.json"` (`cam-docs/.cache/`, git-ignored, per machine; written with `common.save_json`, which
replaces the file in one step). Every source carries `at` (ISO time it was read). A source that fails becomes
`{"error": "<message>"}`; the rest of the snapshot is still built.

### 3.2 Sources (no AI, no network in steps a–b)

| Area | Fact | Read from |
|---|---|---|
| Máquina | missing prerequisites and pinned tools; drifted kit files | `doctor.check()` during `build` (it saves its record, so the doctor row and `doctor.checked()` agree) |
| Documentación | stale and suspect pages, with the repos their cited code belongs to | `harness.freshness` (as `camaron fresh --json`) |
| Documentación | golden questions: total, confirmed | `harness.evals.load()` |
| Documentación | context per agent session vs. budget | `budget.standing()` |
| Documentación | pages waiting for review | `docs.review_queue()` |
| Código, per repo | libraries, vulnerabilities by severity, the scan's date; the vulnerable libraries themselves | the saved inventory (as `GET /api/inventory`) |
| Código, per repo | Sonar used or not; project key, organization, host, dashboard link | `radar.scan_repo()` (rule `sonar`) |
| Código, per repo | coverage from local reports: type, path, line %, file date | known paths only (§3.4) |
| Código, per repo | debt items: item/area, impact, effort, evidence, owner, recommendation, source page, that page's trust state | the tables of `docs/quality/tech-debt.md` and `docs/quality/architecture-review.md` (§3.5) |

### 3.3 State rules — `areas()`

Each area is `ok`, `warn` or `bad`, shown as green "Lista / Al día / Sano", amber "Revisar", red "Riesgo".

- **Máquina:** `bad` if a needed prerequisite or pinned tool is missing; `warn` if kit files drifted; `ok` otherwise;
  unknown (never checked) is `warn` with next action "Comprobar la máquina".
- **Documentación:** `bad` if a page is stale (its cited code is gone); `warn` if a page is suspect, the context is
  over budget, there is no confirmed golden question, or pages await review; `ok` otherwise.
- **Código:** `bad` if any repo has a critical or high vulnerability (step c: or a failed quality gate); `warn` if any
  repo has a medium one, the vulnerability scan never ran or is older than 30 days, a coverage report reads under 50 %,
  or a debt item has high impact; `ok` otherwise.
- **Per repo** (the table and the per-repo page): the worst of its vulnerabilities, coverage and debt by the same rules.

Each area names one **next action** (its most urgent item, in the order the rules above list them) as `{label key,
target}`; the verdict lists the areas that are not `ok` with their reason ("2 vulnerabilidades altas · 3 páginas
desactualizadas"). Thresholds are module constants (`VULN_SCAN_MAX_DAYS = 30`, `COVERAGE_MIN = 50`).

### 3.4 Local coverage reports

Only these paths under each repo, never a full disk scan:

| Type | Paths | Value |
|---|---|---|
| JaCoCo XML | `target/site/jacoco/jacoco.xml`, `build/reports/jacoco/**/*.xml` | report-level `<counter type="LINE">`: covered / (covered + missed) |
| lcov | `coverage/**/lcov.info` | sum of `LH` / sum of `LF` |
| Cobertura XML | `coverage/**/cobertura*.xml` | root `line-rate` |

Each found report gives `{type, path, percent, at}` (`at`: the file's modification time). The repo's coverage is the
newest report's. Parse errors make that report `{error}`; XML is parsed with the standard library, entity expansion off.

### 3.5 Debt items from the docs

Rows of the first Markdown table under `## Items` (`tech-debt.md`: Item · Impact · Evidence · Owner) and of the first
table in `architecture-review.md` (Area · Impact · Estimated effort · Evidence · Recommendation). Header names are
matched case-insensitively in English and Spanish. A row belongs to every repo named by a `<repo>:` prefix in its
Evidence cell (backticks stripped); rows naming no known repo go under `_project`. Impact is normalised to
`high | medium | low | unknown` from its first word. Each item keeps its source page and that page's trust state
(`draft`, `confirmed`, `suspect`…, from the docs index). Skeleton placeholders (`<what>`) are skipped.

### 3.6 CLI and API

- `camaron health [--json] [--refresh]` — prints the verdict, the three areas and the per-repo table; `--json` prints
  the snapshot; `--refresh` builds first. Without a snapshot it builds one. New entry in `lib/catalog.py` (zone
  `check`, verdict `app`), so the app runs it through `app/cmd` like every other action and `catalog --check` stays
  green. Spanish/English output follows the machine language like the other commands.
- `GET /api/health` (`lib/serve.py`) — the snapshot, or `{"snapshot": null}` when it was never built. Read-only, no
  token needed, like `/api/inventory`; it never builds. The app builds it (`health --refresh` through `app/cmd`, a job)
  the first time its Calidad opens without one; the portal then says "Aún no se ha comprobado: ábrelo en la app o
  ejecuta `camaron health`".

## 4. The shared screen — `.camarones/ui`

### 4.1 `HealthBoard`

`ui/src/health.jsx` (component) and `ui/src/health.js` (pure helpers, Vitest), strings in the shared dictionary
`ui/i18n/index.js` (es + en). Props: `snapshot`, `actions` (per row id, a render function the app passes; absent in
the portal), `links` (per row id, where the portal points), `repoHref(repo)`.

- **Top:** verdict line and "comprobado hace …".
- **Tiles:** Máquina, Documentación, Código — colour and word, two figures, the next-action button (in the portal a
  link, or nothing if it needs the app).
- **One area open at a time** (tabs; the choice remembered per browser in `localStorage`, wrapped in try/catch).
  Each check is a row: dot, name, one sentence on what it means, its figure, and the slot.
  - Máquina: requisitos y herramientas; ficheros del kit cambiados.
  - Documentación: páginas desactualizadas; preguntas de control (IA); contexto de cada sesión; páginas por revisar;
    bloques generados; con y sin cam-docs (IA); link to KPIs.
  - Código: the **per-repo table** — repo · Sonar (sí/no, link) · cobertura (with date and source) · vulnerabilidades
    by severity · deuda (count, worst impact, draft/confirmed) · "Ver completo →" — then a Librerías row.
- Missing or unknown values render "—" (never 0); a source with `error` renders its message as an Aviso in its row.
- Colours from the theme tokens only (`--color-estado-*`), as the Plan board does; no raw colours (`style.test.js`).

### 4.2 In the app — `sections/Quality.jsx`

The board, with the app's actions in each row's slot; "Abrir" expands the controls that work today (moved, not
rewritten): Doctor (install / repair), Fresh (ack / refresh unit), Evals (confirm / ask / propose), Ab, Context,
Blocks, Libs (reread / scan, the table). "Comprobar todo" runs `health --refresh`; after any action ends, a quiet
`health --refresh` updates the board. "Ver completo →" opens `../#/health/<repo>` (the portal on the same server).
"Todos los comandos" stays at the bottom (WI-4).

### 4.3 In the portal — view `#/health`

A native, live-only view (`router.js` `NATIVE`, `zones.js`: first view of the Calidad zone, before KPIs and CI;
`ROUTES.health = ['quality', 'health']`), read-only: rows link to Revisión, Librerías, KPIs and CI; no button that runs
something. Inside the desktop app's window the portal stays read-only too: the work is in the app's Calidad.

## 5. The per-repo page — portal `#/health/<repo>`

Reads the same `GET /api/health` and picks the repo; no second endpoint.

- **Header:** repo name and its state; links: Sonar dashboard (when known), the repo's brief/wiki in the portal,
  Librerías filtered to the repo (`#/libs/<repo>`: Libs reads an initial repo filter from its address — a small
  change to `Libs.jsx`).
- **Calidad del código:** Sonar (used or not, key, link; step c adds quality gate, coverage, bugs, vulnerabilities,
  hotspots, debt time, ratings); local coverage, one line per report (type, path, %, date).
- **Vulnerabilidades:** this repo's vulnerable libraries, worst first — version, severity, advisory link (osv.dev),
  fixed-in version.
- **Deuda técnica:** its items — item/area, impact, evidence (a link to the code via the portal's code links), owner,
  effort/recommendation when present, source page with its trust state.
- **Documentación de este repo:** stale and suspect pages citing its code, each linked.
- **Empty states that say what to do:** no Sonar → "Este repo no usa Sonar" and how to add it
  (`sonar-project.properties`); no coverage report → "No hay informe de cobertura: se lee el que deja la build
  (JaCoCo, lcov, Cobertura)"; no debt → "Aún no hay deuda registrada: la recoge la unidad «ADR, SLA, deuda técnica»".
- An unknown repo → "No existe ese repo" with a link back to `#/health`.

## 6. Backward compatibility

- No existing CLI command, flag, file or `workspace.yaml` key changes. New: `camaron health`, `GET /api/health`,
  `cam-docs/.cache/health.json` (generated, git-ignored), the optional `sonar.host` key (§7).
- Projects without the snapshot get one the first time the app's Calidad opens (or `camaron health`); the portal says
  so until then. Projects without `docs/quality/` simply show no debt.
- The portal's existing addresses keep working; `#/libs/<repo>` is new and `#/libs` unchanged.
- `VERSIONS["kit"]` bumps (minor) with step (a); the README badge with it.

## 7. Step (c): the SonarQube server read

- **Host:** each repo's `sonar.host.url` (radar), SonarCloud when only `organization` is set, else the new optional
  team-wide `workspace.yaml` key `sonar: {host: https://sonar.empresa.com}`. Absent key = unchanged behaviour.
- **Token:** per machine and host in the OS keychain through `lib/creds.py`, new kind `sonarqube`
  (`api_base` → `https://<host>`, Basic auth `token:`). Saved from Máquina › Tokens (type selector gains SonarQube),
  verified with `GET /api/authentication/validate` before saving; reaches the server in a request body only and never
  comes back (the existing `/api/app/creds` rule). Sent only over **https** (http only for `localhost`/`127.0.0.1`).
- **Read:** only during `health --refresh`, never when a page opens. Per repo, two GETs with a 10 s timeout:
  `/api/measures/component?component=<key>&metricKeys=coverage,bugs,vulnerabilities,security_hotspots,code_smells,
  sqale_index,sqale_rating,reliability_rating,security_rating` and `/api/qualitygates/project_status?projectKey=<key>`.
  Standard-library HTTP only (no new dependency, AGENTS.md §2.4 not triggered).
- **Results:** per repo `sonar.server = {at, gate, coverage, …}`. On failure (offline, 401, unknown key, timeout) the
  repo keeps its previous values with their date and gets `error` with a plain reason ("token no válido", "proyecto no
  encontrado", "sin conexión"). One repo failing never hides the others.
- **On screen:** quality gate and Sonar figures in the table and the per-repo page; coverage prefers Sonar's value
  and says its source; Código turns `bad` on a failed gate; a repo with Sonar but no token gets "Conectar SonarQube"
  (app only) → Máquina › Tokens with the host filled in.

## 8. Voice and strings

Every string in es and en (shared ones in `ui/i18n`, app ones in the renderer's `i18n.js`, portal ones in
`portal.js`). No jokes in states, errors or empty states; at most one, where the user waits ("Comprobar todo"). Copy
says what a check means and what to do, never the command name alone.

## 9. Docs that move with the code (AGENTS.md §5.1)

- README (Spanish): the Calidad row of the app table, the portal's view list (Salud and the per-repo page),
  `camaron health` in the command list, step (c)'s token and `sonar.host` key.
- Tutorial: `lib/tutorial.py` (es + en) where it lists Calidad, `TUTORIAL.md` regenerated; the command guide templates
  (`templates/docs/guides/tutorial.md` and its `es` twin) gain `camaron health` — existing projects keep their copy,
  said in the commit.
- `docs/research/tooling-candidates.md` M5: SonarQube API reads move from "later" to done in step (c).

## 10. Testing

TDD per AGENTS.md §2.2; offline and deterministic (`make_workspace`, `isolated_env`).

- **pytest — `health.py`:** each source read, each failing on its own (`error`, the rest built); `areas()` for every
  rule and threshold edge; coverage parsing for JaCoCo, lcov and Cobertura fixtures (and a broken file); debt tables
  in English and Spanish headers, `repo:` attribution, skeleton rows skipped; the CLI (`health`, `--json`,
  `--refresh`); `GET /api/health` first build and later reads; catalog in sync.
- **pytest — step (c):** a fake Sonar server on port 0 (happy path, 401, timeout, unknown key), a fake keychain, an
  http host refused, previous values kept on failure, and the token absent from the snapshot, the job log and `--json`.
- **Vitest — `ui/src/health.js`:** verdict text, per-repo row formatting, "—" for unknown, repo state; the portal's
  router/zones for `#/health`, `#/health/<repo>`, `#/libs/<repo>`; the app's i18n key test covers the new keys.
- **End to end:** the sandbox (PetClinic) in the app and the portal, as for WI-5…WI-11: snapshot built, tiles and
  table right, per-repo page, empty states (the sandbox has no Sonar config and no coverage report; a JaCoCo fixture
  report is dropped into a copy to see coverage).
- Both committed builds (`portal/app-build`, `desktop/renderer-build`) rebuilt and committed with their source.

## 11. Order of work and board

1. **(a) Core + shared screen:** `lib/health.py` with sources, rules, coverage and debt parsing; CLI, catalog, API;
   `HealthBoard` in `ui`; the app's Calidad on it; the portal's `#/health`. Card WI-2.
2. **(b) Portal per-repo page:** `#/health/<repo>`, `#/libs/<repo>`. New card under WI-1.
3. **(c) Sonar server read:** creds kind, `sonar.host`, the read, the screen changes. New card under WI-1.

Each step is shippable on its own and leaves the suite green.

**Relation to uncommitted work:** the WI-5…WI-11 fixes (Plan board, interview mode, plugins, Codex dropdown, repair
wording, golden questions, libraries table in Calidad) are in the working tree, not committed. They are committed first,
as their own conventional commits, before step (a) starts: step (a) moves their Calidad controls (golden questions,
libraries) into the board's rows instead of rewriting them.
