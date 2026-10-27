---
type: guide
title: The portal
description: Every zone and view of Camarón's web portal — what you see, what you can do, which address it lives at, and what changes between the live portal and the exported one.
tags: [onboarding, portal]
x-owner: human
---
# The portal

> **TL;DR:** The portal is where the team reads the documentation. Live (`camaron up`, or **View portal** in the app)
> it also edits, confirms, reviews, answers the interview and syncs with the team; exported (`camaron portal`) it is a
> read-only site you can host anywhere. It never runs anything on your machine: that is the
> [desktop app](app.md)'s job.

## Three ways to open it

| How | Command | What it can do |
|---|---|---|
| From the desktop app | **View portal** (header), the Docs section, any "Open in the portal" button | Everything the live portal does, plus writing to the Board and saving stories: the app hands the browser a token for the session |
| Live, from a terminal | `camaron up` (stop it with `camaron down`) | Read, search, edit and create pages, confirm, request changes, review, edit the C4 model, answer the interview, sync with the team, approve or retry plan units. It prints an address with `#cam-token=…`: open that one to also write to the Board and save stories |
| Exported | `camaron portal` (writes `.camarones/.cache/site`); see it with `camaron up --static` or `camaron up --docker` | Read and search only, from static HTML and JSON: no server, no npm, works offline. Host it anywhere (nginx image, GitLab or GitHub Pages). **Edit in the repository ↗** takes you to the page's file in GitLab or GitHub when `cam-docs` has a remote |

The live portal listens only on your machine (`localhost`). It has no login: whoever can open it can edit. The token
in the address is kept for that browser tab only and is removed from the address bar.

### What it never does

Starting or cancelling runs, building the C4 explorer, the code graph or a wiki's graph, generating wikis, scanning
libraries, writing the data pages, generating CI files and answering with AI all run on your machine, so they live in
the desktop app. The portal shows their result, not their buttons.

<!-- go:docs -->

## The frame

**Header**: the project's name (back to Home), where you are (`Architecture › C4 model › index`), **Search** (<kbd>⌘</kbd>
<kbd>K</kbd> / <kbd>Ctrl</kbd> <kbd>K</kbd>, or <kbd>/</kbd>), the trust counts (confirmed, drafts, needing
re-confirmation, change requests not applied yet), the language and ◐ for light or dark.

**Sidebar**: Home and seven zones — Docs, Board, Stories, Architecture, Plan, Quality and Review. The zone you are in
opens its views; below the zones, the panel of what you are looking at (the page tree in Docs, the wikis, the code
map, the C4 views). The exported portal has Docs, Architecture and Review.

**Language.** One selector changes the interface and the documentation together. It appears when the project has
translations; a page with no translation yet is shown in English with a notice.

**All / Business.** At the top of the page tree, and inside any page with technical blocks. Business hides the
`:::tech` blocks and keeps, in the tree and on the Docs home, only the pages about what the system does and why:
overview, domain, glossary, flows and decisions.

**The palette** (<kbd>⌘</kbd> <kbd>K</kbd>): with the live portal, first **Ask** (your text as a question), then **Go
to** (zones and views), **Pages** (by title) and, from two letters, **Content** (full-text hits, and "All results").
<kbd>↑</kbd> <kbd>↓</kbd> move, <kbd>Enter</kbd> opens, <kbd>Esc</kbd> closes.

## Home, search and Ask

**Home** (`#/`) asks first: "Ask anything about the project." The box sends your question to Ask (or, exported, to the
search). Below: the project's home page (`docs/index.md`: what it is, a card per repo, the context map; its nodes open
each repo's page) and the state of the docs — confirmed, to reconfirm, drafts and pending feedback.

A project with no docs yet says so and points at the plan: run its next unit from the desktop app's Plan (or
`camaron run`).

**Search** (`#/search/<words>`): pages that mention it, with up to three highlighted lines each.

**Ask** (`#/ask/<question>`, live): the sections that best answer the question, with their citation and trust, the same
material an agent gets from the MCP. It goes by meaning — "database" finds PostgreSQL, a Spanish question finds English
pages — and needs no AI. A section agents do not get yet (suspect, stale or unreviewed) says so. Writing the answer with
AI is the desktop app's **Docs › Ask with AI**.

<!-- portal:#/ask -->

## Docs

**Docs home** (`#/docs`): the title, the counts (pages, % confirmed, flows, C4 views), a card per section and the
system's context diagram.

**The page tree**: **New page** (live), sections in their usual order, folders that fold, a dot with each page's trust,
and **Working notes** at the end, folded (discovery, interviews, questionnaires).

**A page** (`#/docs/<path>`) shows:

- its **trust**: Confirmed, Draft or Needs re-confirmation — who confirmed it and when;
- its **freshness**: Code up to date, Code changed, Code gone or No sources, against the code it cites in `x-sources`;
- banners when it is an AI draft, needs re-confirmation, cites code that changed or is gone, or its translation is
  missing or out of date;
- **On this page** (the outline), **Previous / Next**, and the **Sources** card: the files it cites, by repo, each with
  its freshness. Hover one to see what changed it (commits, PR or MR, ticket keys). Click to open the lines in your
  editor (VS Code, Cursor, Windsurf, VSCodium, IntelliJ IDEA, WebStorm, PyCharm) or, exported, in the repository.

What you can do on it, live:

| Button | What it does |
|---|---|
| **Edit** | Markdown on the left, live preview on the right; **Save** writes the file and, with "commit to cam-docs" ticked, makes a local commit. Editing a confirmed page makes it need re-confirmation |
| **Confirm as correct** | Signs it with your name (your git user by default): agents treat it as the truth from then on |
| **Request a change** | For the whole page or one section: a comment for the next AI session (it adds the `review-fixes` unit), or **Create a board item →** with the page linked |

**New page** (`#/new`) creates a page of your own (`x-owner: human`), which agents never rewrite.

<!-- portal:#/docs -->

## Wikis

`#/wikis`: one card per repo — pages and when it was updated, or "no wiki yet" / "not cloned" — with **Graph** (the
OpenWiki graph of connected pages) and **Read the pages** (inside the portal, with its own menu and "Linked from").
Generating or updating a wiki is the desktop app's **Docs › Generate the wiki**.

<!-- portal:#/wikis -->

## Board

The Kanban of `cam-docs/backlog/` (`#/kanban`, live), the same cards as the [app's Board](app.md#board).

- **Columns**: Backlog, Ready, In Progress, In Review, Done, Blocked.
- **Cards**: id, type, priority, **Wave N** (tasks of one wave can run at once without touching the same files),
  **Blocked** with why, the parent, assignee, epic, repos and how many linked pages (and how many are suspect).
- **Filters**: repo, epic, label and docs state (out of date, not confirmed), with **Clear**.
- **Move** by dragging or with the keyboard (arrows pick, <kbd>Space</kbd> grabs, arrows move, <kbd>Enter</kbd> drops,
  <kbd>Esc</kbd> cancels). Into In Progress, the **start gate** checks dependencies and file collisions and offers
  **Move anyway**.
- **A card** (`#/kanban/<ID>`): status, type, priority, assignee, epic, repos, its file; **Goal** (description,
  acceptance criteria, definition of done), **Knowledge** (linked pages with their trust, and whether they changed
  since they were linked) and **History**.
- **+ Add** creates an item with its linked page. `#/kanban?parent=WI-14` shows a story with its subtasks.

Without the token (a plain `camaron up` address, or an export) the Board is read-only and says why.

<!-- portal:#/kanban -->

## Stories

`#/stories` (live) is where a story is written well and split into subtasks that do not collide. The verdict, the
subtasks and the waves come from rules and the code map, never from AI: the same board always gives the same answer.

1. **Write the story**: *As / I want / so that*, with instant hints (generic role, two goals in one, a "so that" that
   repeats the "I want", too long, a solution inside the "I want", no footprint). The title follows the "I want".
   **Touches** is the footprint: the files, code groups and pages it changes; type `repo:path` to add a file a task
   will create. Pages the story links fill it from their sources.
2. **Review**: the INVEST verdict (Good, Could be better, Not ready) with a reason per letter, the acceptance criteria,
   the footprint and the overlaps with other open stories.
3. **Proposed subtasks**: one task per code group and one per page, with dependencies (who provides goes before who
   uses), collisions and **waves**. Edit titles, remove, add, merge; the waves recompute at once.

Nothing is written until **Add the story + n subtasks to the backlog** (or **Save**). Saving an existing story writes
only what you changed: what someone else changed meanwhile is kept, and if you both changed the same thing it asks you
to reload. **✨ Suggest with AI** appears in the three steps and spends only when pressed; it
only suggests — never footprints, dependencies, waves or the verdict — and it is off, with the reason, without an
agent, without the token, or with `stories: {ai: false}`. While it thinks the button shimmers and cannot be pressed
again (<kbd>Esc</kbd> cancels); what it proposes stays in this browser, per story, until you accept or dismiss it,
even if you ask for something else, open another story or reload. A draft you leave half written is kept too.

<!-- portal:#/stories -->

## Architecture

**C4 model** (`#/c4/<view>`): the views are listed in the sidebar (system, containers and components, flows,
deployment) and `#/c4` opens the first. Each view shows its diagram and, live, **its elements**: their kind,
technology, description and relations, AI drafts first. You can **Edit** an element, add or remove a relation,
**Remove** an element (its children, relations and mentions go too; the scope of a view cannot be removed), and
**Confirm** one or **the whole view** (`#ai-draft` becomes `#confirmed`, with who and when). Every change touches only
those lines of the `.c4` file and is checked with LikeC4; if it breaks the model it is not saved. The diagram is
redrawn when the C4 explorer is rebuilt from the desktop app. **Read the flow** opens a flow's page; the full explorer
opens from the sidebar.

**Code graph** (`#/code`): the graphify graph as a readable map — each repo's modules and their dependencies, the most
used files, packages and, per file, what it uses and who uses it — with a search box. The raw graph is a click away.

**Data** (`#/data`, live): each repo's tables and collections read from the code, with the ER diagram and their fields.

**Libraries** (`#/libs`, live): every repo's direct dependencies as a library × repo matrix, with filters (category,
language, repo, scope, only vulnerable); vulnerable ones first, with their advisories and the version that fixes
them. `#/libs/<repo>` opens it for one repo.

<!-- portal:#/c4 -->

## Plan

**Pipeline** (`#/pipeline`, live): the plan as a **Graph** (units by phase, with their dependencies) or a **Board** (to
do, running, blocked, done, dropped). A unit's panel: its agent, outcome, time, tokens and cost, whether it worked in its
own copy, what it waits for, its notes and the agent's live log. **Approve** lets the units after one waiting for a
person start; **Retry** puts a blocked one back in the queue. Running and cancelling are the app's (Plan). A run
stopped from outside (its job stopped, its process killed) shows as finished within a few seconds, not as running.

**Interview** (`#/interview`, live): when the interviews run as a team questionnaire, each person answers here — what
was inferred from the code with its evidence, the options, "Other" and a comment. It saves the same file as the offline
form, so both mix, and whoever comes back sees their answers to change them. At the top: who answered, what nobody
answered and where people disagree.

**Sync** (`#/sync`, live): this `cam-docs` against the team's repo — your commits not shared, theirs not here, when
this machine last shared, and files not saved yet. **Sync with the team** does what `camaron share` does (a
checkpoint, the team's work in, yours out); **Check for news** asks the remote. A conflict is undone; a possible secret
blocks the push.

<!-- portal:#/pipeline -->

## Quality

**Health** (`#/health`, live): the same verdict, three areas and repo table as the app's Quality, read-only, from the
last check. Rows link to Review, Libraries or KPIs; checking again is done in the app or with `camaron health`.
`#/health/<repo>` is one repo in full: its SonarQube gate and nine figures, coverage and the reports that give it, its
vulnerable libraries, its technical debt by the page it comes from and the pages that cite its code and are out of date.

**KPIs** (`#/kpis`, live): is the documentation working? **Plan from zero** (what the plan cost), pages and C4 elements
confirmed, pages out of date, searches with no answer, units done, AI cost this month, golden questions, trust per repo
and the **Questions nobody found** — each one **Add to open questions** (for the next interview) or **Dismiss**.

**CI** (`#/ci`, live): the pipeline files in `cam-docs` and whether they still match the kit's definition, what
`check` says now, the snippet for each service repo with **Copy**, and the last pipeline when `gh` or `glab` is signed
in. Generating the files is the desktop app's.

<!-- portal:#/health -->

## Review

`#/review`: what waits for a person. Filter drafts or pages to reconfirm; each shows where it comes from (`x-sources`).
Live, tick several (<kbd>j</kbd> <kbd>k</kbd> move, <kbd>x</kbd> ticks, <kbd>Enter</kbd> opens) and **Confirm the n**
at once. Below: **Reviews an agent is waiting for** (an agent ran `camaron review request` and waits: **Approve** or
**Ask for changes**), then the change requests, the repos whose code changed since the docs, and the checks.

<!-- portal:#/review -->

## What pages can do

The portal renders Markdown with a few extras; agents read the same files as plain Markdown.

| You write | You get |
|---|---|
| `> [!NOTE]` (TIP, IMPORTANT, WARNING, CAUTION) | A callout |
| `:::tabs` with `::tab Label` | Tabs |
| `:::steps`, `:::details Summary`, `:::cards` | Numbered steps, a fold, cards |
| `:::tech` | A block that Business hides |
| `:::rule ORD-1 Title` with `enforced:` and `test:` lines | A business rule card; `camaron check` fails when its code is gone |
| A table | Sortable by column; a filter from eight rows |
| A code block | Highlighted, with **Copy** |
| A Mermaid diagram | Drawn, with full screen and zoom; names that match a page or a repo are links |
| `<!-- generated:… -->` blocks | A label: From the code, Confirmed by…, The code changed, Edited by hand |
| A flow page (`flows/<slug>.md`) | Its dynamic C4 view, interactive, after its first paragraph |

## Addresses

| Address | View |
|---|---|
| `#/` | Home |
| `#/docs`, `#/docs/<path>`, `#/new` | Docs home, a page, a new page |
| `#/wikis`, `#/wiki/<repo>`, `#/wiki/<repo>/<page>` | Wikis, a wiki's graph, a wiki page |
| `#/kanban`, `#/kanban/<ID>`, `#/stories` | Board, a card, Stories |
| `#/c4`, `#/c4/<view>`, `#/code`, `#/data`, `#/libs` | Architecture |
| `#/pipeline`, `#/interview`, `#/sync` | Plan |
| `#/health`, `#/health/<repo>`, `#/kpis`, `#/ci` | Quality |
| `#/review`, `#/search/<words>`, `#/ask/<question>` | Review, search, Ask |

Old addresses (`#/doc/…`, `#/status`, `#/wikis/<repo>`) still work.
