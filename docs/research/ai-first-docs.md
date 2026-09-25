# AI-first documentation: prompts and quality gate

Proposal, 2026-09-25. **Status: proposed**, not implemented yet. The goal is to have the plan units write docs that
**AI agents can read first** and that humans still find pleasant: pages an agent can find, read in pieces and trust
without going back to the code for every claim.

**How to read it**

- Principles have IDs `W1`–`W9` and changes have IDs `P1`–`P10`, so each one can be discarded or implemented on its own.
- Paths are relative to the kit repo, and line numbers are from 2026-09-25.
- §3 lists the decisions already taken. Everything else is open to discussion.

## 0. The problem today

How a unit's instructions reach the agent:

| Layer | Where | What it gives the agent |
|---|---|---|
| Generic brief | `plan.prompt()`, `.camarones/lib/plan.py:331` | The same text for every unit: read PLAYBOOK + CONVENTIONS, claim, note, close. Nothing about how to write. |
| Unit section | `.camarones/PLAYBOOK.md`, one `## <type>` per unit | Which files to produce. Only some sections name the required content (discovery, quick-overview, flow). |
| Format rules | `.camarones/CONVENTIONS.md` §2 frontmatter, §6 page templates | Page structures described in prose only. There is no skeleton file to copy. |
| Enforcement | `CLI check`: `docs.check()` + `quality.CHECKS` (`quality.py:239`) | Checks that a frontmatter block exists, orphan sources, links, Mermaid, secrets and glossary words. Nothing checks structure. |

Gaps:

- **No writing rules.** There is no answer-first rule, no length budget, no heading depth limit and no rule for sections
  that must stand alone. Nothing asks for exact identifiers or inline evidence.
- **`description` is described as "retrieval-oriented" but is not enforced.** It is the only line per page in
  `llms.txt` and `list_docs`.
- **No required sections.** An agent can skip half of the 8 flow sections and `check` stays green.
- **No stable anchors.** The portal renders no heading ids, even though `app.js` already scrolls to `#anchor`.
  `check_links` skips `#anchors`, and `read_doc` always returns the whole page.
- **`llms.txt` is an index only.** There is no `llms-full.txt`, and the index does not follow the llmstxt.org format.
- **Inconsistent prompts:**
  - The `repo-brief` title (`plan.py:39`) says "README + AGENTS.md/CLAUDE.md", but PLAYBOOK `repo-brief` says
    *not* to edit them. The real output is `docs/repos/<repo>/brief.md`.
  - CONVENTIONS §4 ("Repo READMEs embed the Mermaid export") contradicts §7 ("Service repos carry no kit files").

## 1. AI-first principles

The main reader is an agent that gets **fragments**: one `search_docs` hit, one `read_doc`, one grep match or one
`llms.txt` line. Every rule follows from that.

| ID | Principle | Rule | Why it helps an agent |
|---|---|---|---|
| W1 | Answer first | Every page opens with `> **TL;DR:** …` (2–4 lines) right under the H1 | The agent decides whether the page is relevant from the first lines, without reading all of it. Humans skim the same way. |
| W2 | Self-contained sections | Each H2 can be read alone: no "as mentioned above", "this service", "see below". Name the thing again. | Retrieval returns chunks. A pronoun that points to another section is lost context. |
| W3 | Exact identifiers | Endpoints (`POST /orders`), topics, tables, classes, env vars, C4 ids and repo names are in backticks, spelled exactly as in the code. Use the glossary's canonical term. | Agents grep and match tokens. A paraphrase ("the order endpoint") matches nothing. |
| W4 | Tables for facts, prose for why | Endpoints, commands, env vars, ownership and steps go in tables. Commands go in fenced blocks and say which folder they run in. | Tables parse reliably, and commands can be copied and run. |
| W5 | Evidence next to the claim | Keep the page-level `x-sources`, and add inline `(evidence: repo:path#Lx-Ly)` in table rows and critical claims | A chunk carries its own proof. The agent can verify it without opening the frontmatter. |
| W6 | Budgets | A page is at most ~1500 words, an H2 at most ~400 words, headings at most 3 levels deep and no skipped levels. Split rather than compress. | Small, well-cut chunks rank better and fit in context. |
| W7 | Retrieval metadata | `description` is required (40–300 characters and answers "what question does this page answer?"). A new optional `x-answers:` field holds up to 5 literal questions. `tags` come only from repo names, glossary terms and C4 ids. | Search and `llms.txt` match the questions agents actually ask, and the tag vocabulary stays consistent. |
| W8 | Explicit uncertainty | Unknown → `TODO(question): …`. Never fill a section to look complete. (This rule already exists.) | An agent can tell a gap from a fact. |
| W9 | Humans second | Mermaid stays, but every diagram has a table or text equivalent. Translations stay natural (CONVENTIONS §8). | Diagrams help humans, and the text keeps the same facts readable by an agent. |

## 2. Proposed changes

| ID | Change | Files | Enforced by |
|---|---|---|---|
| P1 | **Writing rules, single source.** New CONVENTIONS §11 "Writing for agents (AI-first)" with W1–W9 as short, testable rules. §2: `description` required, `x-answers` and `tags` vocabulary. §10: new rows. Fix §4, where the Mermaid export goes in `brief.md`, not in READMEs. | `.camarones/CONVENTIONS.md` | P5 |
| P2 | **Skeletons per page type**, filled with placeholders: frontmatter, H1, TL;DR, required H2s, example tables. Types: `overview`, `business-flow`, `data-model`, `decision`, `glossary`, `bounded-contexts`, `deployment`, `quality`, `repo-brief`, `threat-model`, `findings`. They live in `.camarones/skeletons/`, not in `templates/docs/`, so `docs.collect()` never treats them as pages. **They are the source of truth for required H2s**: the check parses them, so there is no second list to keep in sync. | `.camarones/skeletons/*.md` | P5, tests |
| P3 | **A uniform contract per PLAYBOOK unit**: every section that writes pages ends with `Output:` · `Skeleton:` · `Done when:` (the unit's checklist + "`CLI check` has no AI-readability WARNs on your pages"). `doc-fixes` gains a step for these WARNs. `update` and `review-fixes` keep the rules when editing. | `.camarones/PLAYBOOK.md` | review |
| P4 | **Generic brief.** `plan.prompt()` gets an inline "Audience and writing rules" block of about 6 lines (agents first, humans second, W1–W7 in one line each, link to §11), so the rules are in context even if the agent skims the playbook. Before `plan done` the agent must run `CLI check` and fix WARNs on its own pages. Also fix the `repo-brief` title in `TYPES` (`plan.py:39`), and review `arch_prompt()` (`wizard.py:1219`) and `wiki_prompt()` (`env.py:714`) under the same rules. | `.camarones/lib/plan.py`, `wizard.py`, `env.py` | tests |
| P5 | **New `quality.check_structure`** in `CHECKS` (`quality.py:239`). It covers canonical pages with a kit `type`. It skips `interview` pages, OpenWiki pages (OKF frontmatter) and translations (their headings are translated). Rules: `type` in the enum; `title`/`description` present and within bounds; exactly one H1; no skipped heading levels; TL;DR under the H1; required H2s from the type's skeleton; W6 budgets (prose only, not code or tables); vague references ("see above/below", "as mentioned", "click here", "aquí", "arriba"). It reuses `prose_lines()` and `pages()`. Thresholds are constants at the top of `quality.py`. | `.camarones/lib/quality.py` | WARN, ERROR with `--strict` |
| P6 | **Stable anchors.** Add `docs.slug(heading)` in GitHub style (accents, `ñ`), mirrored in `portal/live/app.js` so headings get `id`s. This is the same Python/JS mirror pattern as `resolve()`. `check_links` then validates `#anchor` on internal links instead of skipping it. | `docs.py`, `quality.py`, `portal/live/app.js` | `check_links` (ERROR) |
| P7 | **Section-level retrieval in the MCP server.** `read_doc(path, section=None)` returns the trust header + TL;DR + only that H2 (by heading or slug). `search_docs` hits report the H2 slug where they matched, so the next call can be `read_doc(path, section)`. `docs.search()` gives `description` and `x-answers` the same boost as the title. | `.camarones/lib/mcp.py`, `docs.py` | tests |
| P8 | **`llms.txt` + `llms-full.txt`.** `llms.txt` follows llmstxt.org: H1 is the project name, the blockquote is the `description` of `docs/index.md` plus the trust legend, sections are H2, and `interview/` goes under `## Optional`. New `docs/llms-full.txt` holds every canonical non-interview page in the same order, with its frontmatter replaced by `<!-- path · trust · description -->`. The same `CLI llms` writes both, so the static export (`env.py:917`) and `/api/commit` (`serve.py:283`) get it for free. Takes up J6 from [tooling-candidates.md](tooling-candidates.md). | `docs.llms()` | tests |
| P9 | **Agent entry points.** `templates/AGENTS.md` gets a short "to do X, read Y" routing table (repo → brief, flow → `flows/`, term → glossary, decision → ADRs) and recommends `search_docs` → `read_doc(section)` first. The `cam-docs-lookup` skill documents the same retrieval order and weighing by trust. The `cam-docs-update` skill says to keep §11 when editing. The first two are managed blocks, so `refresh_block()` updates existing projects. | `templates/AGENTS.md`, `templates/skills/cam-docs-*/SKILL.md` | — |
| P10 | **User docs.** The quality gate table and a short AI-first paragraph in the tutorial (EN + ES), plus CONVENTIONS §10. | `templates/docs/guides/tutorial.md`, `templates/docs/i18n/es/guides/tutorial.md` | — |

Suggested order: P1 + P2 → P5 (then the rules are enforced) → P3 + P4 (prompts point to rules that exist) → P6 → P7
→ P8 → P9 + P10.

## 3. Decisions taken

- **Scope: prompts and tools** (P1–P10), not just a rewrite of the prompt text.
- **Severity: WARN by default, ERROR with `--strict`**, the same as the glossary check. Projects that are already
  documented keep passing `check`, and the `doc-fixes` unit migrates them (P3).
- **Skeletons are the single source of required sections** (P2). The check derives them, so there is no parallel
  dict to keep in sync.
- **English stays canonical.** Structure checks run on canonical pages only.

## 4. Tests and verification

Tests (`tests/`, same pattern as `test_quality.py`):

- `test_quality.py`: one case per `check_structure` rule, `--strict` promotes WARN → ERROR, interview/OpenWiki pages
  are skipped, and internal links with a valid or missing `#anchor` behave correctly.
- New `test_prompts.py`:
  - every `TYPES[t][3]` has a `## <section>` in PLAYBOOK.md;
  - every skeleton that PLAYBOOK names exists;
  - **every skeleton passes `check_structure` with no WARNs**;
  - `plan.prompt()` contains the writing-rules block.
- `llms`: `llms.txt` has an H1, a blockquote and `## Optional`, and `llms-full.txt` contains every non-interview page
  without YAML frontmatter.
- `mcp`: `read_doc(path, section)` returns only that H2 + TL;DR, and `search_docs` hits carry the section.
- `slug()`: accents and `ñ`.

End to end:

1. `uv run pytest` passes.
2. On the fixture workspace or a real project:
   - `camarones check` gives WARNs on legacy pages and nothing breaks;
   - `check --strict` turns them into ERRORs.
3. `camarones prompt flow:<slug>` and `prompt repo-brief:<repo>` show the rules block and the fixed title.
4. `camarones llms` writes both files. Read them.
5. The MCP `read_doc` call with `section` over stdio returns a single section.
6. `camarones up`: headings have `id`s, and a link with `#anchor` scrolls to the right place.
7. Run one real `flow` unit with the new prompt, and check that `check` is clean on its pages.

## 5. Open points

- **Distribution.** Check how `.camarones/` (PLAYBOOK, CONVENTIONS and the new skeletons) reaches projects that were
  created before the change. If it is a copy that never overwrites, the skeletons need the same update path as the
  playbook.
- **Thresholds.** The limits are 1500 words per page, 400 words per H2 and 40–300 characters for `description`. They
  are first guesses and stay tunable constants. Adjust them after running the check on a real project.
- **`x-answers`** is optional. If it doesn't improve search hits on a real project, drop it and keep `description`
  only.
