# Documentation conventions (Camarón kit)

Canonical language: **English**. Everything an agent (Claude Code, Codex, CI) writes follows this file.
Humans: see `docs/guides/tutorial.md`. `CLI` = `camaron` (legacy per-project copies: `./camaron.command` / `.\camaron.cmd`).

> **Layout.** Everything the kit writes lives in `cam-docs/` (its own git repo, next to the service repos). Paths in
> this file are relative to `cam-docs/`; repos are its siblings (`../<repo>` from `cam-docs/`, `<repo>/` from the workspace
> folder agents run in). Never write kit files into a service repo — the only exception is the optional one-block
> pointer in `<repo>/CLAUDE.md` that the kit itself manages.

## 1. Where things live

| What | Where | Written by |
|---|---|---|
| Repo-level wiki (only repos with `wiki: true` in workspace.yaml) | `wikis/<repo>/` (OpenWiki OKF pages + grounded claims; `<repo>/openwiki` is an untracked link to it) | OpenWiki (via Claude/Codex integration or CI) |
| Project home, repo pages (facts from the code) | `docs/index.md`, `docs/repos/<repo>/index.md` (`reference.md`, `diagrams.md` before 4.52) | kit (`CLI pages`) |
| Repo brief (stack, commands, interfaces, data, component diagram) | `docs/repos/<repo>/brief.md` | Camarón agent |
| Agent rules, skills, MCP | `AGENTS.md`, `CLAUDE.md` (`@AGENTS.md` + project notes), `.claude/`, `.codex/`, `.agents/`, `.mcp.json` — linked from the workspace folder once this machine approves what the kit did not write (`CLI trust`; approvals in `~/.camarones/trust/`, never in the repo) | kit (managed blocks) + humans |
| Project context for OpenWiki | `wikis/<repo>/INSTRUCTIONS.md` (user-authored brief OpenWiki reads, never rewrites) | Camarón, then humans |
| Code graph | `graph/<repo>/` (git-ignored, AST-only, `CLI graph`), merged in `.camarones/.cache/graph/` | graphify |
| Work plan & session handoff | `docs/.work/plan.yaml`, `handoff.md`, `log.md` | Camarón CLI + agents |
| C4 model (single source for every architecture diagram) | `docs/architecture/*.c4` | Camarón agent |
| Project overview, domain, flows, data, deployment, ADRs, quality | `docs/<section>/*.md` | Camarón + humans |
| Security review (opt-in unit) | `docs/security/*.md` | Camarón agent |
| Translations | `docs/i18n/<lang>/<same logical path>` (repo pages: `docs/i18n/<lang>/repos/<repo>/<page>`) | Camarón agent |
| Interview answers & open questions (team mode: `interview/questionnaire/` + `responses/`) | `docs/interview/` | Camarón agent |
| AI index | `docs/llms.txt` (generated: `CLI llms`) | kit |
| Incremental state | `docs/.state.json` (`CLI changes`, `mark-documented`) | kit |

`docs/` sections: `index.md`, `overview/`, `architecture/`, `domain/`, `flows/`, `data/`, `deployment/`,
`decisions/`, `quality/`, `guides/`, `interview/`, `security/` (only present when the opt-in `security-review` unit ran).

## 2. Frontmatter (every `.md` under `docs/`)

```yaml
---
type: business-flow          # overview|architecture|domain|glossary|business-flow|data-model|deployment|decision|quality|guide|interview
title: Place order
description: One or two retrieval-oriented sentences (what question does this page answer?). Required, 40–300 chars.
x-answers:                   # optional, up to 5 questions as an agent would ask them
  - How is an order placed?
tags: [orders, payments]     # only repo names, glossary terms and C4 ids
x-sources:                   # evidence: "<repo>:<path>", "#L10-L40" for lines, "#Class.method" for a symbol (it is
                             # followed when it moves); "docs/<page>.md" or "c4:<element>" for what a derived page
                             # builds on. Drives orphan detection and freshness.
  - orders-service:src/main/java/com/acme/orders/OrderService.java#L12-L30
x-owner: ai                  # ai (agent may rewrite) | human (agent never rewrites; proposes in docs/interview/open-questions.md)
---
```

- `x-confirmed` is written **only** by `CLI confirm` (a human action). Agents never add, copy or edit it.
- `x-translation-of` is written only by `docs.py translated`.
- OpenWiki pages keep OpenWiki's own OKF frontmatter; the kit only adds `x-confirmed` there (OpenWiki preserves unknown fields).

## 3. Trust model (AI vs human)

| State | Meaning | How an agent must treat it |
|---|---|---|
| `confirmed` | a human validated this exact body (hash-locked) | source of truth; if code contradicts it, flag it — do not silently rewrite |
| `needs-reconfirm` | confirmed once, edited since | as draft, and list it for review |
| `draft` | AI-written, unvalidated | verify against code before relying on it |

- Text between `<!-- human -->` and `<!-- /human -->` is human-authored: keep it byte-for-byte, move it with its section.
- Files with `x-owner: human` (ADRs, glossary after confirmation, SLAs) are never rewritten by an agent.
- Editing a confirmed doc is allowed when the code changed; the edit drops it to `needs-reconfirm` automatically — mention it in the MR.
- Never invent facts to fill a template section: write `TODO(question): …` and add the question to `docs/interview/open-questions.md`.

## 4. Architecture (C4 with LikeC4)

- One model, many views. Kinds/tags live in `docs/architecture/spec.c4`; never invent new kinds without adding them there.
- `model.c4`: actors, external systems, the project `system`, one container per repo/datastore/broker/topic.
  Container ids = repo name in camelCase; `metadata { repo '<repo-name>' }` on every repo container.
- `repos/<repo>.c4`: `extend <system>.<container> { components… }` + `view <repo_snake>_components of <system>.<container> { include * }`.
  A repo container that `model.c4` does not have yet is declared here too, with `extend <system> { … }`.
- **Fragments.** Units that may run in parallel write only their own file: `repos/<repo>.c4` (repo-brief) and
  `flows/<slug>.c4` (one `dynamic view flow_<slug>` per flow). The shared files — `spec.c4`, `model.c4`, `views.c4`,
  `deployment.c4` — are edited by the units that run alone (arch-system, deployment, diagrams). LikeC4 reads every
  `.c4` under `docs/architecture/`, so the split changes nothing in the views; flows already in `views.c4` stay valid.
  Components follow the real structure (hexagonal: in-adapters, application services, domain, out-adapters).
- Relationships: `-[sync]->` for HTTP/gRPC, `-[async]->` for AMQP/Kafka/events, always with `technology '…'` and a label
  that names the endpoint/exchange/topic. Shared databases: tag the database `#shared-db` and draw one edge per service.
- New or unvalidated elements carry `#ai-draft`; replace with `#confirmed` after the interview. People confirm in the
  portal (Architecture → a view → its elements), which also writes `confirmed-by`/`confirmed-at` in the element's
  `metadata`: never put `#ai-draft` back on a `#confirmed` element; change it and say so in the handoff instead.
- `views.c4`: `index` (context), `containers`, `deployment view deploy_<env>` per environment; flow views live in `flows/<slug>.c4`.
  The portal embeds `flow_<slug>` interactively at the top of `docs/flows/<slug>.md` (slug `-` → `_`), and `index` on the
  home page. Any other page can embed a view with a fenced block: ```` ```likec4-view ```` containing the view id.
- `deployment.c4`: environments → clusters/hosts → namespaces → `instanceOf`.
- Syntax traps: tags go inside `{ }` blocks (not after a one-line element); metadata keys must not be DSL keywords (`source`, `model`…) —
  use `evidence`. Validate after every edit: `CLI arch-validate` (must print `✓ Valid`).
- Repo briefs (`docs/repos/<repo>/brief.md`) embed the Mermaid export of their component view:
  `likec4 gen mermaid docs/architecture -o build/mmd`. Service repos and their READMEs get no kit files (section 7).

## 5. Markdown diagrams (Mermaid)

- Business flow → `sequenceDiagram` always; add `flowchart` only if there are business rules with branches.
- Lifecycle → `stateDiagram-v2` for **every** entity, job or request with a status (an enum, a `status` column, a state
  machine), wherever it is explained: flow, domain or data page. Real states and the events/endpoints that move them.
- Data model → `erDiagram` per datastore; a cache or key-value store gets a `flowchart` of keys, TTLs, writers and readers.
- Domain → a context map (`flowchart`). System overview → the C4 context (```` ```likec4-view ```` `index`).
  Deployment → a diagram or the C4 deployment view.
- Keep diagrams ≤ ~25 nodes; split instead of shrinking.
- Generated diagrams (`CLI pages`, alias `CLI diagrams`: the `context` map in `docs/index.md`, the `endpoints-map` and
  one `states` diagram per status enum in `docs/repos/<repo>/index.md`, one `messaging` sequence per topic in
  `docs/architecture/messaging.md`; before 4.52: `architecture/system-map.md` and `repos/<repo>/diagrams.md`;
  business-flow sequences are not generated) sit in
  `<!-- generated:<kind> … -->` blocks and say only what the code says. They are in one of three states: from the code
  (facts, no meaning), `confirmed=<sha> by=<name>` (a person verified it; never rewritten, and `CLI check` warns when the
  code changed since) or a **proposal** (`<!-- proposal:<kind> … base=<sha> -->` right after the block: unreviewed AI
  work with a "Why" list where every claim cites `repo:path#Symbol`; a person reviews it and applies it).
- Never edit a generated block: add a proposal. A block may be moved, markers included, to the page it belongs in.
- `CLI check` warns about the gaps (a flow without its sequence, a lifecycle told only in prose, a structure page with
  no picture); the `diagrams` plan unit fills them.

## 6. Page templates

Directives the portal renders (and agents read as plain Markdown): `:::tabs` with `::tab Label` lines for alternatives
(per language, tool or environment), `:::steps` around a numbered list, `:::details Summary` for content that can stay
folded, `:::cards` around a list of `[Title](link): text`, `:::tech` around details only engineers need and `:::business`
around a plain-language explanation. Use them only when they help a reader; plain Markdown is always fine.

Business rules go in `:::rule ID Title` blocks: the rule in plain words, plus `enforced:` (and `test:`) lines with
`repo:path#Symbol` anchors, comma-separated, to the code that applies it and the test that checks it. IDs are unique
across the docs (`ORD-1`, `PAY-3`); `CLI check` fails when an anchored symbol is gone and warns about a rule nobody
enforces.

```
:::rule ORD-1 Non-empty orders
enforced: api:src/main/java/shop/OrderService.java#OrderService.place
test: api:src/test/java/shop/OrderServiceTest.java#OrderServiceTest.rejectsEmptyCart
An order needs at least one line.
:::
```

Start every page from its skeleton in `.camarones/skeletons/` (one per `type`, or per path with `x-skeleton-for`):
frontmatter, H1, TL;DR and the required `##` sections. `CLI check` reads the skeletons to know which sections a page
needs; one marked `<!-- optional -->` may be left out. The team may edit them; an edited copy survives kit upgrades.

**Business flow** (`docs/flows/<slug>.md`, `type: business-flow`)
1. Summary (actor, trigger, outcome) · 2. Sequence diagram · 3. Steps table: step · repo · entrypoint (endpoint/listener) · evidence ·
4. Rules & branches (flowchart if any) · 5. Failure handling / idempotency / retries · 6. Data touched (tables/topics) ·
7. C4 dynamic view id · 8. Open questions.

**Data model** (`docs/data/<store>.md`, `type: data-model`)
ERD · ownership table (table → writer services → reader services) · migrations source (Liquibase/Flyway/Firestore rules) ·
`#shared-db` warning with who-writes-what if shared.

**Decision** (`docs/decisions/NNNN-<slug>.md`, `type: decision`, `x-owner: human` once accepted)
Status · Context · Decision · Consequences · Evidence. Agents may only create `Status: proposed`.

Optional sections, in this order, left out when they have nothing to say: **Decision drivers** (after Context),
**Considered options** (after the drivers), **Confirmation** (how the team will know the decision is followed: a test,
a check, a review step), **Diagram** (a Mermaid block, section 5, when a picture explains the options or the result)
and **Decided by** (who decided, written by the person who accepts the ADR, never by an agent). The kit also reads the
Spanish headings (`Estado`, `Contexto`, `Drivers`, `Opciones consideradas`, `Decisión`, `Consecuencias`,
`Confirmación`, `Diagrama`, `Evidencia`, `Decidido por`).

An ADR with a working state in `docs/.work/adr/<NNNN>.yaml` is being decided by people (the desktop app's
*Decisiones*): its parts, decision points, chosen options and attendees live there. Agents never rewrite such an ADR.
Once accepted it is closed: to change the decision, write a new ADR that supersedes it. An ADR with no working state
(one a person wrote, or an older kit) is read as it is and never rewritten until a person starts a review session on
it; in that session each edit rewrites only the section edited, and a decided one opens no session.

**Domain** (`docs/domain/`): `bounded-contexts.md` (context map, which repo implements which context),
`glossary.md` (term · definition · code name · context · avoid), `actors.md` (people & external systems). **Avoid** is
optional: comma-separated synonyms not to use (`purchase, request` for *Order*); `CLI check` warns wherever they appear
in prose. A translated glossary (`docs/i18n/<lang>/domain/glossary.md`) carries its own Avoid list for that language.

**Quality** (`docs/quality/`): `slas.md`, `tech-debt.md` (item · impact · evidence · owner, from the `decisions-quality`
interview), `architecture-review.md` (area · impact · estimated effort · evidence · recommendation, from the opt-in
`architecture-review` unit — code-evidenced, kept separate from the interview-sourced `tech-debt.md`).

**Security** (`docs/security/`, `type: quality`, from the opt-in `security-review` unit — **beta**):
`threat-model.md` (actors, attack surface, trust boundaries) and `findings.md`
(finding · severity critical/high/medium/low · component · evidence · recommendation).

> `security-review` and `architecture-review` are **beta** units: newer and less battle-tested than the rest of the
> kit. Treat their output as draft leads to verify, not a final verdict.

**Deployment** (`docs/deployment/environments.md`): environments, URLs, infra source (Helm/K8s/ArgoCD/compose), config/secrets sources.

## 7. Repo briefs and managed blocks

Service repos carry no kit files. What an agent needs to work on one repo is its brief, `docs/repos/<repo>/brief.md`:
purpose (1 line) · stack (language, framework, versions, build tool) · how to build/test/run locally · interfaces
(endpoints, listeners, topics) · data owned · component diagram (Mermaid from LikeC4) · where the rest is (`wikis/<repo>/`,
`graph/<repo>/`, portal pages) · trust rule (section 3).

Generated blocks hold facts read from the repos without AI: `<!-- generated:<kind> repo=<repo> -->` …
`<!-- /generated:<kind> -->`, with `<kind>` one of `commands`, `env`, `endpoints`, `topics`, `schema`, the diagram
kinds `states`, `endpoints-map`, `context`, `messaging`, and `repos` (the repo cards of `docs/index.md`).
`docs/repos/<repo>/index.md` is made of them (`reference.md` in a project from before 4.52); `CLI pages` writes the
pages and `CLI blocks` refreshes the blocks in every page. A kit page (`x-generated: true`) is rewritten whole only
while it holds nothing but kit text and is not confirmed; otherwise only its blocks change. A person's page
(`x-owner: human` or any `x-confirmed`) is never rewritten whole, and `CLI pages --adopt` never writes or deletes it. An
agent's page carries `x-owner: ai` (a page with no `x-owner` is an agent's too, as the kit reads it). Put the same
markers in any page instead of copying those facts by hand; `CLI blocks` and `CLI sync` fill and refresh them. Never edit inside a block: fix the source in the repo. A hand edit is kept and flagged.

Managed blocks (`<!-- camarones:start -->` / `<!-- camarones:end -->` in `AGENTS.md`; `<!-- cam-docs:start -->` /
`<!-- cam-docs:end -->` for the optional pointer in `<repo>/CLAUDE.md`) are rewritten by the kit only; everything outside
the markers is left alone.

## 8. Translations

English is canonical. After writing/updating a canonical page, write/update `docs/i18n/<lang>/<logical path>` (natural,
not literal; keep code identifiers, endpoints and glossary terms untranslated unless the glossary gives a translation),
then stamp it: `CLI translated <files>`. `CLI status` shows missing/outdated translations.

## 9. Incremental updates and cleanup

1. `CLI changes` → per-repo changed files since `docs/.state.json`.
2. Map changed files to docs through `x-sources` (and OpenWiki claims for repo wikis); update only those, plus the C4 model
   if interfaces/dependencies changed.
3. Cleanup: `CLI status` / `CLI check` list orphans (sources gone). Orphan `draft` → delete the page (and its translations and
   C4 elements). Orphan `confirmed` → do not delete; mark `TODO(question)` and ask. Repo removed from `.camarones/workspace.yaml` →
   delete its C4 file, its `docs/i18n/*/repos/<repo>/` and references.
4. `CLI llms`, `CLI check`, then `CLI mark-documented`.

## 10. Quality gate (`CLI check`)

| Check | Severity | Needs |
|---|---|---|
| Missing frontmatter, orphan `x-sources` | ERROR | — |
| Broken internal link (`.md` target, resolved like the portal does; external URLs are not checked) | ERROR | — |
| `#anchor` with no matching heading in the target page (slugs as in the portal: lower case, punctuation dropped, spaces → `-`) | WARN (ERROR with `--strict`) | — |
| Invalid Mermaid diagram | ERROR | mermaid-cli (`quality` component) |
| Possible secret in `docs/` or a wiki | ERROR; also blocks checkpoint commits and `CLI portal` | gitleaks (`quality` component) |
| Glossary synonym to avoid | WARN (ERROR with `--strict`) | an Avoid column in the glossary |
| Confirmed page changed since confirmation | WARN (ERROR with `--strict`) | — |
| Missing / outdated translation | WARN | — |
| Missing diagram (flow without a sequence, lifecycle told only in prose) | WARN (ERROR with `--strict`) | — |
| Cited code changed or gone since the page was written (`CLI fresh`) | WARN (ERROR with `--strict`) | — |
| Generated block edited by hand or behind the code (`CLI blocks`) | WARN (ERROR with `--strict`) | — |
| Team plugin folder that no longer matches `.camarones/plugins.lock`, or is not in it (`CLI plugins`) | WARN (ERROR with `--strict`) | — |
| Page structure (section 11): type, title, description, one H1, TL;DR, skeleton sections, budgets, vague references | WARN (ERROR with `--strict`) | — |

A check whose tool is missing prints one WARN and is skipped. `CLI check --secrets` runs only the secret scan (CI gate).

## 11. Writing for agents first

The first reader is an agent that gets **fragments**: one search hit, one section, one `llms.txt` line. People read
the same pages second, and skim them the same way. `CLI check` enforces the rules marked ✓ (section 10); interviews,
guides, wikis and pages with `x-owner: human` keep their own shape.

| ID | Rule | ✓ |
|---|---|---|
| W1 | Open with `> **TL;DR:** …` (2–4 lines) right under the H1: what the page answers, in plain words. | ✓ |
| W2 | Every `##` section reads alone: name the thing again instead of "as mentioned above", "this service", "see below". | ✓ |
| W3 | Exact identifiers in backticks, spelled as in the code: `POST /orders`, topics, tables, classes, env vars, C4 ids, repo names. Use the glossary term. | |
| W4 | Tables for facts (endpoints, commands, env vars, ownership, steps), prose for the why. Commands in fenced blocks, saying which folder they run in. | |
| W5 | Evidence next to the claim: keep `x-sources`, and add `(evidence: repo:path#Lx-Ly)` in table rows and critical claims. | |
| W6 | Budgets: at most ~1500 words of prose per page and ~400 per `##` section; one H1; no skipped heading levels. Split instead of compressing. | ✓ |
| W7 | `description` of 40–300 characters that says which question the page answers; optional `x-answers`; `tags` from repo names, glossary terms and C4 ids. | ✓ |
| W8 | Unknown → `TODO(question): …`. Never fill a section to look complete. | |
| W9 | Every diagram has a table or text with the same facts. | |
