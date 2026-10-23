# Roadmap: a solid base (portal that works, facts before AI)

Plan of 2026-10-23, after the 4.27 portal was tried on a real project and on the sandbox. IDs `S1`–`S18` are stable.
Same rules as [roadmap.md](roadmap.md): one small PR per item, failing test first, three OSes, `es` + `en`, README and
tutorial in the same commit, `VERSIONS["kit"]` bumped when projects see a change.

Order follows AGENTS.md §1: fix what is broken, then add **facts the kit extracts without AI** (libraries, CVEs, data
schemas), then let people confirm them on screen, then the screens that measure it.

## Diagnosis (sandbox, kit 4.27.0, 2026-10-23)

Set up with `init`, `detect`, `arch-draft --save`, `plan sync`, `radar`, `llms` (no AI), portal on `up --foreground`.

| Area | What happens | Cause |
|---|---|---|
| Ask: retrieval | "what database does it use" returns `overview/tooling.md`; `search?q=database` returns nothing although `architecture/first-look.md` says PostgreSQL and MySQL | Lexical BM25 only (`docs.search`): no synonyms (database ↔ PostgreSQL/MySQL/Firestore), no ES ↔ EN, `.c4` model not indexed |
| Ask: noise | "qué base de datos usa" returns `guides/tutorial.md` | The kit's own guides (`guides/tutorial.md`, `guides/self-hosted-runner.md`) are indexed as project docs |
| Ask: AI answer | First call > 60 s with no feedback, the next 3.4 s; **$0.21 per answer** | `answers.answer` runs `claude -p` with the default model in the workspace (loads its CLAUDE.md, MCP, hooks); `--allowedTools ""` does not deny read-only tools (to verify); no timeout shown to the user |
| Ask: UI | A failed `api/ask` shows nothing; the TL;DR is rendered twice | `Ask.run` has no `catch`; `api_ask` sends `tldr` and a `text` that already contains it |
| Wikis | No Generate button: "no wiki for this repo (choose repos in the wizard → Wikis)"; CLI: `no INSTRUCTIONS.md yet — run its repo-brief unit first` | `wiki.js` shows the button only when the repo is `chosen` **and** `ready`; `ready` needs the AI repo-brief. A fresh install can never generate a wiki from the portal |
| Boards: name | Starting from a C4 view leaves the name empty | `Boards.jsx` does not derive it from the view |
| Boards: layout | Boxes in a 3-column grid in model order, straight centre-to-centre arrows crossing boxes, no relation labels, clipped titles (see the enjoy-the-club screenshot) | `boards.sketch`: grid layout, `label` is not an Excalidraw field (labels are bound text), fixed 240 px width, parallel relations not merged |
| C4 | Read-only in the portal; `#ai-draft` tags can only be removed by editing `.c4` files | No element editor or confirm action |
| KPIs, CI | CLI only (`kpis`, `stats`, `ci`) | No portal view |
| Libraries, CVEs | Not available. `radar` detects ~60 known tools, not the dependency list | No manifest parser, no vulnerability source |
| Data schemas | Only the AI `data` unit (`skeletons/data-model.md`) | No static extraction; NoSQL (Firestore, Mongo) not covered |

Claude Code integration: good at the workspace root (`AGENTS.md`/`CLAUDE.md`, three skills, the `camarones` MCP in
`.mcp.json`, optional method hooks). Weak inside a single repo: Claude Code finds the parent `CLAUDE.md`, but not the
MCP server (`.mcp.json` lives in the workspace root) and the repo pointer is opt-in. Headless runs launched by the kit
(Ask AI, wiki) inherit the workspace's config and the default (most expensive) model.

## Phase 0 — make what exists work

Done 2026-10-23 (kit 4.28.0–4.30.2), checked on the sandbox: S1 (4.28.0), S2 (4.28.1), S3 (4.28.2), S4 (4.29.0),
S5 (4.29.1), S6 (4.30.0). Two fixes the sandbox run turned up: a wiki run connects OpenWiki's MCP to the agent when
setup did not (4.30.1), and `first-look.md` cites the files it was read from, so the freshness gate lets agents and
Ask's AI answer use it on a fresh install (4.30.2). Measured: the same AI answer went from $0.21 to $0.0016 (haiku,
6 s), and "qué base de datos usa" now answers PostgreSQL and MySQL with the citation.

Not done from these items: indexing the `.c4` model itself in search (S1; first-look carries the same facts) and
"nothing found" listing the closest titles (S1). New: `GET /api/tree` takes seconds because `wiki_engines()` runs
`npm ls -g` twice on every call; cache it per process.

| ID | Change | Test first |
|---|---|---|
| S1 | **Ask retrieval.** Index the C4 model (titles, technology, descriptions) and the facts pages of S5/S8; a synonym table in a data file (`database` → PostgreSQL, MySQL, Mongo, Firestore…, ES ↔ EN pairs from the glossary); kit guides out of project search unless the query names the kit; "nothing found" lists the closest page titles | Fixture: "what database does it use" and "qué base de datos usa" both return the page naming PostgreSQL first; a kit guide never outranks a project page |
| S2 | **Ask AI answer.** Cheapest model of the bounded tier by default (`ask.model` overrides), no tools at all, a temp empty `cwd` so project hooks/MCP do not load, 90 s timeout, the cost shown under the answer; UI catches errors and shows the busy time | Built argv has no tools and the temp cwd; a fake runner that sleeps past the timeout returns a readable error; `Ask` renders an error on a 500 |
| S3 | **Ask UI.** TL;DR once; the home page box hidden in the static portal | vitest on `Ask`; `api_ask` text never starts with the TL;DR |
| S4 | **Wikis from the portal.** Generate is always offered when an engine exists. Missing brief → "Write a starter brief (no AI) and generate": `INSTRUCTIONS.md` from `radar` + `arch-draft` (role, stack, entry points, neighbours), marked draft for repo-brief to improve. Repo not chosen → the button adds it to `wikis` and re-adds the plan unit. No engine → the exact fix (`openwiki auth configure …` or install Claude Code). The job log streams on the page | `wikis()` reports `can_generate` + `reason` for each case; the starter brief passes `wiki_brief_ready`; a dropped `repo-wiki` unit comes back as `todo` |
| S5 | **Board name.** Choosing a view fills `<view-title>-draft` (slug), `-2`, `-3` if taken; a name the user typed is kept | vitest: view pick fills the name; existing name gets a suffix; typed name untouched |
| S6 | **Board layout.** Layered layout without a new dependency: rows by C4 kind (actors → apps/web/mobile → services/functions → stores/queues → external), order inside a row by barycentre to cut crossings; box width from the title; Excalidraw elbow arrows bound to both boxes; relation label as bound text; parallel relations merged into one arrow, `A↔B` as one double-headed arrow | pytest on `sketch()` for a 9-element fixture shaped like the screenshot: no overlapping boxes, every arrow bound at both ends, every label a bound text, crossings ≤ the grid layout's |

## Phase 1 — facts without AI

| ID | Change | Test first |
|---|---|---|
| S7 | **Library inventory.** `lib/inventory.py`: direct dependencies per repo from manifests and lockfiles — Maven (`pom.xml`, properties, BOM imports best effort), Gradle (version catalog, lockfile), npm/pnpm/yarn, Python (`pyproject`, `uv.lock`, `requirements*.txt`), Go, .NET, Composer, Cargo. Each row: repo, ecosystem, name, version, scope (runtime/test/build), category from `lib/data/dep-categories.yaml` (framework, cache, security, data, messaging, testing, observability, http, cloud-sdk, ui, build, language-runtime). Writes `docs/.work/inventory.json` and a generated block in `overview/dependencies.md`; runs in `setup` and `radar` | Golden output for PetClinic REST + Angular fixtures; unknown libraries land in `other`, never dropped; a lib used by two repos with two versions is flagged |
| S8 | **CVEs.** OSV-Scanner (tooling-candidates N2, 🟢) as a pinned binary, **offline database** by default (`--offline-vulnerabilities`, DB downloaded once to the cache); online mode opt-in per machine because it sends package coordinates to osv.dev. Missing binary → inventory without CVEs and a note, never a failure. Findings merged into `inventory.json` (id, severity, fixed version) | Canned OSV JSON → the right rows marked with severity; binary absent → exit 0, `vulns: null`; online mode never used without the machine flag |
| S9 | **Libraries view.** Portal tab: matrix library × service with filters (category, language, service, scope, "only vulnerable"); CVE rows and badges in red with severity and the fixed version; version drift between services in amber; the same table as a `:::` live table for pages | vitest on the filter reducer; pytest `GET /api/inventory` on a fixture |
| S10 | **Data schemas.** `lib/schemas.py`, per store found by `arch-draft`: SQL from Flyway/Liquibase (SQL, XML, YAML), `schema.sql`, JPA `@Entity`/`@Table`/relations, Prisma, TypeORM, SQLAlchemy, Django; NoSQL from Mongo `@Document`/Mongoose, **Firestore** (`collection('…')`/`doc('…')` paths, converters and TS interfaces, `firestore.rules`, `firestore.indexes.json`), DynamoDB tables in CDK/Terraform. Output `data/<store>.md` draft from the `data-model` skeleton: `erDiagram` for SQL, a collection tree with document fields for NoSQL, `x-sources` to the files. The AI `data` unit then completes ownership and meaning instead of starting blank | Fixtures per source type → golden pages; a confirmed page is never rewritten (§2.3) |
| S11 | **Data view.** Portal tab: pick a store → diagram, tables or collections with fields, who reads/writes it (relations from the C4 model) | pytest on `/api/schemas`; vitest on the view |
| S12 | **Firebase in `arch-draft`.** `firebase.json`, `functions/`, `firestore.rules`, `storage.rules`, Flutter/React Native/web apps → containers (Cloud Functions, Firestore, Storage, Hosting) and relations, so projects like enjoy-the-club get a correct first C4 | Fixture Firebase monorepo → expected `model.c4` |

## Phase 2 — confirm the C4 on screen

| ID | Change | Test first |
|---|---|---|
| S13 | **C4 element panel.** Click an element in a view → side panel with title, kind, technology, description, tags and relations. Edit → `lib/c4edit.py` rewrites only that element block in its `.c4` file, runs `arch-validate`, and refuses to save an invalid model. **Confirm** removes `#ai-draft` and adds `#confirmed` with `confirmed-by`/date metadata; "Confirm view" does it for every element in the view. Add/remove a relation from the panel. Freshness L3 already marks confirmed elements suspect when their sources change | Round-trip: edit one element, every other byte of the file unchanged; invalid edit → 400 and file untouched; confirm on a fixture view removes every `#ai-draft` in it; a fragment file under `fragments/` is edited in place under the `c4-model` lock |

## Phase 3 — screens that measure it

| ID | Change | Test first |
|---|---|---|
| S14 | **KPIs view.** From `kpis --json` and `stats --json`: coverage per repo (confirmed / draft / needs-reconfirm), suspect pages, runs (time, tokens, cost per unit and month), AI-draft edit distance, eval score trend, Ask and search hit rate and **the questions that found nothing** (each one can become a doc task) | pytest `/api/kpis` from fixture events; zero-result queries are recorded without personal data |
| S15 | **CI view.** What is installed (umbrella pipeline, `docs-fresh`, per-repo snippets), the last `check` and `fresh` results, buttons to generate the GitHub/GitLab pipeline, the snippet per repo to copy, the runner guide; the last pipeline status through `gh`/`glab` when installed, hidden otherwise | pytest `/api/ci` with and without the files; no network in tests |

## Phase 4 — Claude Code and the safety net

| ID | Change | Test first |
|---|---|---|
| S16 | **Claude Code inside each repo.** `setup` registers the `camarones` MCP for every repo path with `claude mcp add --scope local` (stored in the user's Claude config, nothing written in the repo); `uninstall` removes it; `doctor` reports it. Verify on the sandbox with `ab --qa` started from inside `spring-petclinic-rest` | argv of the registration and removal; `traces` exit 0 after uninstall; sandbox: the in-repo session calls `search_docs` |
| S17 | **Portal smoke tests.** API-level pytest per view on the fixture workspace (ask, wikis, boards, inventory, schemas, kpis, ci) plus one Playwright smoke on the sandbox under the `e2e` marker that clicks through every tab | The tests of S1–S15 run in CI; the smoke fails on an empty view or a console error |
| S18 | **Empty states.** Every view says what is missing and offers the one button that fixes it (build C4, generate wiki, run inventory…), never "go to the wizard" | vitest per view with an empty API response |

## How the documentation becomes solid

1. **Facts first, generated and cited:** stack (`radar`), libraries and CVEs (S7–S8), data schemas (S10), C4 draft
   (S12), endpoints (OpenAPI blocks), config and env vars (X3 blocks). No model, reproducible, refreshed by CI.
2. **AI explains the facts instead of rediscovering them:** discovery, repo-brief and `data` read those pages and cite
   them in `x-sources`; their prompts say so.
3. **People confirm on screen:** pages (exists) and C4 elements (S13).
4. **Measure:** ten golden questions written at the start (`eval draft`/`confirm`), e.g. "which database does each
   service use?"; `eval` after each phase. Today's Ask failure is exactly such a question failing. S14 shows the
   trend and the questions nobody could answer.

## Order

S1–S3 → S4 → S5–S6 → S17 (API part, grows with each item) → S7–S9 → S10–S12 → S13 → S14–S15 → S16 → S18.
