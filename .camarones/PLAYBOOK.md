# Camarones Documenter playbook 🦐

How an agent (Claude Code or Codex) documents a project **one unit per session**. `CONVENTIONS.md` defines the format;
this file defines the work. `CLI` below = `./camarones.command` (macOS/Linux) or `.\camarones.cmd` (Windows).

> *Camarón que se duerme, se lo lleva la corriente* — save progress early and often.

## Session protocol

1. **Load only what the unit needs.** Start with `docs/.work/handoff.md`, then the files it points to. Deep work fills
   the context window fast: prefer `graphify query "…"` / `graphify explain` / OpenAPI files over reading whole trees.
2. **Claim the unit**: `CLI plan start <id>`. If the unit is already `doing` it was interrupted (the user closed the
   session or the computer): read its checkpoints in `docs/.work/units/<id>.md`, `git status`/`git diff` of the umbrella
   and the unit's output files, and **continue** from the last checkpoint — never start over.
3. **Write as you go and checkpoint.** Persist findings to their final file (or a clearly named draft) during the
   session, not at the end. After each significant step run `CLI plan note <id> "done: … / next: …"` — that line is what
   the next session (or the wizard's "▶ Continue") resumes from.
4. **Too big for one session?** Split it: finish a coherent part, then
   `CLI plan add <id>:part2 "What remains" --type <type> --deps <id>` and mark the current unit done with a note.
5. **Close the unit**: `CLI plan done <id> --note "…"` (or `plan block <id> --note "reason"`; both make a local checkpoint
   commit), run `CLI check`, then `CLI checkpoint "<id>"` after the handoff below, and rewrite
   the `## Last session` section of `docs/.work/handoff.md`:
   ```markdown
   ## Last session — <unit id> (<date>, <agent>)
   - Done: …
   - Decisions / user answers: …
   - Pending / risks: …
   - Read first next time: <files>
   ```
6. **Ask what next.** Show `CLI plan next` (top 3–4 ready units) and ask the user which one — in Claude Code with
   AskUserQuestion (options = units + "stop here"), in Codex as a numbered list. Recommend a **new session** after heavy
   units (discovery, repo-wiki, flows) — the user reopens the Camarones Documenter wizard and picks "Next step".
7. Never write `x-confirmed`; never rewrite `<!-- human -->` blocks, `x-owner: human` files or confirmed pages silently.

## setup
Done by the wizard (`CLI setup`). If an agent lands here: run it, report missing prerequisites with the fix, mark done.

## discovery
Scope: one repo. Output: `docs/interview/discovery/<repo>.md` (`type: interview`). Read-only on code.
Truth order: OpenAPI/AsyncAPI → manifests → config → code; navigate with `graphify` (inside the repo) rather than grep.
Capture with evidence `<repo>:<path>#Lx-Ly`:
- **Stack**: language+version, framework (Spring Boot, Quarkus, Flutter, FastAPI…), build/test tools, Dockerfile.
- **Run/test locally**: commands, compose files, env vars, profiles, toolchain pins (`.sdkmanrc`, `.java-version`, `.nvmrc`,
  `.tool-versions`, `mvnw`/`gradlew`). JVM via SDKMAN: non-interactive shells need
  `source ~/.sdkman/bin/sdkman-init.sh && sdk env` (inside the repo) before `mvn`/`gradle`; prefer the wrappers when present.
- **Inbound**: REST routes/controllers, OpenAPI, GraphQL, listeners (`@RabbitListener`, `@KafkaListener`…), schedulers, app screens.
- **Outbound**: HTTP clients (Feign/RestClient/WebClient/dio), producers, exchanges/queues/topics/routing keys, 3rd-party APIs, auth (Keycloak/OIDC).
- **Data**: datasources, schemas, Liquibase/Flyway, entities, Firestore collections, caches.
- **Deployment**: Helm/K8s/ArgoCD/compose, CI files, environment configs.
- **Architecture & domain signals**: package structure (hexagonal?), aggregates, ubiquitous-language terms.
- **Unknowns** list.

## discovery-cross
Read every `docs/interview/discovery/*.md` (not the code again, except to confirm a doubtful link). Output
`docs/interview/discovery/cross-repo.md`: integration table (caller → callee, protocol, endpoint/topic, evidence),
producer↔consumer pairs, shared databases, candidate bounded contexts, candidate business flows
(entrypoint → hops → side effects), questions for the interviews. `.camarones/.cache/graph/graph.json` cross-repo edges are INFERRED —
confirm in code before stating them.

## interview
Three short units (`interview-context`, `interview-language`, `interview-history`). Show what was inferred, let the user
validate or correct; ≤4 questions per round. Topics per unit:
- **context**: bounded contexts (and which repo implements each, relationships: customer/supplier, ACL, shared kernel),
  external actors (people, systems), environments (which, where, differences).
- **language**: DDD glossary (term, definition, code name, context; which translations to keep), SLAs/NFRs.
- **history**: historical decisions (why, alternatives dropped) → ADR material; known debt; validation of the inferred
  integrations, flows (names/scope) and data ownership / shared DBs.
Record answers faithfully in `docs/interview/<YYYY-MM-DD>-<unit>.md`; unanswered → `docs/interview/open-questions.md`.
Unattended: do not ask; take the most reasonable reading and record every question.

## repo-brief
The foundation for one repo — after this unit the repo is useful on its own:
1. `<repo>/openwiki/INSTRUCTIONS.md`: the repo's role, bounded context, key glossary terms, integrations, what to emphasize.
2. C4: its container in `docs/architecture/model.c4` (create `likec4.config.json` + `model.c4` + `views.c4` if missing —
   or run `CLI arch-draft --save` to start from the static-scan draft)
   and `docs/architecture/repos/<repo>.c4` (components + `<repo_snake>_components` view). `CLI arch-validate` → ✓ Valid.
3. Managed blocks (CONVENTIONS §7): `<repo>/AGENTS.md` (stack, commands, interfaces, data, doc pointers, trust rule),
   `<repo>/CLAUDE.md` starting with `@AGENTS.md`, `<repo>/README.md` block with the Mermaid component diagram
   (`likec4 gen mermaid docs/architecture -o build/mmd` → `build/mmd/repos/<repo_snake>_components.mmd`).

## repo-wiki
Generate the OpenWiki of one repo. Preferred: OpenWiki MCP tools (`openwiki_begin` with the repo's absolute git root, mode
`init` if `<repo>/openwiki/` is missing else `update`, then follow the returned lifecycle). If the tools are not loaded in
this session (they load at session start from `.mcp.json`), tell the user to restart the agent in the umbrella folder, or
use the CLI in the repo when a provider key is configured: `openwiki code --init --print`. Never edit `openwiki/.claims`,
`.run.json`, indexes or OpenWiki-managed blocks.

## arch-system
If `docs/architecture/first-look.md` exists, the C4 files started as a static-scan draft: verify and refine them rather
than starting over.
`docs/architecture/model.c4` + `views.c4`: actors, external systems, every container (services, apps, DBs, brokers, topics),
`index` (context) and `containers` views; `#ai-draft` on unvalidated elements, `#confirmed` on validated ones.
Write `docs/overview/system.md` (purpose, context diagram in words, how to navigate) and `docs/index.md` (entry point).

## domain
`docs/domain/bounded-contexts.md` (context map + repo mapping), `glossary.md`, `actors.md` from the interviews.

## data
`docs/data/<store>.md` per datastore: `erDiagram`, ownership table (table → writers → readers), migration source,
`#shared-db` tag in C4 + warning section when shared.

## deployment
`docs/architecture/deployment.c4` + `deployment view deploy_<env>` per environment; `docs/deployment/environments.md`.

## decisions-quality
`docs/decisions/NNNN-<slug>.md` (ADR; `Status: accepted` only when the user said it was decided, else `proposed`),
`docs/quality/slas.md`, `docs/quality/tech-debt.md`.

## flows-catalog
Propose the business flows (from cross-repo discovery + interviews), let the user pick/rename/add, then create one unit
per flow: `CLI plan add flow:<slug> "<Flow name>"`. Write `docs/flows/index.md` listing them.

## flow
One flow: `docs/flows/<slug>.md` per CONVENTIONS §6 (sequence diagram always; flowchart only with branching rules; state
diagram for lifecycles) + `dynamic view flow_<slug>` in `views.c4`. Every step cites entrypoint + evidence.

## i18n
Spanish for every canonical page written/changed since the last i18n pass (`CLI status` lists `es:missing/outdated`),
under `docs/i18n/es/<same path>` (repo wikis: `docs/i18n/es/repos/<repo>/<page>`); then `CLI translated <files>`, `CLI llms`.

## portal
Wizard: `CLI portal` then `CLI up`. Check `/`, `/architecture/`, `/code-graph/` and a flow page.

## ci
Wizard: `CLI ci` installs the umbrella pipeline; per-repo snippets are in `.camarones/ci/`. Propose them; the user applies
them to service repos.

## confirm
Human review in the wizard ("✅ Review & verify": page by page, confirm or request changes). An agent may only *propose*
which pages come straight from the user's answers and run `CLI confirm <files> --by <name>` after an explicit yes; if
the user says something is wrong, record it with `CLI feedback <file> "<comment>" --by <name>` (→ `review-fixes`).

## handover
`CLI mark-documented`; commit on branch `docs/camarones` in the umbrella and each touched repo (ask before pushing / MRs);
final summary: counts per type, drafts left, open questions, how to update (`update` below), tutorial link.

## update
Recurring after the first full pass (also what CI runs):
1. `CLI sync`, `CLI changes`. Nothing changed and `CLI check` passes → report "up to date".
2. Repo wikis of changed repos: OpenWiki `update` (skip if that repo's CI already did it).
3. Map changed files to docs via `x-sources`; update affected pages and C4 (interfaces, dependencies, deployment).
   New capability → draft flow + open question.
4. Refresh managed blocks if stack/commands/interfaces/diagram changed.
5. Cleanup (CONVENTIONS §9): orphan drafts deleted (with translations and C4 elements); orphan confirmed pages → question.
6. Translations of changed pages + `CLI translated`; `CLI arch-validate`, `CLI llms`, `CLI check`, `CLI mark-documented`.
7. Short report: pages created/updated/deleted, confirmed pages needing re-confirmation, new questions.

## review-fixes
Input: `docs/.work/review-feedback.md`. Each `- [ ]` line is a human review comment on one page (written in the wizard's
"Review & verify" or with `CLI feedback`). For each: read the page and the code it describes; if the human is right, fix
the page (and its `docs/i18n/es/` translation, then `CLI translated`); if the code contradicts the comment, keep the page,
add the evidence, and ask the user. Tick the line `- [x]` with a short "→ what changed". A page you edited is a draft
again: tell the user it is ready for another review. Never write `x-confirmed`.

## doc-fixes
Triggered from the wizard's "Documentation status". Run `CLI check` and `CLI status`, then fix, in this order:
1. `ERROR`s (frontmatter, broken links, invalid C4 → `CLI arch-validate`).
2. Orphans: `x-sources` that no longer exist → find where the code moved (`graphify query`, `git log --follow`) and
   update the page and its sources, or remove the claim.
3. `needs-reconfirm` pages: diff what changed since confirmation, verify it against the code, and write a short summary
   for the user of what changed (they re-confirm it in the wizard). Do not revert human edits.
4. Missing / outdated translations → translate, then `CLI translated <files>`.
Finish with `CLI llms`, a clean `CLI check` and `CLI checkpoint "doc-fixes"`.
