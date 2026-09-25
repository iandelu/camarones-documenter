# Camarones Documenter playbook 🦐

How an agent (Claude Code or Codex) documents a project **one unit per session**. `CONVENTIONS.md` defines the format;
this file defines the work. `CLI` below = `camarones` (global install; legacy per-project copies: `./camarones.command`
or `.\camarones.cmd`).

> **Layout.** Everything the kit writes lives in `cam-docs/` (its own git repo, next to the service repos). Paths in
> this file are relative to `cam-docs/`; repos are its siblings (`../<repo>` from `cam-docs/`, `<repo>/` from the workspace
> folder agents run in). Never write kit files into a service repo — the only exception is the optional one-block
> pointer in `<repo>/CLAUDE.md` that the kit itself manages.

> *Camarón que se duerme, se lo lleva la corriente* — save progress early and often.

## Session protocol

1. **Load only what the unit needs.** Start with `docs/.work/handoff.md`, then the files it points to. Deep work fills
   the context window fast: prefer `graphify query "…"` / `graphify explain` / OpenAPI files over reading whole trees.
2. **Claim the unit**: `CLI plan start <id>`. If the unit is already `doing` it was interrupted (the user closed the
   session or the computer): read its checkpoints in `docs/.work/units/<id>.md`, `git status`/`git diff` of `cam-docs/`
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
   **Autopilot** (`CLI autopilot`, or "Autopilot" in the wizard's ready-units list) skips this step. An outer loop
   starts every ready agent unit in its own fresh, unattended session (`claude -p … --dangerously-skip-permissions`
   or `codex exec --approve-for-me …`). If one agent hits its usage limit, the loop switches to the other; if both are
   limited, it waits. It never runs interview units or wizard steps (setup, portal, ci, confirm), and it stops when
   only those are left, when a unit fails, or when a unit ends without `plan done`/`plan block`. In an autopilot
   session you close the unit as usual (step 5), and questions go to `docs/interview/open-questions.md`.
7. Never write `x-confirmed`; never rewrite `<!-- human -->` blocks, `x-owner: human` files or confirmed pages silently.

## setup
Done by the wizard (`CLI setup`). If an agent lands here: run it, report missing prerequisites with the fix, mark done.
Agent config (`.claude/`, `.codex/`, `.agents/`, `.mcp.json`, AGENTS.md/CLAUDE.md) is written to `cam-docs/` and linked
from the workspace folder; code graphs go to `graph/<repo>/`. Service repos are not touched. The `full` profile also
installs the quality gate (mermaid-cli, gitleaks) that `CLI check` uses; without it those checks are skipped with a WARN.

## discovery
Scope: one repo. Output: `docs/interview/discovery/<repo>.md` (`type: interview`). Read-only on code.
Truth order: OpenAPI/AsyncAPI → manifests → config → code; navigate with `graphify query "…" --graph graph/<repo>/graph.json`
(or the `camarones` MCP tool `repo_graph`) rather than grep.
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

## quick-overview
This is the short route. Use the completed discovery notes and verify their sources in the code.
Write `docs/index.md` and `docs/overview/system.md`: purpose, repositories, how to run locally,
one representative flow (a Mermaid sequence diagram), evidence and unanswered questions.
Translate these two pages into `docs/i18n/es/` and run `CLI translated` for them.
No OpenWiki, graphify, C4 or git hooks are required. Do not install them or edit service repositories.
Keep all pages as drafts for human review. The next unit builds the portal.
For discovery and later updates in the quick profile, inspect files directly when graphify is absent.

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
- **language**: DDD glossary (term, definition, code name, context, synonyms to avoid; which translations to keep), SLAs/NFRs.
- **history**: historical decisions (why, alternatives dropped) → ADR material; known debt; validation of the inferred
  integrations, flows (names/scope) and data ownership / shared DBs.
Record answers faithfully in `docs/interview/<YYYY-MM-DD>-<unit>.md`; unanswered → `docs/interview/open-questions.md`.
Unattended: do not ask; take the most reasonable reading and record every question.

## repo-brief
The foundation for one repo — after this unit the repo is useful on its own:
1. `wikis/<repo>/INSTRUCTIONS.md` (the repo sees it as an untracked `openwiki/` link): the repo's role, bounded context,
   key glossary terms, integrations, what to emphasize.
2. C4: its container in `docs/architecture/model.c4` (create `likec4.config.json` + `model.c4` + `views.c4` if missing —
   or run `CLI arch-draft --save` to start from the static-scan draft)
   and `docs/architecture/repos/<repo>.c4` (components + `<repo_snake>_components` view). `CLI arch-validate` → ✓ Valid.
3. Repo brief (CONVENTIONS §7): `docs/repos/<repo>/brief.md` — stack, how to build/test/run, interfaces, data owned,
   doc pointers and the Mermaid component diagram (`likec4 gen mermaid docs/architecture -o build/mmd` →
   `build/mmd/repos/<repo_snake>_components.mmd`). Do not edit the repo's own README/AGENTS.md/CLAUDE.md.

## repo-wiki
Generate the OpenWiki of one repo. The unit exists only for the repos the user chose (`wiki: true` in
`.camarones/workspace.yaml`; wizard → 📚 Wikis → choose) and needs `wikis/<repo>/INSTRUCTIONS.md` from repo-brief. Keep
the wiki about the repo's internals: the cross-repo domain, flows and C4 live in `docs/` — do not restate them.
Simplest: `CLI wiki <repo>` (headless: OpenWiki with a provider key, else Claude Code / Codex through the OpenWiki MCP;
the portal's Wikis tab runs the same; one run at a time, and a batch stops when the engine is out of quota or logged
out). Doing it yourself with the OpenWiki MCP tools:
first `CLI wiki <repo> --open` (OpenWiki refuses the `openwiki/` symlink, so this makes it a real folder), then
`openwiki_begin` with the repo's absolute git root, mode `init` if `wikis/<repo>/` is empty else `update`, follow the
returned lifecycle, and always finish with `CLI wiki <repo> --close` (moves the pages to `wikis/<repo>/` and removes the
AGENTS.md / CLAUDE.md / `.github/` files OpenWiki adds to the repo; without a prior `--open` it does nothing). If the tools are not loaded (they load at session
start from `.mcp.json`), use `CLI wiki <repo>`. Never edit `openwiki/.claims`, `.run.json`, indexes or OpenWiki-managed blocks.

## arch-system
If `docs/architecture/first-look.md` exists, the C4 files started as a static-scan draft: verify and refine them rather
than starting over.
`docs/architecture/model.c4` + `views.c4`: actors, external systems, every container (services, apps, DBs, brokers, topics),
`index` (context) and `containers` views; `#ai-draft` on unvalidated elements, `#confirmed` on validated ones.
Write `docs/overview/system.md` (purpose, context diagram in words, how to navigate) and `docs/index.md` (entry point).
The `likec4` MCP server (in `.mcp.json` / `.codex/config.toml`) answers questions about the model while you write it
(search elements, relationships, "who calls X?").

## domain
`docs/domain/bounded-contexts.md` (context map + repo mapping), `glossary.md`, `actors.md` from the interviews. Fill the
glossary's **Avoid** column with the synonyms the interviews rejected: `CLI check` flags them across the docs.

## data
`docs/data/<store>.md` per datastore: `erDiagram`, ownership table (table → writers → readers), migration source,
`#shared-db` tag in C4 + warning section when shared.

## deployment
`docs/architecture/deployment.c4` + `deployment view deploy_<env>` per environment; `docs/deployment/environments.md`.

## decisions-quality
`docs/decisions/NNNN-<slug>.md` (ADR; `Status: accepted` only when the user said it was decided, else `proposed`),
`docs/quality/slas.md`, `docs/quality/tech-debt.md`.

## security-review [beta]
**Beta**: newer, less battle-tested than the rest of the kit — treat every finding as a lead to verify, not a final
verdict; expect rougher edges and give feedback if something doesn't fit.
Optional, opt-in unit (not in the default blueprint — the user adds it explicitly with
`CLI plan add security-review "Security review" --type security-review --deps arch-system domain data deployment` once
the architecture is documented). Sources: `docs/architecture/*.c4`, `docs/domain/`, `docs/data/`, `docs/deployment/`,
`docs/interview/discovery/*.md` (already capture auth/OIDC, datastores, brokers, exposed endpoints). No code re-reading
beyond confirming a doubtful point — this unit reasons over what discovery/arch-system/data/deployment already
captured, adding a security lens.
Look for, with evidence `<repo>:<path>#Lx-Ly`:
- **AuthN/AuthZ**: endpoints without protection, inconsistent roles/scopes, implicit trust between services.
- **Data**: PII unencrypted in transit/at rest, `#shared-db` containers with excessive access, secrets in config/code
  (per what discovery already captured).
- **Exposed surface**: admin/debug endpoints reachable publicly, missing CORS/rate-limiting, outdated dependency
  versions (cross-check the "Stack" section of each discovery note).
- **Cross-repo trust**: sync/async calls without mutual auth, queues/topics without access control.
Never invent a finding: missing evidence → `TODO(question)` + entry in `docs/interview/open-questions.md`.
Output: `docs/security/threat-model.md` (actors, attack surface, trust boundaries between components) and
`docs/security/findings.md` (finding · severity critical/high/medium/low · component · evidence · recommendation).

## architecture-review [beta]
**Beta**: newer, less battle-tested than the rest of the kit — treat every finding as a lead to verify, not a final
verdict; expect rougher edges and give feedback if something doesn't fit.
Optional, opt-in unit (not in the default blueprint — added the same way as `security-review`, with `--deps arch-system
domain data deployment decisions-quality`). Complements `decisions-quality` (which is interview-based) with
code-evidenced findings:
- **Coupling/cycles**: `graphify query`/`graphify explain` over the dependency graph to spot high coupling or circular
  dependencies between containers.
- **Oversized/mixed-responsibility components**: from the C4 components views (`docs/architecture/repos/*.c4`).
- **Outdated stack / missing tests or observability**: cross-check the "Stack" and "Unknowns" sections of each
  discovery note.
- **SLA drift**: compare `docs/quality/slas.md` (from `decisions-quality`) against what was actually observed.
Every finding needs evidence, same pattern as the rest of the kit. Output: `docs/quality/architecture-review.md`
(area · impact · estimated effort · evidence · recommendation) — a new file, kept separate from `tech-debt.md` (which
stays the interview-sourced material, `x-owner: human` once confirmed).

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
Wizard: `CLI up` (one portal: Docs to read/edit/confirm/comment, Architecture (C4), Code graph, Wikis, Review). For
hosting: `CLI portal` exports the same app read-only to `.camarones/.cache/site` (no npm); check `#/docs`, `#/c4`,
`#/code/all`, `#/wikis` and a flow page with `CLI up --static`. The export refuses to run while gitleaks finds a possible
secret in the docs (as do checkpoint commits): replace it with a placeholder first.

## ci
Wizard: `CLI ci` installs the `cam-docs` pipeline; per-repo snippets are in `.camarones/ci/`. Propose them; the user applies
them to service repos.

## confirm
Human review in the wizard ("✅ Review & verify": page by page, confirm or request changes). An agent may only *propose*
which pages come straight from the user's answers and run `CLI confirm <files> --by <name>` after an explicit yes; if
the user says something is wrong, record it with `CLI feedback <file> "<comment>" --by <name>` (→ `review-fixes`).

## handover
`CLI mark-documented`; commit on branch `docs/camarones` in `cam-docs/` (ask before pushing / MRs; service repos are untouched);
final summary: counts per type, drafts left, open questions, how to update (`update` below), tutorial link.

## update
Recurring after the first full pass (also what CI runs):
1. `CLI sync`, `CLI changes`. Nothing changed and `CLI check` passes → report "up to date".
2. Repo wikis of changed repos: OpenWiki `update` (skip if that repo's CI already did it).
3. Map changed files to docs via `x-sources`; update affected pages and C4 (interfaces, dependencies, deployment).
   New capability → draft flow + open question.
4. Refresh `docs/repos/<repo>/brief.md` if stack/commands/interfaces/diagram changed.
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
1. `ERROR`s: possible secrets first (replace with a placeholder), then frontmatter, broken links, invalid Mermaid
   diagrams, invalid C4 (→ `CLI arch-validate`). Glossary `WARN`s: use the preferred term.
2. Orphans: `x-sources` that no longer exist → find where the code moved (`graphify query`, `git log --follow`) and
   update the page and its sources, or remove the claim.
3. `needs-reconfirm` pages: diff what changed since confirmation, verify it against the code, and write a short summary
   for the user of what changed (they re-confirm it in the wizard). Do not revert human edits.
4. Missing / outdated translations → translate, then `CLI translated <files>`.
Finish with `CLI llms`, a clean `CLI check` and `CLI checkpoint "doc-fixes"`.
