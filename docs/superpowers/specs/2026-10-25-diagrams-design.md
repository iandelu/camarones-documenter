# Diagrams from the code, improved by AI, confirmed by people — design

Part 2 of 3 of "simpler start, Mermaid diagrams, less noise" (1: boards removed, kit 4.49.0; 3: a shorter, simpler
first run and plan).

## 1. Intent

AGENTS.md priority 1 says installing gives value almost without AI. Today a fresh install draws the C4 draft and each
repo's ER diagram; every other picture CONVENTIONS §5 asks for (lifecycles, context map, messaging, a service at a
glance) waits for the AI `diagrams` unit. This piece:

1. **Draws four more diagram kinds from the code, no AI**, at install and on every refresh.
2. **Lets the AI propose an improvement next to each one**, from the plan or from a button, never editing them.
3. **Lets a person accept or discard each proposal** in the portal; an accepted diagram is confirmed and protected,
   and says so when the code moves on.
4. **Teaches agents Mermaid** through the doc skills, so every diagram an agent draws follows the same rules.

**Anti-goals — a failure even if it works:** an AI change to a diagram that nobody accepted; a confirmed diagram
overwritten by a refresh; an invented state, transition or call; a 3.x/4.x project changing without being asked.

## 2. Diagram kinds generated without AI

New kinds in `lib/genblocks.py` next to the existing `schema` (erDiagram), same block mechanism:
`<!-- generated:<kind> repo=<repo> [id=<id>] sha=<hash> -->…<!-- /generated:<kind> -->`.

| Kind | Scope | Source | Diagram |
|---|---|---|---|
| `states` | per repo, one block per enum (`id=<EnumName>`) | new scanner `lib/diagrams.py`: enums whose name ends in `Status`, `State`, `Phase` or `Stage` in Java, Kotlin, TypeScript, Python (`Enum`), C#, Dart, Go (`iota` const blocks of a `…Status` type); SQL `CHECK (<col> IN (…))` on a `status`/`state` column and ORM enums from `schemas.py` | `stateDiagram-v2` with the **states only**, plus a `note` "transitions: waiting for a proposal". Never a transition |
| `endpoints-map` | per repo (split by resource group when over the node limit, `id=<group>`) | `genblocks.endpoint_rows` + this repo's edges in `quickarch.scan()` | `flowchart LR`: endpoints grouped by first path segment; the repo's datastores, topics published/consumed and repos it calls |
| `context` | system (`repo=_system`) | `quickarch.scan()` | `flowchart`: repos, datastores, brokers, identity providers, external systems; edges labelled as in the C4 draft |
| `messaging` | system, one block per topic (`id=<topic>`) | `quickarch` `PUBLISH`/`CONSUME` matches per repo | `sequenceDiagram`: producers → broker → consumers for that topic |

- Every diagram stays ≤ 25 nodes (CONVENTIONS §5). Over that: split (`endpoints-map` per group, `context` drops
  external systems into one "External" node and says so in a note). Never shrink labels.
- Each block's sources (`repo:path`) go to the page's `x-sources`, as `refresh` already does for `x-generated` pages.
- Labels are quoted when they contain Mermaid-special characters; node ids come from `quickarch.ident`.
- `repo=_system` is a reserved name for system-wide blocks; `docs.repo_names()` never returns it.

**Pages written at install** (`x-generated: true`, `type` per skeleton, trust `draft`):

- `docs/architecture/system-map.md` — `context` and the `messaging` blocks (H1, TL;DR, one `##` per kind).
- `docs/repos/<repo>/diagrams.md` — `endpoints-map` and `states` blocks for that repo.

A page with no block to show is not written. When an agent later writes the page a diagram belongs to (flow, domain,
data), it **moves the block with its markers**; refresh works on any page, so nothing is lost.

**Commands and hooks**

- `camaron diagrams [--json]` writes or refreshes those pages (new `lib/diagrams.py`: `write_pages(log) -> list[str]`).
- `camaron blocks` keeps refreshing every block in every page, the new kinds included.
- `wizard.scan_repos()` and `serve.first_look()` call `diagrams.write_pages(log=log)` right after
  `schemas.write_pages`.
- `lib/catalog.py`: `diagrams` → app / analyze.

## 3. Proposals

A proposal sits right after its generated block:

```
<!-- proposal:states repo=api id=OrderStatus base=<sha> by=<runner:model> at=<YYYY-MM-DD> -->
> **Why:** <one line per claim, each ending with its cite `repo:path#Symbol`>
```mermaid
…
```
<!-- /proposal:states -->
```

- `base` is the `sha` of the generated (or confirmed) block body the proposal started from.
- At most one proposal per block; a new one replaces the old.
- **Rules the code enforces** (`diagrams.validate_proposal`), not only the skill:
  1. The body is one valid Mermaid diagram of the same family as the block (`mmdc` when installed; otherwise the
     portal runs `mermaid.parse` before it enables Accept, and `check` warns "not validated").
  2. Every claim cites `repo:path#Symbol` with a file that exists and a symbol found in it (the same check Ask uses
     for citations). Claims without a valid cite are dropped; a proposal left with none is refused.
  3. No proposal is written into a page with `x-owner: human`; those are reported, not touched.

## 4. Accept, discard, confirmed

- **Accept** (`POST /api/diagrams/accept {page, kind, repo, id}`; CLI `camaron diagrams accept <page> <kind>:<repo>[:<id>]`):
  the block body becomes the proposal's diagram; the opening marker gets `confirmed=<base> by=<person>`; `sha` is
  recomputed from the new body (so it is not "edited"); the proposal block is removed; its cites join `x-sources`.
  A page that was `confirmed` stays confirmed (the accept is a person confirming that diagram: `docs.confirm` is
  re-run for the same person after the write). The share of words the person changed is recorded in
  `docs/.work/ai-drafts.json` like page confirmations (`harness/drafts.py`).
- **Discard** (`POST /api/diagrams/discard`, CLI `… discard`): removes the proposal block, nothing else.
- **States** (`genblocks.states`) gain two: `confirmed` (a fresh scan still gives `base`) and `confirmed-stale` (it
  gives another sha). `refresh` never rewrites a confirmed block, with or without `--force`.
- `check`: `confirmed-stale` → WARN "the code changed since this diagram was confirmed (<page>, <kind> <repo>)";
  an invalid or unvalidated proposal → WARN; a proposal whose `base` differs from its block's current `sha` → WARN
  "proposal made on an older diagram"; a proposal with no generated block right before it → ERROR.
- Old blocks without `id`, `confirmed` or `base` read exactly as before (same regex, optional attributes).

## 5. Asking the AI for proposals

`camaron diagrams propose [<page> [<kind>:<repo>[:<id>]]] [--all] [--json]` (`lib/diagrams.py: propose(...)`):

- One headless call per block to the runner routed for bounded work, local models allowed — the same path as Ask's
  AI answer (`lib/answers.py`: empty folder, no tools, the project's agent config not loaded).
  `diagrams: {ai: false, model: …}` in `workspace.yaml` turns it off or picks the model.
- The kit builds a closed context per kind, capped at 9000 characters:
  `states` → the enum's file plus the lines using its values (`OrderStatus.PAID`, `setStatus(…)`, `status = …`), 15
  lines around each; `messaging` → producer and consumer code for the topic; `endpoints-map` → the controllers;
  `context` → the first-look `x-sources` files.
- The runner returns JSON `{mermaid, why: [{claim, cite}]}`; the result goes through `validate_proposal`; a refused
  result writes nothing and says why. Timeout 120 s per block.
- `--all`: every generated block with no proposal and not confirmed (or `confirmed-stale`, which proposes an update
  from the confirmed body plus the generated diff).
- No runner, or `ai: false`: a clear error naming how to set one up; generated diagrams keep working.
- `lib/catalog.py`: `diagrams propose` → app / generate; `accept` and `discard` → portal.

**Plan unit `diagrams`** (phase 5, agent) — PLAYBOOK rewritten: (1) `CLI diagrams`; (2) `CLI diagrams propose --all`;
(3) fill the gaps `check` sees and the generators cannot (a business flow's sequence…) as proposals on generated
blocks or as new diagrams in `draft` pages, never by editing a generated block; (4) `CLI check` with no diagram
errors, `CLI checkpoint "diagrams"`.

## 6. Portal

- Doc view: each generated block shows a small badge — "From the code" / "Confirmed by <name>" / "The code changed"
  (es: "Del código" / "Confirmado por <nombre>" / "El código cambió").
- A block with a proposal shows **Generated | AI proposal** side by side (tabs under 720 px), the **Why** list with
  links to its cites, and **Accept** / **Discard** (live portal only). Accept stays disabled until `mermaid.parse`
  passes.
- **Propose an improvement**: desktop app only (machine work, app token). In a browser the button says so and shows
  the CLI command. A `confirmed-stale` block offers **Propose an update** the same way.
- Static export: badges and both diagrams, read-only, no buttons.
- Review zone: two new lists, "Diagram proposals to review" and "Diagrams the code left behind" (`confirmed-stale`).
- Pure helpers (block parsing, button state) in `src/` with vitest; the legacy doc view calls them through
  `window.CamaronContent` like the existing directives.

## 7. Mermaid in the doc skills

Kit skills are rewritten in every project on each run (`env.write_kit_skills`), so 3.x/4.x projects get these with
no migration.

- New `templates/skills/cam-docs-diagrams/SKILL.md`: which diagram for what (CONVENTIONS §5 condensed); the three
  states (from the code = facts, confirmed = verified, proposal = unreviewed AI); never edit a generated block —
  write a proposal with cites or run `CLI diagrams propose`; Mermaid traps (quote special labels, no HTML, ≤ 25
  nodes or split, `stateDiagram-v2` syntax, one diagram per fence); finish with `CLI check`.
- `cam-docs-update`: new step — a change that touches something drawn (a status, an endpoint, a topic, a call)
  runs `CLI diagrams`, then a proposal or `CLI diagrams propose`.
- `cam-docs-lookup`: one line — confirmed diagrams are reliable; proposals are not; generated ones are facts with
  no meaning added.
- `CONVENTIONS.md` §5 and `PLAYBOOK.md` (`diagrams`) carry the same rules.

## 8. Tests first

- Each generator from a `make_workspace` fixture: enums in Java, Kotlin, TS, Python, C#, Go; SQL `CHECK … IN`;
  Rabbit and Kafka topics; Spring endpoints. Assert the Mermaid text, ≤ 25 nodes, the split, quoted labels, sources.
- Block states `new/current/stale/edited/confirmed/confirmed-stale`; refresh (also `--force`) leaves confirmed blocks;
  human pages skipped; an old `generated:schema` block with no `id` unchanged.
- `propose` with a fake runner: writes the proposal; drops fake cites; refuses invalid Mermaid and a proposal with
  no valid cite; `ai: false` and no runner give the documented error.
- Accept/discard through the API: body, markers, `x-sources`, page trust kept, `ai-drafts.json` entry.
- `check` warnings and the error from §4.
- vitest: block parsing and button state; `catalog --check` green.
- Sandbox: `uv run scripts/sandbox.py cli diagrams`, then `cli check` (PetClinic: endpoints maps and context map).

## 9. Docs and version

README (Spanish), `lib/tutorial.py` + regenerated `TUTORIAL.md`, both tutorial templates (existing projects keep
their copy: say so in the commit), `VERSIONS["kit"]` minor bump with the badge.

## 10. Delivery

Two deliveries, each with its own plan, commit(s), docs and minor version:

- **2a — no AI:** §2 (generators, pages, `camaron diagrams`, install hooks), the `confirmed`/`confirmed-stale`
  states and their `check` warning from §4 (so 2b only adds writers), the portal badges from §6, and §7 skills
  (proposal rules included, so agents already write proposals by hand). Useful on its own: install draws them.
- **2b — AI and review:** §3 proposals, §4 accept/discard, §5 `propose` and the PLAYBOOK unit, the rest of §6.

## 11. Out of scope

Reordering the first run, a shorter default plan and a more visual home page (part 3); diagrams of code structure
(the code graph covers it); exporting proposals to a forge.
