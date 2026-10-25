# First docs (3a): a project home and one page per repo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fresh install (no AI) writes a short project home (`docs/index.md`) and one page per repo
(`docs/repos/<repo>/index.md`) instead of `first-look.md`, `system-map.md`, `reference.md`, `diagrams.md` and
`data/<repo>.md`; existing projects keep their layout until they run `camaron pages --adopt`.

**Architecture:** A new `lib/pages.py` owns the layout question (`layout()`), the facts the TL;DRs and cards are made of,
the three new pages (home, repo page, messaging page), their writer and `adopt`. It reuses 2a's generated blocks
(`genblocks`, `diagrams`) unchanged in format; one new block kind, `repos` (`repo=_system`), holds the repo cards. Every
caller that used to write an old page (install, first look, `blocks`, `schemas`, `arch-draft --save`, the portal's Data
button) asks `pages.layout()` first; in an old-layout project it behaves exactly as today.

**Tech Stack:** Python 3 (stdlib + PyYAML, already a dependency), pytest; the portal's legacy plain-JS views and its
Vite build (`npm run build` in `.camarones/portal/app`, output committed in `app-build/`).

**Spec:** `docs/superpowers/specs/2026-10-25-first-docs-design.md`

## Global Constraints

- macOS, Windows and Linux: `pathlib` only, `encoding="utf-8"` on every read and write, `newline="\n"` on writes; no
  `sys.platform` checks (AGENTS.md §2.1).
- TDD: every task starts with a failing test. Run tests with `uv run python -m pytest …` (on this Windows machine the
  `.venv` `pytest.exe` is blocked by App Control).
- Backward compatibility (AGENTS.md §2.3): a 3.x/4.x project's pages never move or vanish unless `camaron pages --adopt`
  is run; `camaron diagrams` stays as an alias of `pages`; no CLI command, flag or frontmatter field is renamed or dropped.
- A page with `x-owner: human` is never written. A block with `confirmed=` or edited by hand is never rewritten.
- Generated pages: `x-generated: true`, `x-owner: ai`, `type: overview`, an H1, then `> **TL;DR:** …` right under it.
- TL;DRs are about the project and built from facts. A zero count is said plainly ("no message topics", "no tables"),
  never left out. How a page is made goes in a final `:::details How this page is made` block.
- Directives (`:::cards`, `:::details …`) wrap generated blocks from outside; a generated block's body holds only data.
- New user-facing portal strings exist in `es` and `en` (`public/legacy/core.js`); no jokes in generated pages.
- No new dependency. Kit version: `VERSIONS["kit"]` → `4.52.0` (README badge too).
- Parallel sessions share this repo: stage only your own hunks. Never commit the main checkout's loose title-bar edits or
  the four untracked docs (`docs/superpowers/specs/2026-10-24-board-design.md`,
  `docs/superpowers/plans/2026-10-25-board-1a.md`, `docs/research/dev-harness-requirements.md`,
  `docs/research/spec-v0.1-gap.md`).

## Review Focus

- An agent (or a person in the portal editor) adds prose to a kit page and leaves `x-generated: true`: `camaron pages`
  must keep that prose and only bring the page's blocks up to date (Task 3, `test_prose_in_a_kit_page_is_kept`).
- Not every repo is cloned on this machine: the home and its system-wide blocks are left as they are, repo pages are
  written for the repos that are here (Task 3, `test_a_partial_clone_leaves_the_home_alone`).
- A repo where the scan finds nothing (no endpoints, tables, topics, env vars or commands) still gets a page and a card
  that say so plainly (Task 2, `test_an_empty_repo_says_what_it_lacks`).
- In a new-layout project the old commands (`blocks`, `schemas`, `arch-draft --save`, the portal's Data "write page"
  button) must not create an old page that would flip the project back to the old layout (Task 4,
  `test_old_commands_do_not_write_old_pages_in_the_new_layout`).
- `--adopt` on a project whose briefs link to `reference.md`: links in unconfirmed pages point to the repo page
  afterwards, confirmed pages are listed instead, and `check` reports no broken link (Task 6,
  `test_adopt_relinks_and_check_has_no_broken_link`).

---

### Task 1: Facts and the `repos` block

**Files:**
- Create: `.camarones/lib/pages.py`
- Modify: `.camarones/lib/genblocks.py` (kinds, `render`, `Scanner.get`, `states`)
- Test: `tests/test_pages.py`

**Interfaces:**
- Produces (in `lib/pages.py`):
  - `SYSTEM = "_system"`, `HOME = "index.md"`, `REPO_PAGE = "repos/{repo}/index.md"`, `MESSAGING = "architecture/messaging.md"`
  - `count(n: int, noun: str, plural: str | None = None) -> str` — `count(0, "endpoint") == "no endpoints"`,
    `count(1, "endpoint") == "1 endpoint"`, `count(35, "endpoint") == "35 endpoints"`, `count(2, "repo") == "2 repos"`;
    `plural` for irregular nouns (`count(3, "direct dependency", "direct dependencies")`).
  - `facts(memo: dict | None = None) -> dict` — `{"project": str, "repos": {name: {"kind": str, "stack": str,
    "endpoints": int, "tables": int, "engines": [str], "publishes": [topic], "consumes": [topic], "calls": [repo],
    "states": int, "env": int, "commands": int}}, "dependencies": int, "sources": [str]}` for the repos present on this
    machine, in `docs.repo_names()` order. `stack` = `quickarch.scan()["repos"][name]["tech"]` (honours a fixed stack);
    `endpoints` = distinct (method, path) of `genblocks.endpoint_rows`; `tables` = entities of `schemas.scan_repo`;
    `engines` = sorted labels of `quickarch.scan()["dbs"]` the repo uses; `calls` = sibling repos from the scan's
    `calls…` edges; `dependencies` = rows of `inventory.load()` or else `inventory.scan()`. Cached in `memo["facts",]`;
    the architecture scan is shared through `diagrams._scan(memo)`.
  - `repos_block(memo: dict | None = None) -> tuple[str, list[str]] | None` — the `repos` block body: one line per
    repo, `- [<repo>](repos/<repo>/index.md): <stack> · <count endpoints> · <count tables> · <count topics>` (topics =
    distinct published + consumed); None when no repo is present or not every repo is on this machine.
- Produces (in `lib/genblocks.py`): `PAGE_KINDS = ("repos",)`; `render("repos", "_system", None)` delegates to
  `pages.repos_block`; `Scanner.get` and `states` accept `PAGE_KINDS` (not in `KINDS`: it never joins a reference page).

- [ ] **Step 1: Write the failing tests** in `tests/test_pages.py`, with a fixture `pg(kit)` like `dg` in
  `tests/test_diagram_blocks.py` (a `put(repo, rel, text)` helper plus `mod = lib.pages`, `gb = lib.genblocks`):

```python
def test_count_says_zero_plainly(pg):
    assert pg.mod.count(0, "endpoint") == "no endpoints"
    assert pg.mod.count(1, "table") == "1 table" and pg.mod.count(9, "table") == "9 tables"
    assert pg.mod.count(3, "direct dependency", "direct dependencies") == "3 direct dependencies"

def test_facts_count_what_the_code_states(pg):
    pg.put("api", "src/main/resources/openapi.yaml", OPENAPI)            # 3 operations, one path twice in two files
    pg.put("api", "src/main/resources/db/migration/V1__init.sql", SQL)   # 2 tables
    pg.put("api", "src/main/resources/application.properties", "spring.datasource.url=jdbc:postgresql://localhost:5432/pets\n")
    f = pg.mod.facts()["repos"]["api"]
    assert (f["endpoints"], f["tables"], f["engines"]) == (3, 2, ["PostgreSQL"])
    assert f["publishes"] == [] and f["calls"] == ["worker"]             # the fixture's Api.java mentions worker

def test_the_repos_block_has_one_card_per_repo(pg):
    body, sources = pg.mod.repos_block()
    lines = body.splitlines()
    assert lines[0].startswith("- [api](repos/api/index.md): ") and len(lines) == 3
    assert "no endpoints" in lines[1] and "no tables" in lines[1] and "no topics" in lines[1]

def test_a_repos_block_refreshes_through_genblocks(pg):
    page = pg.kit.root / "docs" / "index.md"
    page.write_text("# demo\n\n" + pg.gb.block("repos", "_system", "old") + "\n", encoding="utf-8")
    pg.gb.refresh()
    assert "repos/web/index.md" in page.read_text(encoding="utf-8")

def test_the_repos_block_is_unknown_when_a_repo_is_missing(pg):
    pg.rmtree(pg.kit.ws / "worker")
    assert pg.mod.repos_block() is None
    states = [s for _m, s, _b in pg.gb.states(pg.gb.block("repos", "_system", "x"), pg.gb.Scanner())]
    assert states == ["unknown"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run python -m pytest tests/test_pages.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.pages'`

- [ ] **Step 3: Implement `count`, `facts`, `repos_block` in `lib/pages.py` and the `repos` kind in `lib/genblocks.py`**

Module docstring in the style of `lib/diagrams.py` (what the module owns, the two layouts). `genblocks.render` imports
`pages` inside the function (pages imports genblocks at the top).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run python -m pytest tests/test_pages.py tests/test_genblocks.py tests/test_diagram_blocks.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/pages.py .camarones/lib/genblocks.py tests/test_pages.py
git commit -m "feat(pages): facts about each repo and a repos block of cards, from the code"
```

### Task 2: Layout detection and the three pages as text

**Files:**
- Modify: `.camarones/lib/pages.py`
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: `facts`, `repos_block`, `count` (Task 1); `diagrams.ids/render`, `genblocks.render/block`, `docs.join_fm`.
- Produces:
  - `old_pages() -> list[Path]` — the old-layout pages that exist: `docs/repos/*/reference.md`, `docs/repos/*/diagrams.md`,
    `docs/data/<repo>.md` with `x-generated: true` for a workspace repo, `docs/architecture/first-look.md`,
    `docs/architecture/system-map.md`.
  - `layout() -> str` — `"new"` when a docs page holds a `generated:repos` block; else `"old"` when `old_pages()` is not
    empty; else `"new"`.
  - `Key = tuple` `(kind, repo, id or None)`; `TARGET: dict[str, tuple[str, str, str | None]]` — kind → (page pattern,
    section heading, `:::details` summary or None):
    `repos → (HOME, "", None)` (the cards, right under the TL;DR, inside `:::cards`), `context → (HOME, "Context map",
    None)`, `messaging → (MESSAGING, "Messaging", None)`, `endpoints-map → (REPO_PAGE, "What it exposes", None)`,
    `endpoints → (REPO_PAGE, "What it exposes", "Endpoints")`, `schema → (REPO_PAGE, "Data", None)`,
    `states → (REPO_PAGE, "Lifecycles", None)`, `topics → (REPO_PAGE, "Messages", None)`,
    `env → (REPO_PAGE, "What it needs to run", "Environment variables")`,
    `commands → (REPO_PAGE, "What it needs to run", "Commands")`.
  - `home_tldr(f: dict) -> str`, `repo_tldr(name: str, f: dict) -> str` — the sentences (copy below).
  - `home_page(memo: dict, skip: set[Key] = frozenset()) -> str | None`, `repo_page(repo: str, memo: dict,
    skip: set[Key] = frozenset()) -> str | None`, `messaging_page(memo: dict, skip: set[Key] = frozenset()) -> str | None`
    — a whole page written from scratch (frontmatter + body), with a block for every key the code has except those in
    `skip` (they live in another page); None when the page has nothing to show (home: no repo present or not all repos
    here; repo page: repo not here; messaging: no topic). Sections and `:::details` with no block are left out.

TL;DR copy (exact; `count` for every number; `join` = "a, b and c"):
- Home: `{project} has {count(n, "repo")} ({stacks, distinct, in repo order, ", "-joined}): {count(endpoints, "endpoint")},
  {count(tables, "table")}, {count(topics, "message topic")}, {count(deps, "direct dependency", "direct dependencies")}.`
- Repo: `` `{repo}` is a {stack} {noun}: {endpoints}, {tables}; {messages}; {calls}. `` with noun per workspace kind
  (`service` → service, `webapp` → web app, `mobileApp` → mobile app, `library` → library, `infra` → infrastructure repo);
  tables `no tables` | `9 tables` | `9 tables in its PostgreSQL database` | `9 tables in its PostgreSQL and MySQL
  databases`; messages `it publishes and consumes no messages` | `it publishes 2 topics` | `it consumes 1 topic` |
  `it publishes 2 topics and consumes 1`; calls `it calls no other repo` | `it calls web and worker`.

Page shapes (frontmatter: `type: overview`, `title`, `description`, `tags` ([repo] on a repo page), `x-sources`,
`x-owner: ai`, `x-generated: true`):
- Home — title = project; description `"{project} at a glance: its repos, how they connect and where to read on (a static
  scan, no AI)."`; body: `# {project}`, TL;DR, `:::cards` / repos block / `:::`, `## Context map` + context block,
  `## More` with `- [Stack and tooling](overview/tooling.md)`, `- [Libraries](overview/libraries.md)` and, only when there
  are topics, `- [Messaging](architecture/messaging.md)`, then the details block.
- Repo page — title = repo; description `"What {repo} exposes, stores and needs to run, read from its code (a static scan,
  no AI)."`; body: `# {repo}`, TL;DR, then the sections of `TARGET` in this order: What it exposes, Data, Lifecycles,
  Messages, What it needs to run; then the details block.
- Messaging page — title `Messaging`; one `messaging` block per topic under `## Messaging`; details block.
- Details block (exact; `{tutorial}` is the relative link to `guides/tutorial.md` from the page):
  ```
  :::details How this page is made
  Read from the code with no AI. `camaron pages` brings it up to date and `camaron blocks` refreshes the diagrams and
  tables in every page. A person can confirm a diagram so that no refresh rewrites it: see [the tutorial]({tutorial}).
  :::
  ```

- [ ] **Step 1: Write the failing tests** (same file):

```python
def test_a_fresh_project_is_new_layout(pg):
    assert pg.mod.layout() == "new"

@pytest.mark.parametrize("rel", ["repos/api/reference.md", "repos/api/diagrams.md", "architecture/first-look.md",
                                 "architecture/system-map.md"])
def test_any_old_page_makes_the_layout_old(pg, rel):
    write_doc(pg, rel, "# old\n")
    assert pg.mod.layout() == "old"

def test_a_hand_written_data_page_is_not_an_old_page(pg):
    write_doc(pg, "data/api.md", "---\ntitle: api data\n---\n# api data\n")      # no x-generated
    assert pg.mod.layout() == "new"

def test_the_home_with_cards_wins_over_a_kept_old_page(pg):
    write_doc(pg, "repos/api/reference.md", "# old\n")
    write_doc(pg, "index.md", "# demo\n\n" + pg.gb.block("repos", "_system", "x") + "\n")
    assert pg.mod.layout() == "new"

def test_the_home_says_the_facts_and_zero_counts(pg):
    text = pg.mod.home_page({})
    assert "> **TL;DR:** demo has 3 repos (" in text and "no message topics" in text
    assert "\n:::cards\n<!-- generated:repos repo=_system" in text and "## Context map" in text
    assert "architecture/messaging.md" not in text                              # no topics: no link
    assert text.rstrip().endswith(":::") and text.index("## More") < text.index(":::details How this page is made")

def test_the_repo_page_puts_diagrams_first_and_tables_folded(pg):
    pg.put("api", "src/main/resources/openapi.yaml", OPENAPI)
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    text = pg.mod.repo_page("api", {})
    order = [text.index(h) for h in ("## What it exposes", "generated:endpoints-map", ":::details Endpoints",
                                     "generated:endpoints ", "## Lifecycles", "## What it needs to run",
                                     ":::details Commands", ":::details How this page is made")]
    assert order == sorted(order)
    assert "## Data" not in text and "## Messages" not in text                  # nothing to show: no section

def test_an_empty_repo_says_what_it_lacks(pg):
    text = pg.mod.repo_page("worker", {})
    assert "no endpoints" in text and "no tables" in text and "publishes and consumes no messages" in text
    assert "## What it exposes" not in text

def test_a_skipped_key_is_not_drawn_again(pg):
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    assert "OrderStatus" not in pg.mod.repo_page("api", {}, skip={("states", "api", "OrderStatus")})

def test_the_messaging_page_exists_only_with_topics(pg):
    assert pg.mod.messaging_page({}) is None
    pg.put("api", "src/main/java/demo/Pub.java", PUBLISHER)                     # kafkaTemplate.send("orders", …)
    assert "generated:messaging repo=_system id=orders" in pg.mod.messaging_page({})

def test_the_generated_pages_pass_check(pg):
    for rel, text in (("index.md", pg.mod.home_page({})), ("repos/api/index.md", pg.mod.repo_page("api", {}))):
        write_doc(pg, rel, text)
    errors = [i for i in pg.kit.quality.check()["errors"] if "index.md" in i]   # use the suite's existing check helper
    assert errors == []
```

(`write_doc` writes under `kit.root / "docs"`; `OPENAPI`, `ORDER`, `SQL`, `PUBLISHER` are small module constants —
reuse the shapes in `tests/test_diagram_blocks.py`. Use whatever `quality` entry point the existing tests use for the
check run.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run python -m pytest tests/test_pages.py -q`
Expected: FAIL with `AttributeError: module 'lib.pages' has no attribute 'layout'`

- [ ] **Step 3: Implement `old_pages`, `layout`, `TARGET`, the TL;DRs and the three page functions**

Draw blocks with one `genblocks.Scanner` per pass (its `memo` is the pass's `memo`) so a page never scans twice.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run python -m pytest tests/test_pages.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/pages.py tests/test_pages.py
git commit -m "feat(pages): the project home, the repo page and the messaging page, about the project"
```

### Task 3: Writing the pages

**Files:**
- Modify: `.camarones/lib/pages.py`, `.camarones/lib/diagrams.py` (`_page_blocks`, `_edit_page` generalised)
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: Task 2's page functions and `TARGET`; `diagrams._edit_page`, `genblocks.states`.
- Produces:
  - `kit_only(text: str, kit_text: str) -> bool` — True when every non-blank line of `text` outside its frontmatter and
    its generated blocks is a heading (`#…`), a `>` line, a `:::` line, a list item that is only a link
    (`- [x](y)` with an optional `: …`), or a line of `kit_text`.
  - `place(body: str, text: str, key: Key) -> str` — `text` (a whole block, markers included) in `body`: it replaces
    the block with the same key, else goes at the end of its `TARGET` section (inside its `:::details` when the target
    has one: the existing one, or a new one), else in a new section placed before `:::details How this page is made`.
  - `write(log=lambda _: None) -> list[str]` — old layout: `diagrams.write_pages(log)` (2a, unchanged); new layout:
    `_write_new(log)`. Returns the pages written (`docs/…` paths).
  - `_write_new(log, exclude: frozenset[Path] = frozenset()) -> list[str]` — writes the home, every present repo's page
    and, with topics, the messaging page. `exclude`: pages whose blocks do not count as living elsewhere (Task 5).
  - `diagrams._edit_page(body, repo, managed: list[tuple[str, str]], wanted, draw)` (was a dict heading → kind) and
    `diagrams._page_blocks(text, kinds=KINDS)`; `diagrams.write_pages` passes `list(dict.items())`, behaviour unchanged.

Rules for each target page in `_write_new` (in this order):
1. A block whose key already lives in another docs page (2a's `homes` rule, all kinds, pages in `exclude` ignored) goes
   in `skip`.
2. No file: write the fresh page (if the page function returns one).
3. `x-owner: human`: never written. No `x-generated` and no generated block: "not written by the kit: left as it is".
4. `x-generated: true` and `kit_only(text, fresh)`: the fresh page, then every block of the old page that is confirmed,
   edited by hand or `unknown` goes back with `place` verbatim (an unconfirmed `current`/`stale`/`gone` block is
   replaced by the fresh one or dropped); `x-confirmed` from the old frontmatter is kept (as `radar.run` does).
5. Otherwise (the page has text a person or an agent wrote): only its blocks, through `diagrams._edit_page` with the
   page's `(heading, kind)` pairs from `TARGET`; the TL;DR is left alone; log
   `"· {rel}: has text a person or an agent wrote, only its blocks were brought up to date"`.
6. The home (and its system-wide blocks) while some repo is not on this machine: left as it is, logged like 2a's system
   map. A file is written only when its text changed.

- [ ] **Step 1: Write the failing tests** (same file):

```python
def test_write_creates_the_home_and_a_page_per_repo(pg):
    written = pg.mod.write()
    assert set(written) == {"docs/index.md", "docs/repos/api/index.md", "docs/repos/web/index.md", "docs/repos/worker/index.md"}
    assert pg.mod.write() == []                                                    # idempotent

def test_write_in_the_old_layout_is_2a(pg):
    write_doc(pg, "architecture/first-look.md", "# old\n")
    pg.mod.write()
    assert not (pg.kit.root / "docs" / "index.md").exists()
    assert (pg.kit.root / "docs" / "architecture" / "system-map.md").exists()

def test_a_confirmed_block_survives_a_rewrite(pg):
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    pg.mod.write()
    page = pg.kit.root / "docs" / "repos" / "api" / "index.md"
    confirmed = confirm(pg, page, "OrderStatus")                                   # helper: sets confirmed= and by=
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER.replace("SHIPPED", "SHIPPED, LOST"))
    pg.mod.write()
    assert page.read_text(encoding="utf-8").count(confirmed) == 1

def test_prose_in_a_kit_page_is_kept(pg):
    pg.mod.write()
    page = pg.kit.root / "docs" / "repos" / "api" / "index.md"
    page.write_text(page.read_text(encoding="utf-8").replace("## What it needs to run",
                    "The team runs it behind nginx.\n\n## What it needs to run"), encoding="utf-8")
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    pg.mod.write()
    text = page.read_text(encoding="utf-8")
    assert "behind nginx" in text and "generated:states repo=api id=OrderStatus" in text

def test_a_block_moved_elsewhere_is_not_written_twice(pg):
    pg.put("api", "src/main/java/demo/OrderStatus.java", ORDER)
    write_doc(pg, "flows/checkout.md", "---\ntitle: Checkout\n---\n# Checkout\n\n"
              + pg.gb.block("states", "api", "x", id="OrderStatus") + "\n")
    pg.mod.write()
    assert "OrderStatus" not in (pg.kit.root / "docs" / "repos" / "api" / "index.md").read_text(encoding="utf-8")

def test_a_partial_clone_leaves_the_home_alone(pg):
    pg.mod.write()
    home = (pg.kit.root / "docs" / "index.md").read_text(encoding="utf-8")
    pg.rmtree(pg.kit.ws / "worker")
    pg.put("api", "src/main/resources/openapi.yaml", OPENAPI)
    pg.mod.write()
    assert (pg.kit.root / "docs" / "index.md").read_text(encoding="utf-8") == home
    assert "generated:endpoints-map" in (pg.kit.root / "docs" / "repos" / "api" / "index.md").read_text(encoding="utf-8")

def test_a_human_page_is_never_written(pg):
    write_doc(pg, "index.md", "---\ntitle: Home\nx-owner: human\n---\n# Home\n")
    pg.mod.write()
    assert (pg.kit.root / "docs" / "index.md").read_text(encoding="utf-8").endswith("# Home\n")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run python -m pytest tests/test_pages.py -q -k "write or confirmed or prose or moved or partial or human"`
Expected: FAIL with `AttributeError: … 'write'`

- [ ] **Step 3: Implement `kit_only`, `place`, `write`, `_write_new`, and generalise `diagrams._edit_page`/`_page_blocks`**

- [ ] **Step 4: Run the page and 2a tests**

Run: `uv run python -m pytest tests/test_pages.py tests/test_diagram_blocks.py tests/test_genblocks.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/pages.py .camarones/lib/diagrams.py tests/test_pages.py
git commit -m "feat(pages): write the home and the repo pages, keeping confirmed blocks and prose"
```

### Task 4: Commands, install, first look and the wizard use the layout

**Files:**
- Modify: `.camarones/camarones.py` (help text, `pages` parser with `--adopt`/`--json`, `diagrams` alias, `cmd_pages`,
  `cmd_blocks`, `schemas`, `arch-draft`), `.camarones/lib/catalog.py`, `.camarones/lib/quickarch.py`,
  `.camarones/lib/wizard.py` (`scan_repos`, `arch_flow`, `arch_prompt`), `.camarones/lib/serve.py` (`first_look`,
  `api_schemas`, `schemas_write`)
- Test: `tests/test_pages.py`, and adapt `tests/test_genblocks.py`, `tests/test_diagram_blocks.py`,
  `tests/test_portal_smoke.py`, `tests/test_wizard.py` (any other test the full run shows relying on a fresh workspace
  producing old pages)
- Modify: `tests/fixtures/builder.py` — `seed_old_layout(root: Path) -> None` writes a minimal
  `docs/architecture/first-look.md`, so an adapted test keeps exercising the old layout

**Interfaces:**
- Consumes: `pages.layout`, `pages.write` (Task 3); `pages.adopt` is wired here but implemented in Task 5 (until then
  `--adopt` may raise `NotImplementedError`).
- Produces:
  - `quickarch.first_look_page(model: dict) -> str` (the page text `save` writes today, moved out unchanged) and
    `quickarch.save(model, overwrite=False, page=True)`: `page=False` writes the C4 files only.
  - `cmd_pages(a) -> int`: `{"layout", "written", "updated", "edited", "human"}` with `--json`; `--adopt` prints/returns
    `pages.adopt()`. `diagrams` parses to the same handler (no `--adopt`, no `--force`).
  - Catalog: `"pages": _e("app", "analyze", "Páginas desde el código, sin IA: el inicio y una por repo", "Pages from the
    code, no AI: the home and one per repo")`; `"diagrams"` becomes `CLI` (an alias; the Taller shows `pages`).
  - New layout: `scan_repos` = radar, inventory, `pages.write` (caught: `"⚠ pages skipped: {e}"`), `genblocks.refresh`;
    `first_look` = `quickarch.save(draft, page=False)`, radar, inventory, `pages.write` (caught), `docs.llms`, C4 build,
    last log line `"✔ first look written: index.md, a page per repo, overview/tooling.md and the C4 draft"`;
    `cmd_blocks` creates no reference page; `schemas` and `schemas_write` call `pages.write` instead of
    `schemas.write_pages`; `arch-draft --save` passes `page=False`. Old layout: all of these exactly as today.
  - `api_schemas` page link: `data/<repo>.md` if it exists, else `repos/<repo>/index.md` if it exists, else None.
  - `arch_flow` treats the draft as saved when `docs/architecture/model.c4` exists (not `first-look.md`); `arch_prompt`
    says "Update `first-look.md` to match" only when that file exists.

- [ ] **Step 1: Write the failing tests** (in `tests/test_pages.py`, `cli(pg, *args)` runs `camarones.py` in a
  subprocess like `test_the_diagrams_command_has_no_force_flag`):

```python
def test_install_writes_the_new_pages(pg):
    pg.kit.wizard.scan_repos(log=lambda _: None)
    docs_dir = pg.kit.root / "docs"
    assert (docs_dir / "index.md").exists() and (docs_dir / "repos" / "api" / "index.md").exists()
    assert not (docs_dir / "repos" / "api" / "reference.md").exists()
    assert not (docs_dir / "architecture" / "system-map.md").exists()

def test_install_in_the_old_layout_is_unchanged(pg):
    seed_old_layout(pg.kit.root)
    pg.kit.wizard.scan_repos(log=lambda _: None)
    assert (pg.kit.root / "docs" / "repos" / "api" / "reference.md").exists()

def test_install_survives_a_pages_failure(pg, monkeypatch):
    monkeypatch.setattr(pg.mod, "write", lambda log=None: (_ for _ in ()).throw(RuntimeError("no pages today")))
    logs = []
    pg.kit.wizard.scan_repos(log=logs.append)
    assert (pg.kit.root / "docs" / "overview" / "tooling.md").exists()
    assert any("pages skipped" in l and "no pages today" in l for l in logs)

def test_first_look_writes_the_home_not_first_look_md(pg, monkeypatch):
    serve = importlib.import_module("lib.serve")
    monkeypatch.setattr(serve.env, "which", lambda _n: None)
    logs = []
    assert serve.first_look(log=logs.append)
    docs_dir = pg.kit.root / "docs"
    assert (docs_dir / "index.md").exists() and (docs_dir / "architecture" / "model.c4").exists()
    assert not (docs_dir / "architecture" / "first-look.md").exists() and "index.md" in logs[-1]

def test_old_commands_do_not_write_old_pages_in_the_new_layout(pg):
    pg.put("api", "src/main/resources/db/migration/V1__init.sql", SQL)
    for args in (("blocks",), ("schemas",), ("arch-draft", "--save")):
        assert cli(pg, *args).returncode == 0
    importlib.import_module("lib.serve").schemas_write()
    assert pg.mod.old_pages() == [] and pg.mod.layout() == "new"

def test_pages_and_its_alias(pg):
    out = json.loads(cli(pg, "pages", "--json").stdout)
    assert out["layout"] == "new" and "docs/index.md" in out["written"]
    assert cli(pg, "diagrams", "--json").returncode == 0 and cli(pg, "diagrams", "--adopt").returncode != 0

def test_the_data_view_links_the_repo_page(pg):
    pg.put("api", "src/main/resources/db/migration/V1__init.sql", SQL)
    pg.mod.write()
    rows = importlib.import_module("lib.serve").api_schemas()["repos"]
    assert next(r for r in rows if r["repo"] == "api")["page"] == "repos/api/index.md"

```

In `tests/test_wizard.py`, the `first_look` fixture writes `docs/architecture/model.c4` instead of `first-look.md` (its
tests keep their assertions), plus:

```python
def test_a_first_look_page_without_a_model_drafts_again(kit, fake_wizard, monkeypatch):
    page = kit.docs.DOCS / "architecture" / "first-look.md"
    page.parent.mkdir(parents=True)
    page.write_text("# First look\n", encoding="utf-8")
    drafts = []
    monkeypatch.setattr(kit.wizard.quickarch, "draft", lambda log=None, **kw: drafts.append(1))   # None → again/skip
    assert fake_wizard(["skip"]).arch_flow() == "skipped" and drafts == [1]
```

Also: `uv run python .camarones/camarones.py catalog --check` must pass (put it in `tests/test_catalog.py` if the
existing test does not already cover new parser entries).

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run python -m pytest tests/test_pages.py tests/test_wizard.py -q -k "install or first_look or old_commands or alias or data_view or c4_step"`
Expected: FAIL (old pages written; `pages` is not a command)

- [ ] **Step 3: Implement the callers, `first_look_page`/`save(page=)`, the catalog entries and the help text**

Help text lines (`camarones.py`):
`pages [--adopt] [--json]  the docs from the code, no AI: docs/index.md (what the project is, a card per repo, the
context map) and docs/repos/<repo>/index.md (what each repo exposes, stores and needs to run). Projects from before
4.52 keep their pages; --adopt moves them to this layout` and `diagrams [--json]  alias of pages`.

- [ ] **Step 4: Adapt the old tests and run the whole suite**

Old-layout tests (`scan_repos` writes reference pages, the first look draws `system-map.md`, `blocks --json` creates
`reference.md`, the portal's first look writes `first-look.md`) call `seed_old_layout(kit.root)` first; the portal
smoke test asserts the new pages instead.

Run: `uv run python -m pytest -n auto -q` (or without `-n` if xdist is not installed on this branch)
Expected: PASS except the five known Windows failures already on `main`

- [ ] **Step 5: Commit**

```bash
git add .camarones/camarones.py .camarones/lib/catalog.py .camarones/lib/quickarch.py .camarones/lib/wizard.py \
  .camarones/lib/serve.py tests/
git commit -m "feat(pages): camaron pages; a new project's install writes the home and the repo pages"
```

### Task 5: `camaron pages --adopt` moves an old project's blocks

**Files:**
- Modify: `.camarones/lib/pages.py`
- Test: `tests/test_pages_adopt.py`

**Interfaces:**
- Consumes: `old_pages`, `kit_only`, `place`, `_write_new(log, exclude=…)`, `TARGET` (Tasks 2–3);
  `genblocks.reference_page`, `diagrams._new_page`, `schemas.page`, `quickarch.first_look_page` for the text the kit
  would write today for each old page.
- Produces: `adopt(log=lambda _: None) -> dict` with `"moved"` (`"<kind> <repo>[ <id>] → docs/<page>"` per carried
  block), `"deleted"`, `"kept"` (`"docs/<page>: <reason>"`), `"relinked"`, `"links"`, `"translations"` (lists of
  `docs/…` paths; the last three filled in Task 6).

Algorithm:
1. Each old page: `x-owner: human` → kept ("owned by a person"); a block of a kind with no `TARGET` → kept ("has a block
   the new pages have no place for"); `not kit_only(text, kit_text_today)` → kept ("has text a person or an agent
   wrote"). A kept page is left exactly as it is, blocks included, so `_write_new` does not draw those blocks again.
   (`first-look.md` has no `x-generated`: it counts as the kit's when its title is `Architecture — first look`.)
2. `_write_new(log, exclude=<the removable pages>)` writes the new pages with every block the code has.
3. Every block of a removable page that is confirmed, edited by hand or `unknown` goes into its new page with `place`,
   verbatim; the others are already there fresh. Each one is listed in `moved`.
4. The removable pages are deleted. A second run finds nothing to move or delete and writes no file.

- [ ] **Step 1: Write the failing tests** — fixture `old_project(pg)`: code with an OpenAPI file, a status enum, a SQL
  migration and a publisher; then the 4.x writers: `genblocks.write_reference()`, `diagrams.write_pages()`,
  `schemas.write_pages()`, `quickarch.save(quickarch.draft(log=…))` (LikeC4 off). Small helpers in the test file:
  `confirm(fx, rel, id)` sets `confirmed=<sha> by=ana` on that block and returns the new block text;
  `hand_edit_table(fx, rel, kind)` appends a row inside that block and returns it; `add_paragraph(fx, rel, text)` puts a
  paragraph before the page's last `## ` heading; `make_human(fx, rel)` sets `x-owner: human`; `run_check(fx)` returns
  the issue strings of the project's quality check.

```python
def test_adopt_moves_every_block_and_deletes_the_emptied_pages(old_project):
    out = old_project.mod.adopt()
    docs_dir = old_project.kit.root / "docs"
    for rel in ("repos/api/reference.md", "repos/api/diagrams.md", "data/api.md", "architecture/system-map.md",
                "architecture/first-look.md"):
        assert not (docs_dir / rel).exists() and f"docs/{rel}" in out["deleted"]
    api = (docs_dir / "repos" / "api" / "index.md").read_text(encoding="utf-8")
    for kind in ("endpoints-map", "endpoints", "schema", "states", "topics", "env", "commands"):
        assert f"<!-- generated:{kind} repo=api" in api
    assert old_project.mod.layout() == "new"

def test_adopt_keeps_a_confirmed_and_an_edited_block_verbatim(old_project):
    confirmed = confirm(old_project, "repos/api/diagrams.md", "OrderStatus")
    edited = hand_edit_table(old_project, "repos/api/reference.md", "env")
    old_project.mod.adopt()
    api = (old_project.kit.root / "docs" / "repos" / "api" / "index.md").read_text(encoding="utf-8")
    assert api.count(confirmed) == 1 and api.count(edited) == 1

def test_adopt_leaves_a_page_with_prose_and_a_human_page(old_project):
    add_paragraph(old_project, "data/api.md", "Pets are never deleted, only archived.")
    make_human(old_project, "repos/web/reference.md")
    out = old_project.mod.adopt()
    docs_dir = old_project.kit.root / "docs"
    assert "archived" in (docs_dir / "data" / "api.md").read_text(encoding="utf-8")
    assert (docs_dir / "repos" / "web" / "reference.md").exists()
    assert any(k.startswith("docs/data/api.md") for k in out["kept"])
    assert "generated:schema repo=api" not in (docs_dir / "repos" / "api" / "index.md").read_text(encoding="utf-8")

def test_adopt_twice_changes_nothing(old_project):
    old_project.mod.adopt()
    before = snapshot(old_project.kit.root / "docs")                               # tests/fixtures/builder.snapshot
    out = old_project.mod.adopt()
    assert snapshot(old_project.kit.root / "docs") == before and out["moved"] == out["deleted"] == []

def test_adopt_on_a_new_project_is_a_no_op(pg):
    pg.mod.write()
    assert pg.mod.adopt()["deleted"] == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run python -m pytest tests/test_pages_adopt.py -q`
Expected: FAIL with `AttributeError: … 'adopt'` (or `NotImplementedError`)

- [ ] **Step 3: Implement `adopt` (steps 1–4 above)**

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run python -m pytest tests/test_pages_adopt.py tests/test_pages.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/pages.py tests/test_pages_adopt.py
git commit -m "feat(pages): --adopt moves an old project's generated blocks into the new pages"
```

### Task 6: `--adopt` fixes the links to the pages it removed

**Files:**
- Modify: `.camarones/lib/pages.py`
- Test: `tests/test_pages_adopt.py`

**Interfaces:**
- Consumes: `adopt` (Task 5).
- Produces: in `adopt`'s result, `"relinked"` (pages whose Markdown links were rewritten), `"links"` (pages that link to
  a removed page and were not rewritten: `x-owner: human` or `x-confirmed`), `"translations"` (existing
  `docs/i18n/<lang>/<removed page>` files, listed and never deleted). New target per removed page:
  `reference.md`, `diagrams.md`, `data/<repo>.md` → `repos/<repo>/index.md`; `system-map.md`, `first-look.md` →
  `index.md`; always as a path relative to the linking page, anchors dropped.

- [ ] **Step 1: Write the failing tests**:

```python
def test_adopt_relinks_and_check_has_no_broken_link(old_project):
    brief = write_doc(old_project, "repos/api/brief.md", "---\ntitle: api\nx-owner: ai\n---\n# api\n\n"
                      "> **TL;DR:** The API.\n\nSee [the reference](reference.md#http-endpoints).\n")
    confirmed = write_doc(old_project, "overview/system.md", "---\ntitle: System\nx-confirmed: 2026-10-01\n---\n"
                          "# System\n\n> **TL;DR:** x.\n\nSee [the map](../architecture/system-map.md).\n")
    out = old_project.mod.adopt()
    assert "[the reference](index.md)" in brief.read_text(encoding="utf-8")
    assert "docs/repos/api/brief.md" in out["relinked"] and "docs/overview/system.md" in out["links"]
    assert "../architecture/system-map.md" in confirmed.read_text(encoding="utf-8")       # confirmed: untouched
    broken = [i for i in run_check(old_project) if "repos/api/brief.md" in i and "link" in i.lower()]
    assert broken == []

def test_adopt_lists_the_translations_of_removed_pages(old_project):
    write_doc(old_project, "i18n/es/repos/api/reference.md", "---\nx-translation-of: repos/api/reference.md\n---\n# api\n")
    out = old_project.mod.adopt()
    assert "docs/i18n/es/repos/api/reference.md" in out["translations"]
    assert (old_project.kit.root / "docs" / "i18n" / "es" / "repos" / "api" / "reference.md").exists()
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run python -m pytest tests/test_pages_adopt.py -q -k "relinks or translations"`
Expected: FAIL (`KeyError: 'relinked'` or the link still points to `reference.md`)

- [ ] **Step 3: Implement the relinking and the lists; print them in `cmd_pages --adopt` (one line per list entry,
  English, no joke)**

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run python -m pytest tests/test_pages_adopt.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/lib/pages.py .camarones/camarones.py tests/test_pages_adopt.py
git commit -m "feat(pages): --adopt points links at the new pages and lists what it could not touch"
```

### Task 7: The tooling and libraries pages talk about the project

**Files:**
- Modify: `.camarones/lib/radar.py` (`render`), `.camarones/lib/inventory.py` (`render`)
- Test: `tests/test_radar.py`, `tests/test_inventory.py`

**Interfaces:**
- Consumes: `pages.count` (Task 1).
- Produces: new TL;DRs and a final `:::details How this page is made` block (exact copy):
  - Tooling: `> **TL;DR:** {count(n, "repo")}: {name} ({stack}), …; the team already uses {count(k, "tool")}` + (`: {first
    five distinct tool labels, ", "}` + (`…` when more)) + `.` (zero tools → `the team uses no tool the scan knows`).
    Details: `Read from each repo's files with no AI. Fix a wrong stack with \`camaron stack <repo> "<stack>"\`, then
    \`camaron radar\` to refresh this page.`
  - Libraries: `> **TL;DR:** {count(N, "direct dependency", "direct dependencies")} across {count(n, "repo")}` +
    (`; {count(d, "library", "libraries")} with different versions in different repos` when d) + (`; {count(v, "library",
    "libraries")} with known vulnerabilities` when the scan has vulnerabilities) + `.` Details: `Read from each repo's
    manifests and lockfiles with no AI. \`camaron inventory --cves\` adds the known vulnerabilities (OSV); the portal's
    Libraries tab filters this list.`

- [ ] **Step 1: Write the failing tests**:

```python
def test_the_tooling_tldr_is_about_the_project(kit):              # tests/test_radar.py
    text = kit.radar.render(kit.radar.scan())
    assert "> **TL;DR:** 3 repos: api (" in text and "Discovery reads this page" not in text
    assert text.rstrip().endswith(":::") and "camaron stack <repo>" in text.split(":::details How this page is made")[1]

def test_the_libraries_tldr_counts_and_drift(kit):                # tests/test_inventory.py
    text = kit.inventory.render(kit.inventory.scan())
    assert "> **TL;DR:** 1 direct dependency across 1 repo." in text      # the fixture: web's react only
    assert "camaron inventory --cves" in text.split(":::details How this page is made")[1]
```

(Adjust the expected counts to what the fixture's manifests really declare; update any existing assertion on the old
TL;DR text.)

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run python -m pytest tests/test_radar.py tests/test_inventory.py -q`
Expected: FAIL on the TL;DR assertions

- [ ] **Step 3: Implement the two `render` changes**

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run python -m pytest tests/test_radar.py tests/test_inventory.py tests/test_ask_retrieval.py -q`
Expected: PASS

- [ ] **Step 5: Commit** (body: a confirmed `tooling.md`/`libraries.md` reads as `needs-reconfirm` after its next
  refresh, because its TL;DR changed)

```bash
git add .camarones/lib/radar.py .camarones/lib/inventory.py tests/test_radar.py tests/test_inventory.py
git commit -m "feat(pages): tooling and libraries TL;DRs about the project; how they are made goes last"
```

### Task 8: The portal shows the home and links the repo page

**Files:**
- Modify: `.camarones/portal/app/public/legacy/app.js` (`showStart`), `.camarones/portal/app/public/legacy/doc.js`
  (`diagramTargets`), `.camarones/portal/app/public/legacy/core.js` (es/en strings), `.camarones/portal/app/public/legacy/app.css`
  (only if the section needs spacing), rebuilt `.camarones/portal/app-build/`
- Test: `tests/test_portal_app.py`

**Interfaces:**
- Consumes: `index.md` as written by Task 3; `api('doc', {path, lang})` and `mountDoc(container, raw, path, anchor,
  blocks)` from the legacy scripts.
- Produces: in `showStart`, when `BY_PATH['index.md']` exists, a `<section class="start-sec start-home">` with the
  heading `t('home.system')` (en `The system`, es `El sistema`) right after the hero and before the KPIs; its body is
  `index.md` (the current language's version, else English) without its first `# …` line, mounted with `mountDoc` and
  the doc's `blocks`. `diagramTargets` prefers `repos/<repo>/index.md`, then `brief.md`, then `reference.md`.

- [ ] **Step 1: Write the failing tests** (string checks, the way `tests/test_portal_app.py` already reads the legacy
  sources):

```python
def test_the_home_shows_the_project_home_before_the_kpis():
    app = LEGACY.joinpath("app.js").read_text(encoding="utf-8")
    start = app[app.index("async function showStart"):app.index("function showZone")]
    assert "start-home" in start and "'index.md'" in start and "mountDoc(" in start
    assert start.index("start-home") < start.index("home-kpis")

def test_diagram_nodes_open_the_repo_page_first():
    doc = LEGACY.joinpath("doc.js").read_text(encoding="utf-8")
    targets = doc[doc.index("function diagramTargets"):doc.index("function linkDiagrams")]
    assert targets.index("/index.md") < targets.index("brief.md") < targets.index("reference.md")

def test_the_home_section_title_exists_in_both_languages():
    core = LEGACY.joinpath("core.js").read_text(encoding="utf-8")
    assert core.count("'home.system'") == 2
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run python -m pytest tests/test_portal_app.py -q -k "project_home or repo_page_first or home_section"`
Expected: FAIL

- [ ] **Step 3: Implement the three changes, then rebuild**

Run (from `.camarones/portal/app`): `npm run build` and `npm test`
Expected: build writes `../app-build/`, vitest PASS

- [ ] **Step 4: Run the portal tests**

Run: `uv run python -m pytest tests/test_portal_app.py tests/test_portal_smoke.py -q`
Expected: PASS (including the check that `app-build/` matches its source)

- [ ] **Step 5: Commit**

```bash
git add .camarones/portal/app/public/legacy .camarones/portal/app-build tests/test_portal_app.py
git commit -m "feat(portal): the Home shows the project home; diagram nodes open the repo page"
```

### Task 9: Agents read and write the new pages

**Files:**
- Modify: `.camarones/PLAYBOOK.md` (`quick-overview`, `repo-brief`, `arch-system`, `data`, `diagrams`),
  `.camarones/CONVENTIONS.md` (§5 generated diagrams line, §7 generated blocks), `.camarones/templates/skills/cam-docs-diagrams/SKILL.md`
  (step 1 and step 5), `.camarones/templates/AGENTS.md` (the "work in a repo" row), `.camarones/templates/skeletons/repo-brief.md`
- Test: `tests/test_agent_guidance.py`

**Interfaces:**
- Consumes: page names from Tasks 2–5. Produces: text only. What each text must say:
  - New pages first, old ones as the old-layout alternative: "`docs/repos/<repo>/index.md` (or `reference.md` and
    `diagrams.md` in a project from before 4.52)"; the same for `docs/index.md` vs `architecture/system-map.md`.
  - `quick-overview` and `arch-system`: when `docs/index.md` is the generated home, keep its blocks and its `:::cards`,
    write the overview around them and remove `x-generated: true` from its frontmatter (the page is then the agent's;
    `camaron blocks` still refreshes the blocks).
  - `arch-system`: the C4 files started as a static-scan draft when `model.c4` begins with `// Camarones first-look
    draft` (or `first-look.md` exists).
  - `data`: a `docs/data/` page the unit writes never carries `x-generated: true`; it may move the `schema` block there,
    markers included.
  - `diagrams`: start with `CLI pages` (`CLI diagrams` is its alias).
  - The skill and CONVENTIONS list the block kinds including `schema`, the four diagram kinds and `repos`.

- [ ] **Step 1: Write the failing test**:

```python
def test_agents_are_told_about_the_new_pages():
    for f in (KIT / "PLAYBOOK.md", KIT / "CONVENTIONS.md", SKILLS / "cam-docs-diagrams" / "SKILL.md",
              KIT / "templates" / "AGENTS.md", KIT / "templates" / "skeletons" / "repo-brief.md"):
        text = f.read_text(encoding="utf-8")
        assert "repos/<repo>/index.md" in text or "(index.md)" in text, f
    playbook = (KIT / "PLAYBOOK.md").read_text(encoding="utf-8")
    assert "remove `x-generated: true`" in playbook and "CLI pages" in playbook
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run python -m pytest tests/test_agent_guidance.py -q`
Expected: FAIL

- [ ] **Step 3: Edit the five texts**

- [ ] **Step 4: Run the guidance and budget tests**

Run: `uv run python -m pytest tests/test_agent_guidance.py tests/test_context_budget.py tests/test_structure.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .camarones/PLAYBOOK.md .camarones/CONVENTIONS.md .camarones/templates tests/test_agent_guidance.py
git commit -m "docs(agents): the project home and the repo pages, with the old pages as the older layout"
```

### Task 10: User docs, version and the sandbox

**Files:**
- Modify: `README.md` (Spanish: the no-AI base, `camaron pages`, `--adopt`, the badge), `.camarones/lib/tutorial.py`
  (es and en: the "Facts from the code" and "Diagrams from the code" paragraphs, lines ~328–332 and ~682–686),
  `.camarones/TUTORIAL.md` (regenerated), `.camarones/templates/docs/guides/tutorial.md` and
  `.camarones/templates/docs/i18n/es/guides/tutorial.md` (same paragraphs), `.camarones/lib/common.py`
  (`VERSIONS["kit"] = "4.52.0"`)
- Test: `tests/test_wizard.py` (tutorial ↔ `TUTORIAL.md`), the whole suite, the sandbox

- [ ] **Step 1: Edit the docs** — what to say: a new project's install writes `docs/index.md` (what the project is, a
  card per repo, the context map) and `docs/repos/<repo>/index.md` (what it exposes, stores and needs to run; tables
  folded); `camaron pages` brings them up to date (`camaron diagrams` is its alias); a project from before 4.52 keeps
  its pages until `camaron pages --adopt`, which moves the blocks with their confirmations, deletes only the kit pages
  it emptied, keeps pages with text a person wrote and lists them.

- [ ] **Step 2: Regenerate `TUTORIAL.md`**

Run (from `.camarones/`): `uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"`

- [ ] **Step 3: Run the whole suite**

Run: `uv run python -m pytest -n auto -q` (or without `-n`)
Expected: PASS except the five known Windows failures on `main`

- [ ] **Step 4: Sandbox, new layout and adopt**

Run: `uv run scripts/sandbox.py --dir C:/Users/aneri/sbx reset`, then `… cli pages --json`, `… cli check`
Expected: `docs/index.md`, `docs/repos/spring-petclinic-rest/index.md` and `docs/repos/spring-petclinic-angular/index.md`
(the PetClinic repos), `overview/tooling.md`, `overview/libraries.md`; `check` shows no Mermaid error and no error on
these pages. Then open the portal (`… open`, or the app) and look at Home: the cards and the context map under the Ask
box. For adopt: `reset`, run the 4.51 writers through `… cli blocks` and `… cli diagrams` with a seeded
`first-look.md`, then `… cli pages --adopt` and `… cli check`.

- [ ] **Step 5: Commit**

```bash
git add README.md .camarones/lib/tutorial.py .camarones/TUTORIAL.md .camarones/templates/docs .camarones/lib/common.py
git commit -m "docs: the project home and the repo pages; camaron pages --adopt; kit 4.52.0"
```

(Body: the shipped tutorial templates are copied once, so existing projects keep their copy.)
