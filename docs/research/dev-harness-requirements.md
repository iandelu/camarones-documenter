# Development harness — requirements (elicitation, 2026-10-24)

Status: **draft**, from a question-by-question session with the maintainer. Input: the external spec v0.1 and its gap
analysis ([spec-v0.1-gap.md](spec-v0.1-gap.md)). Each decision has an ID so later designs can cite it. Nothing here is
designed yet; open questions are at the end.

## 1. Vision and scope

| ID | Decision |
|---|---|
| V1 | Camarón goes beyond documenting: it **executes code changes with guards** (agent edits code in a worktree, the kit verifies, nothing closes without evidence and human approval). |
| V2 | For the **whole team** (portal to read, app to work, CI). |
| V3 | Any kind of project (legacy, own microservices, greenfield): nothing stack- or phase-specific in the model. |
| V4 | Delivered in **small, compatible 4.x steps**; 3.x/4.x projects keep working (AGENTS.md 2.3). |
| V5 | First step: the **board without AI** (AGENTS.md priority 1). Then all runners through the `Runner` port; JVM (Maven/Gradle) is the first verified stack. |

## 2. Work items and the board

| ID | Decision |
|---|---|
| W1 | Work lives in **cam-docs, folder `backlog/`**, in the **Backlog.md file format** (MIT) so its CLI opens the same board. We do not depend on its binary. |
| W2 | Content (what, criteria, links) in one `.md` per item; volatile state (column, order, assignee) in **`board.yaml`, which is authoritative**. The item's frontmatter carries a copy of the status that the kit keeps in sync; edits made outside (e.g. Backlog.md CLI) are **overwritten by board.yaml on sync, with a warning**. |
| W3 | Levels: **epic + story** (plus bug, spike, task). Epics use whatever Backlog.md uses for parents/milestones — verify in its source before designing. |
| W4 | IDs: readable `WI-N` (Backlog.md `id`) **plus a hidden short unique `x-uid`**. If two branches create the same N, sync renumbers the newer one and fixes references by uid. |
| W5 | **Fixed columns** (backlog / ready / in progress / in review / done / blocked), written into Backlog.md's `config.yml` so both tools agree. Fixed because execution hooks onto them. |
| W6 | Fields in v1: acceptance criteria with IDs (`AC-1`…), links to docs by `x-id`, affected repos, priority P0–P3, labels, assignee. No story points. |
| W7 | Board moves are versioned, **grouped into the next sync** (not one commit per drag). |
| W8 | Merge: one line per card in `board.yaml`, ordered by id, and a **kit merge driver** that merges per card and, per field, keeps the latest change (timestamped); what cannot be merged is shown. Limit: git only uses a driver registered in each clone's local config — the kit registers it on every machine (like hooks); without the kit a person sees a normal conflict. |
| W9 | Order inside a column: a **rank between neighbours** (LexoRank-style), so moving one card does not renumber others. |
| W10 | WIP limits **warn**, never block. |
| W11 | Done items are **archived after N days** (configurable) into Backlog.md's archive; still searchable and linkable. |
| W12 | Kit templates per kind (story: as/want/so + criteria; bug: steps, expected/actual, environment; spike: question, timebox, output; epic: goal + linked feature), es and en. Items are written in the project's language, never translated. |
| W13 | Default **Definition of Done** from the kit (required checks green, docs reconciled and confirmed, PR approved), extended per project, stored in Backlog.md's `definition_of_done`. |
| W14 | Backlog.md's own `docs/` and `decisions/` folders are **not used**: docs live in cam-docs `docs/`; the check warns if files appear there. |
| W15 | Scale target: **hundreds** of active items (~500), board opens < 1 s, plain files, no index. |

## 3. Interfaces

| ID | Decision |
|---|---|
| U1 | CLI **`camaron board`** (add / list / move / show…). Free today (the whiteboards have no CLI command). |
| U2 | Kanban in the **portal and the app**. The portal edits (writes the files; the next sync commits). |
| U3 | UI names: es **Tablero** (Kanban) / **Pizarras** (Excalidraw); en **Board** / **Whiteboards**. Only the tab labels change, not routes or files. |
| U4 | Agents **read and propose** through MCP: they read items and criteria and may create items as `draft` that a person accepts; they never move columns. |
| U5 | **On by default in new projects**; existing projects enable it with a command. |
| U6 | People without git (PM, business) are served later by a **shared team portal** (team-server spike), not in the first delivery. |
| U7 | Doc findings (drift, stale pages, `TODO(question)`, OSV vulnerabilities) show as **suggestions**; one click turns one into an item. |
| U8 | The documentation plan (`plan.yaml`) stays **separate** (Pipeline view); the board is for product/code work. |
| U9 | `camaron uninstall` **asks** whether to keep or delete `backlog/` (it holds human work). |
| U10 | A portal edit is attributed to the **machine's git user**: the sync commits as them and `board.yaml` keeps who/when per field (the merge driver uses it). |
| U11 | Views: **Kanban** (drag and drop and keyboard), **list** (sortable table), **by epic** (stories and progress as counts, never invented percentages). |
| U12 | Card detail in v1: goal + criteria + DoD; **knowledge** (linked docs with their trust state, flagged when they changed since linked); **history** (who moved what, from `board.yaml` and git); empty **Plan / Runs / Evidence** tabs that say which version brings them. |
| U13 | Filters in v1: repo, epic and label, **docs state** (items whose linked docs are suspect or unconfirmed). |
| U14 | **"Create item" from a doc section** (like anchored comments): the item is born linked to that `x-id`, and the page gets its `x-id` if it had none. |
| U15 | Suggestions (U7) live in a separate **Suggestions tray** next to the board: accept = new backlog item; dismiss = hidden until the finding changes. |
| U16 | The wizard does not change: the board is explained in the **tutorial** only. |
| U17 | No board validation in CI; checks run locally on sync. |
| U19 | The local portal writes to the board **only with the machine's token** (opened by the app or the local CLI), like machine work today; another tab or process cannot. |
| U18 | No push notifications: a **"since last time"** summary when the portal or app opens. |

## 4. External trackers

| ID | Decision |
|---|---|
| T1 | None needed to start; then **import** and **export**. No two-way sync. |
| T2 | First tracker: **Jira Data Center/Server, through CSV files only** — import a Jira CSV export, export a CSV Jira can import. No API, no token, works offline. |
| T3 | Import is one-way and once: **Camarón takes over**; the item keeps the Jira key as a reference. |
| T4 | Imported: epics, stories and bugs (title, description, status mapped to the fixed columns, priority, labels, assignee). |
| T5 | After export nothing is synchronised: changes made in Jira afterwards are not tracked. |
| T6 | The Jira key is kept in a frontmatter field **`x-jira: PROJ-123`**, shown as a link when the Jira URL is configured. |

## 5. Knowledge links

| ID | Decision |
|---|---|
| K1 | Intent lives in a new doc type **`feature`** (`docs/product/features/<slug>.md`, draft/confirmed like any page). Legacy: AI drafts features from code and interviews, people confirm. Greenfield: people write them first. |
| K1b | Feature sections: motivation and users; scope and out of scope; **business rules with their own IDs** (`FEAT-012.R1`) so criteria and tests cite them; links to flows, domain, decisions and C4 elements. |
| K1c | Features **link, never replace**, domain and flow pages: a feature is intent (what and why), flows and domain are what the code does today; a difference between them is drift. |
| K2 | Items link docs by **stable `x-id`** in frontmatter (`FEAT-…`, `DEC-…`…). A page gets its `x-id` **the first time something links it**; new pages are born with one. Adding it touches frontmatter only; `x-confirmed.body_sha` hashes the body, so confirmation survives. |
| K3 | Docs are updated **inside the same change**: the plan lists the pages, the agent edits them in a cam-docs worktree, code and docs PRs are linked, and the item is not done until the docs are confirmed. |
| K4 | Value drift ("the decision says 3 retries, the code does 5") three ways: decisions cite the constant/config key in `x-sources` (no AI, goes `suspect` when the value changes); a periodic AI review proposes findings (inferred); and at planning time the decisions in scope are checked. |

## 6. Executing a change

| ID | Decision |
|---|---|
| E1 | The coding agent runs **headless** (kit launches, limits, collects the diff) **or interactive** (a person drives it; the kit prepares context and verifies). Interactive runs are verified **when the agent's session closes**; a session that closes with no changes **asks**: discard the worktree, reopen the session, or leave it. |
| E2 | Plan: **the person writes it, the AI improves it, the person approves it**. |
| E3 | A multi-repo item is **one change, N linked PRs**: a worktree per repo, joint verification, no PR opens if one fails. |
| E4 | Git: **own branch + PR after an explicit click**. Never merge to main. |
| E5 | The board follows the PR with fixed rules: running → in progress; PR open → in review; verification failed → blocked; PR merged + docs confirmed → done. Manual moves are allowed except into done. |
| E6 | PR state is read **on sync** (forge API, `creds.py` token) and, when configured, by a **CI job**. |
| E7 | Budget (time, iterations, cost) is set **per machine** (`camaron config`): each person pays their own account. |
| E8 | After a crash: the run is **interrupted, its worktree kept**; resume or discard. Never counted as green. |
| E9 | Service worktrees in **`<workspace>/.cw/<item>/<repo>`**, next to today's docs-unit worktrees, so `uninstall` and `traces` already cover them. |
| E10 | Branch names from a **template** in `workspace.yaml`, default `cam/{id}-{slug}`. |
| E11 | Concurrency: **several runs at once, one writer per repo** (two items touching the same repo queue). |
| E13 | During a run the agent reads **only the worktrees in scope** and the docs through MCP behind the freshness gate; the rest of the workspace is not there. |
| E14 | KPIs (extending `harness/kpis`): time from plan approval to PR ready; share of runs needing human intervention and why; cost per item; traceability of done items (criterion → test → evidence, docs confirmed). |
| E12 | Evidence is valid for its base SHA: if main moved, opening the PR **merges main in and re-runs the required checks**. |

## 7. Verification

| ID | Decision |
|---|---|
| C1 | Evidence: build/tests **detected** by the kit (mvnw, gradlew…) and **declared** per repo in `workspace.yaml`, run by the kit in the worktree (exit code, log, SHA); each **acceptance criterion linked to a test**; the repo's own **linters**. |
| C2 | Verification plan: the **required base comes without AI** (repo profile + risk signals + criteria); the AI suggests additions the person accepts or drops. |
| C3 | Architecture: run existing rules (ArchUnit…); **generate rules from the confirmed C4** (ArchUnit / dependency-cruiser / import-linter), offered as a **suggested board item** per repo and executed like any item; and a **kit check** comparing the code graph with the confirmed C4 without touching the repo. |
| C3b | Per-repo checks in `workspace.yaml`, additive: `repos[].verify: {profile: spring-maven, extra: [{id, run: [argv…]}]}`. The profile brings the detected compile/unit/integration/lint; `extra` adds commands as argv, never a shell string. |
| C1b | Criterion ↔ test: the **item lists the tests that cover each criterion** (`Class#method`); the code does not change. |
| C1c | Results are read **per test from JUnit XML** (surefire, failsafe, Gradle), so each criterion's tests can be checked. |
| C1d | A test that fails and then passes is retried **once** and marked **flaky**; flaky still blocks until a person accepts it with a reason. |
| C1e | A check the machine cannot run (e.g. Testcontainers without Docker) is an **error and blocks**; `doctor` says how to fix it. Never green. |
| C4 | Evidence storage: a small **versioned summary** (check, result, SHA, log hash) in the item and the PR; full logs in the machine's local cache. |
| C5 | Exploratory testing by an agent: **later**. |
| C6 | Sonar: **not now** (full analysis needs a server). Record in `tooling-candidates.md`. |

## 8. Risk, approvals, limits

| ID | Decision |
|---|---|
| R1 | Risk score: the kit's **default signals and weights** (public contract, SQL migration, auth/secrets path, messaging, 2+ repos, unknown consumers), adjustable in `workspace.yaml`; the explanation (which signals added up) is always shown. Thresholds from the spec: 0–2 low, 3–5 medium, ≥6 high; an unknown critical signal counts as high. Calibrated with use. |
| R1b | Extra signals, from data the kit already has: **git hotspots** and single-owner files (`history.py`), and **known vulnerabilities** or new dependencies (`osv`, `inventory`). |
| R2 | Human approval at: **plan before running**, **diff before the PR**, **doc changes** (confirm, as today) and **owner on high risk**. |
| R3 | Plan and diff are approved **locally** by whoever is at the machine (recorded with their git user); team and owner approval **is the PR**: the kit requests CODEOWNERS reviewers and flags high risk in the description. |
| R4 | Limits in **three layers**: before (clean worktree — untracked files such as `.env` are not there; sparse-checkout for tracked forbidden paths; environment without tokens), during (per-runner `allow_tools`, PreToolUse hooks where the agent supports them, OS sandbox where available), after (diff gate: forbidden paths, files outside the approved scope, gitleaks on the diff; evidence produced by the kit, never the agent's text). Layers 1 and 3 are guaranteed on every OS; layer 2 depends on agent and OS and the UI says so. |
| R5 | If the diff gate fails, the agent gets the exact reason and **retries within its budget**; then the change is blocked. |
| R6 | **PreToolUse hooks** in the worktree for agents that support them (Claude Code today), through the mechanism `lib/hooks.py` and trust already know. |

## 9. How we know the first delivery works

- Sandbox (PetClinic): create an epic and stories linked to docs, move them, close and reopen, and the Backlog.md CLI
  shows the same board.
- Real use: `usage.py` counts items created/moved per week and from where (portal, app, CLI).
- Traceability: share of items with criteria and at least one link to a confirmed page.
- Everything works with no network and no agent.

## 10. Delivery

One **minor version per piece**, each with its README and tutorial update (AGENTS.md 5.1):

1. Board without AI (W*, U*, T* CSV import/export).
2. `feature` pages and `x-id` (K1, K1b, K2).
3. Risk score and verification plan, first in the PR comment (R1, C2).
4. Minimal execution: one item → agent in a worktree → checks → PR with evidence (E*, C1, C4, R2–R6).
5. Then: multi-repo groups (E3), docs inside the change (K3), architecture rules (C3), value drift (K4).

## 11. Open questions (next rounds)

1. Backlog.md internals: frontmatter fields, epics/parents, archive folder, whether `id` accepts our scheme — read its
   source at a pinned version.
2. Jira CSV column mapping (Data Center export headers, custom fields).
