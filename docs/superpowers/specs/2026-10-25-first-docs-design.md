# First docs: a project home and one page per repo — design (3a)

Part 3a of "simpler start, Mermaid diagrams, less noise" (1: boards removed; 2a: diagrams from the code; 3b: creating a
project in the desktop app is one screen and a run; 3c: a short plan that grows on demand).

## 1. Intent

A fresh install (no AI) of Spring PetClinic writes 11 pages and about 9 000 words today, with no page that says what the
project is. `architecture/first-look.md` and `architecture/system-map.md` overlap; each repo is split across
`repos/<repo>/reference.md`, `repos/<repo>/diagrams.md` and `data/<repo>.md`; the TL;DRs explain the kit ("Discovery
reads this page first… fix it with `camaron stack`") instead of the project. This piece makes the first docs short,
visual and about the project:

1. **A generated project home**, `docs/index.md`: what the system is, a card per repo, the context map.
2. **One generated page per repo**, `docs/repos/<repo>/index.md`: diagrams first, tables folded.
3. **Texts about the project**; how a page is made goes to a folded block at the end.

**Anti-goals — a failure even if it works:** a 3.x/4.x project whose pages move or vanish without being asked; a page
or block a person wrote or confirmed being rewritten; a page that only an AI run can fill.

## 2. The project home — `docs/index.md`

Generated (`x-generated: true`, `x-owner: ai`, `type: overview`, trust draft), written only when the file does not exist
or is itself kit-generated (same rule as 2a's `write_pages`).

- H1: the project name (`workspace.yaml` `project.name`).
- `> **TL;DR:**` composed from facts, e.g. "Pet Clinic has 2 repos (Java · Spring Boot, TypeScript · Angular): 35
  endpoints, 9 tables, no message topics, 61 direct dependencies." Zero counts are said plainly ("no message topics"),
  never left out silently.
- A new generated block kind `repos` (`repo=_system`): a `:::cards` list, one card per repo —
  `[<repo>](repos/<repo>/index.md): <stack> · <n> endpoints · <n> tables · <n> topics`.
- `## Context map`: the `context` block from 2a (moved here from `architecture/system-map.md`).
- `## More`: links to `overview/tooling.md`, `overview/libraries.md` and, when there are topics,
  `architecture/messaging.md`.
- `:::details How this page is made` at the end: read from the code with no AI, `camaron pages` refreshes it, how to
  confirm a diagram (link to the tutorial section).

## 3. The repo page — `docs/repos/<repo>/index.md`

Generated, one per repo on this machine; a repo where the scan finds nothing still gets one, whose TL;DR says so
(same writing rules as the home). It is the folder's cover, so the
portal tree shows it as "the repo".

- H1: the repo name. `> **TL;DR:**` from facts, e.g. "`spring-petclinic-rest` is a Java · Spring Boot service: 35
  endpoints, 9 tables (PostgreSQL, MySQL); it publishes no messages; it calls no other repo."
- Sections, in this order, each written only when it has content:
  1. `## What it exposes` — the `endpoints-map` block(s); the `endpoints` table block inside `:::details Endpoints`.
  2. `## Data` — the `schema` block (ER diagram).
  3. `## Lifecycles` — the `states` blocks.
  4. `## Messages` — the `topics` table block.
  5. `## What it needs to run` — `env` and `commands` table blocks, each inside `:::details`.
- `:::details How this page is made` at the end.

## 4. What new projects stop getting, and what stays

- Not written for **new-layout** projects: `architecture/first-look.md` (the C4 draft files are still written),
  `repos/<repo>/reference.md`, `repos/<repo>/diagrams.md`, `data/<repo>.md` at install, `architecture/system-map.md`.
- `architecture/messaging.md`: the `messaging` blocks, written only when there are topics.
- Unchanged pages, with TL;DRs rewritten about the project and the kit hints moved to a folded block:
  `overview/tooling.md` (radar), `overview/libraries.md` (inventory). The kit guides stay.
- The AI `data` unit may still write `data/` pages later; it moves the `schema` block there with its markers (2a's
  moved-block rule keeps `camaron pages` from writing it back).

## 5. Layouts and existing projects (AGENTS.md 2.3)

- **Old layout**: the project has any of `repos/*/reference.md`, a kit-generated `data/<repo>.md`,
  `architecture/first-look.md`, `architecture/system-map.md`, `repos/*/diagrams.md`. It keeps them; every writer and
  refresh behaves exactly as today; `camaron pages` refreshes blocks but writes no new-layout page.
- **New layout**: a docs page holds the `repos` block (the home was written), or none of those exists (a fresh
  project). `camaron pages` writes §2–§4.
- An existing kit page (`x-generated: true`, no `x-confirmed`) is rewritten whole, with its confirmed, hand-edited and
  unreadable blocks put back verbatim, only while everything outside its blocks is kit text (headings, the
  `> **TL;DR:**` line, bare `:::`, link items to the More pages, and lines the kit would write today outside its blocks).
  A page with any other text, or confirmed, gets its blocks brought up to date and nothing else.
- A person's page is one with `x-owner: human` or `x-confirmed`; a page with no `x-owner` is an agent's (the kit's
  default).
- **`camaron pages --adopt`** (explicit, idempotent): moves every generated block, with its markers and confirmations,
  from the kit's old pages into the new pages (filling an agent's home or repo page with the blocks, never a
  person's); deletes an old page only when it is not a person's, holds nothing but kit text (the rule above) and every
  block in it lives in a page that stays; leaves any other page in place, blocks included, and lists it. Links to a
  deleted page are pointed at its new page in pages that are not a person's; those, and the translations of deleted
  pages, are listed. Afterwards the project is new-layout. A test starts from a 4.x layout fixture.

## 6. Commands, install, portal, agents

- `camaron pages [--adopt] [--json]` (new; `lib/pages.py`). `camaron diagrams` stays as an alias of `pages` (2a is
  unreleased; the alias costs nothing). Catalog: `pages` → app / analyze.
- Install: `wizard.scan_repos` and `serve.first_look` call `pages.write` instead of `quickarch.save`'s page,
  `schemas.write_pages`, `genblocks.write_reference` and `diagrams.write_pages` (the C4 draft files are still saved).
  A failure is caught and logged; the rest of the install continues (as 2a).
- Wizard C4 step (`arch_flow`): depends on the C4 draft files, not on `first-look.md`.
- Portal Home (`#/`): under the Ask box, the project home's body (cards, context map) before the state KPIs; the Docs
  cover keeps showing `index.md` as today. Repo links (`legacy/doc.js` ~295) prefer `repos/<repo>/index.md`. Data view:
  its page link falls back to `repos/<repo>/index.md` when `data/<repo>.md` does not exist.
- Agents: PLAYBOOK (`repo-brief` reads `repos/<repo>/index.md`, else `reference.md`; `arch-system` starts from the C4
  draft files), CONVENTIONS §4/§5 and the `cam-docs-diagrams` skill name the new pages, with the old ones as the
  old-layout alternative.

## 7. Tests first

- Home and repo page from a `make_workspace` fixture: TL;DR facts (counts, zero counts said), cards, section order,
  tables inside `:::details`, "How this page is made" at the end, idempotent second run.
- Layout detection: fresh → new; each old page alone → old; old-layout `camaron pages` writes no new page.
- `--adopt` from a 4.x layout fixture: blocks moved intact (a confirmed and an edited one included), emptied kit pages
  deleted, a page with human prose kept, `x-owner: human` untouched, second run no-op.
- Install hooks write the new pages; a failing writer does not stop the install.
- Portal: Home renders `index.md`; repo links and Data fallback (vitest / python).
- `catalog --check`; sandbox: PetClinic gets `index.md`, two repo pages, `tooling.md`, `libraries.md` (plus the kit
  guides) and `check` has no Mermaid error.

## 8. Docs and version

README (Spanish), `lib/tutorial.py` + regenerated `TUTORIAL.md`, both tutorial templates (existing projects keep their
copy: say so in the commit), `VERSIONS["kit"]` minor bump with the badge.

## 9. Out of scope

The app's create flow (3b), the plan (3c), translations of generated pages (the existing `translation es missing`
warning stays as it is), AI proposals (2b).
