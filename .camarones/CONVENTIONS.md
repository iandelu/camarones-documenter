# Documentation conventions (Camarones Documenter kit)

Canonical language: **English**. Everything an agent (Claude Code, Codex, CI) writes follows this file.
Humans: see `docs/guides/tutorial.md`. `CLI` = `camarones` (legacy per-project copies: `./camarones.command` / `.\camarones.cmd`).

> **Layout.** Everything the kit writes lives in `cam-docs/` (its own git repo, next to the service repos). Paths in
> this file are relative to `cam-docs/`; repos are its siblings (`../<repo>` from `cam-docs/`, `<repo>/` from the workspace
> folder agents run in). Never write kit files into a service repo — the only exception is the optional one-block
> pointer in `<repo>/CLAUDE.md` that the kit itself manages.

## 1. Where things live

| What | Where | Written by |
|---|---|---|
| Repo-level wiki (per microservice/app) | `wikis/<repo>/` (OpenWiki OKF pages + grounded claims; `<repo>/openwiki` is an untracked link to it) | OpenWiki (via Claude/Codex integration or CI) |
| Repo brief (stack, commands, interfaces, data, component diagram) | `docs/repos/<repo>/brief.md` | Camarones Documenter agent |
| Agent rules, skills, MCP | `AGENTS.md`, `CLAUDE.md` (`@AGENTS.md` + project notes), `.claude/`, `.codex/`, `.agents/`, `.mcp.json` — linked from the workspace folder | kit (managed blocks) + humans |
| Project context for OpenWiki | `wikis/<repo>/INSTRUCTIONS.md` (user-authored brief OpenWiki reads, never rewrites) | Camarones Documenter, then humans |
| Code graph | `graph/<repo>/` (git-ignored, AST-only, `CLI graph`), merged in `.camarones/.cache/graph/` | graphify |
| Work plan & session handoff | `docs/.work/plan.yaml`, `handoff.md`, `log.md` | Camarones Documenter CLI + agents |
| C4 model (single source for every architecture diagram) | `docs/architecture/*.c4` | Camarones Documenter agent |
| Project overview, domain, flows, data, deployment, ADRs, quality | `docs/<section>/*.md` | Camarones Documenter + humans |
| Security review (opt-in unit) | `docs/security/*.md` | Camarones Documenter agent |
| Translations | `docs/i18n/<lang>/<same logical path>` (repo pages: `docs/i18n/<lang>/repos/<repo>/<page>`) | Camarones Documenter agent |
| Interview answers & open questions | `docs/interview/` | Camarones Documenter agent |
| AI index | `docs/llms.txt` (generated: `CLI llms`) | kit |
| Incremental state | `docs/.state.json` (`CLI changes`, `mark-documented`) | kit |

`docs/` sections: `index.md`, `overview/`, `architecture/`, `domain/`, `flows/`, `data/`, `deployment/`,
`decisions/`, `quality/`, `guides/`, `interview/`, `security/` (only present when the opt-in `security-review` unit ran).

## 2. Frontmatter (every `.md` under `docs/`)

```yaml
---
type: business-flow          # overview|architecture|domain|glossary|business-flow|data-model|deployment|decision|quality|guide|interview
title: Place order
description: One or two retrieval-oriented sentences (what question does this page answer?).
tags: [orders, payments]
x-sources:                   # evidence, "<repo>:<path>" (optionally #L10-L40). Drives orphan detection.
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
  Components follow the real structure (hexagonal: in-adapters, application services, domain, out-adapters).
- Relationships: `-[sync]->` for HTTP/gRPC, `-[async]->` for AMQP/Kafka/events, always with `technology '…'` and a label
  that names the endpoint/exchange/topic. Shared databases: tag the database `#shared-db` and draw one edge per service.
- New or unvalidated elements carry `#ai-draft`; replace with `#confirmed` after the interview.
- `views.c4`: `index` (context), `containers`, one `dynamic view flow_<slug>` per business flow, `deployment view deploy_<env>` per environment.
- `deployment.c4`: environments → clusters/hosts → namespaces → `instanceOf`.
- Syntax traps: tags go inside `{ }` blocks (not after a one-line element); metadata keys must not be DSL keywords (`source`, `model`…) —
  use `evidence`. Validate after every edit: `CLI arch-validate` (must print `✓ Valid`).
- Repo READMEs embed the Mermaid export of their component view: `likec4 gen mermaid docs/architecture -o build/mmd`.

## 5. Markdown diagrams (Mermaid)

- Business flow → `sequenceDiagram` always; add `flowchart` only if there are business rules with branches;
  add `stateDiagram-v2` when an entity has a lifecycle.
- Data model → `erDiagram` per datastore.
- Keep diagrams ≤ ~25 nodes; split instead of shrinking.

## 6. Page templates

**Business flow** (`docs/flows/<slug>.md`, `type: business-flow`)
1. Summary (actor, trigger, outcome) · 2. Sequence diagram · 3. Steps table: step · repo · entrypoint (endpoint/listener) · evidence ·
4. Rules & branches (flowchart if any) · 5. Failure handling / idempotency / retries · 6. Data touched (tables/topics) ·
7. C4 dynamic view id · 8. Open questions.

**Data model** (`docs/data/<store>.md`, `type: data-model`)
ERD · ownership table (table → writer services → reader services) · migrations source (Liquibase/Flyway/Firestore rules) ·
`#shared-db` warning with who-writes-what if shared.

**Decision** (`docs/decisions/NNNN-<slug>.md`, `type: decision`, `x-owner: human` once accepted)
Status · Context · Decision · Consequences · Evidence. Agents may only create `Status: proposed`.

**Domain** (`docs/domain/`): `bounded-contexts.md` (context map, which repo implements which context),
`glossary.md` (term · definition · code name · context), `actors.md` (people & external systems).

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
