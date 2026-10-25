---
name: cam-docs-diagrams
description: Draw and keep {{PROJECT_NAME}}'s Mermaid diagrams — sequence, state, ER, flowchart — and know which ones come from the code, which a person confirmed and which are only an AI proposal. Use whenever you add, change or review a diagram in cam-docs, or when a change touches a status, an endpoint, a topic or a call.
---

# Draw and keep the diagrams

1. Start from the code: `{{CLI}} pages` (`{{CLI}} diagrams` is its alias) writes the pages, with no AI, safe to repeat:
   `{{CAM}}docs/index.md` holds the context map; `{{CAM}}docs/repos/<repo>/index.md` holds the endpoints map and one
   state diagram per status enum; `{{CAM}}docs/architecture/messaging.md` holds one sequence per message topic. A
   project from before 4.52 has `architecture/system-map.md` and `repos/<repo>/diagrams.md` instead, until
   `{{CLI}} pages --adopt`. `{{CLI}} blocks` refreshes every generated block in every page.
2. Pick the diagram that fits (CONVENTIONS §5): business flow → `sequenceDiagram`; anything with a status →
   `stateDiagram-v2`; datastore → `erDiagram` (a cache: a `flowchart` of keys, TTLs, writers, readers); domain →
   context-map `flowchart`; system overview → the C4 `likec4-view`.
3. Know what you are looking at. A block `<!-- generated:<kind> repo=<repo> sha=… -->` … `<!-- /generated:<kind> -->`
   is in one of three states:
   - from the code: facts only. State diagrams list states, with the note "transitions: waiting for a proposal".
   - `confirmed=<sha> by=<name>` in the marker: a person verified it. Trust it; if `{{CLI}} check` says the code
     changed since it was confirmed, propose an update, do not redraw it.
   - a `proposal` block: unreviewed AI work. Never treat it as fact.
4. The rule: never edit a generated block. A refresh rewrites it and a confirmed one is never rewritten. To add meaning
   (transitions, a business flow), write a proposal right after the block, by hand:

   ````
   <!-- proposal:states repo=api id=OrderStatus base=<sha of the block> by=<runner:model> at=<YYYY-MM-DD> -->
   > **Why:** <one line per claim, each ending with its cite `repo:path#Symbol`>
   ```mermaid
   stateDiagram-v2
       …
   ```
   <!-- /proposal:states -->
   ````

   `base` is the `sha` in the generated block's marker. One proposal per block (a new one replaces the old). Every
   claim cites `repo:path#Symbol` and the file and symbol must exist; a claim you cannot cite does not go in. Never
   write a proposal in a page with `x-owner: human`. A person reviews the proposal and applies it; say in your
   summary which proposals are waiting for review.
5. The block kinds are `commands`, `env`, `endpoints`, `topics`, `schema`, the diagram kinds `states`, `endpoints-map`,
   `context`, `messaging`, and `repos`. You may move a generated block, markers included, into the page where it
   belongs (flow, domain, data page, never one with `x-generated: true`); refresh keeps working there and
   `{{CLI}} pages` will not duplicate it.
6. New diagrams the generators cannot know (a business flow's sequence) go in a `draft` page, with `x-sources`.
   Never invent a state, step or transition: unknown → `TODO(question)` and open-questions.md.
7. Mermaid traps: quote labels with special characters (`A["order (paid)"]`); no HTML in labels; one diagram per
   fence; `stateDiagram-v2` (not `stateDiagram`) with `[*]` for start and end; at most 25 nodes, split instead of
   shrinking; no tabs in indentation.
8. Finish with `{{CLI}} check`: no diagram errors, and each warning fixed or explained. Then
   `{{CLI}} checkpoint "diagrams"`.
