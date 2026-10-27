# The guide and the tour — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Camarón explains itself inside the desktop app: four Markdown guides (es + en) read in Machine › Guide with
buttons to what they describe, a guided tour over the real interface, and a README that links to them.

**Architecture:** The guides are kit templates (`templates/docs/guides/*.md`, `i18n/es/guides/*.md`); `lib/guide.py`
serves the installed kit's copy at `GET /api/app/guide`; the renderer parses a Markdown subset into blocks
(`guide.js`) and renders them with React (`Guide.jsx`); HTML-comment markers become buttons. The tour is data plus
pure helpers (`tour.js`) and one overlay (`Tour.jsx`) mounted in `App.jsx`, pointing at `data-tour` attributes.

**Tech Stack:** Python 3.10 stdlib (server), React 19 + Vite 8 + Vitest 5 (renderer, `environment: 'node'`, tests
render with `renderToStaticMarkup`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-27-in-app-guide-design.md`

## Global Constraints

- No new npm or Python dependency; no `innerHTML`/`dangerouslySetInnerHTML` for guide text.
- Every user-facing string in `es` and `en` (`desktop/renderer/src/i18n.js`); intern-shrimp voice, at most one joke per
  screen, none in errors, prompts or tour steps that ask for a decision.
- macOS, Windows and Linux: `pathlib`, `encoding="utf-8"`, LF.
- Guide headings carry no emoji; anchors are the portal's slug (`lib/docs.py slugify`: lower case, keep letters,
  digits, space, `_`, `-`; spaces → `-`).
- Markers: one per line, alone: `<!-- go:<section> -->`, `<!-- cmd:<command> -->`, `<!-- portal:<#/address> -->`,
  `<!-- tour:<id> -->`.
- Guide order: `using, app, portal, internals, tutorial`.
- `VERSIONS["kit"]` → `4.70.0`; the README badge follows.
- Every statement in the guides matches the code of this commit (checklist: the inventories in the session scratchpad
  `inv-app-a.md`, `inv-app-b.md`, `inv-portal.md`, re-verified against the source when in doubt).
- `localStorage` reads and writes wrapped in try/catch; the page works without it.

## Review Focus

- Two headings with the same text in one guide → the second gets `-1` like the portal, and links/index reach each one.
- A search query with regex characters (`c++ (`, `*`) → no exception, plain substring match.
- A tour target that never appears (board off, no agent, Kit dev outside a checkout) → the step shows centred with the
  "not on screen" note; the tour goes on.
- A target near the window's edge or a window smaller than the bubble → the bubble stays inside the window.
- A marker whose target this window lacks (catalog not loaded yet, Kit dev, unknown command) → no button, no crash.

---

### Task 1: Server — `lib/guide.py` and `GET /api/app/guide`

**Files:**
- Create: `.camarones/lib/guide.py`
- Modify: `.camarones/lib/serve.py` (`api_app_get`, next to `machine`)
- Test: `tests/test_guide.py`

**Interfaces:**
- Produces: `guide.ORDER = ("using", "app", "portal", "internals", "tutorial")`;
  `guide.guides(lang: str, base: Path | None = None) -> list[dict]` — each `{"name", "title", "description",
  "markdown"}` (front matter stripped from `markdown`), only names whose English file exists, Spanish twin when
  `lang == "es"` and it exists; `base` defaults to `env.TEMPLATES / "docs"`.
- Produces: `GET /api/app/guide?lang=es|en` → `{"lang": str, "guides": [...]}`; 403 without the app token. Missing
  `lang` → the machine's (`PREFS` `lang`, default `es`).

- [ ] **Step 1: Write the failing tests** in `tests/test_guide.py` (fixture `kit`; the server fixture as in
  `tests/test_machine.py`):
  - `test_guides_follow_the_order_and_fall_back_to_english(kit, tmp_path)`: write `guides/app.md` and `guides/using.md`
    (front matter `title`, `description`) and `i18n/es/guides/using.md` under `tmp_path`; `guides("es", tmp_path)` →
    names `["using", "app"]`, `using` from the Spanish file, `app` from the English one, `markdown` starts after the
    front matter; `guides("en", tmp_path)[0]["title"]` is the English title.
  - `test_guide_endpoint_needs_the_app_token(kit, app)`: `call(f"{app}/api/app/guide?lang=en", token=None)` → 403;
    with the token → 200 and `body["lang"] == "en"` and `body["guides"]` a list.
- [ ] **Step 2: Run** `uv run pytest tests/test_guide.py -q` → FAIL (`lib.guide` missing).
- [ ] **Step 3: Implement** `lib/guide.py` (use `docs.split_fm`) and the `name == "guide"` branch in
  `serve.api_app_get` (`lang` from `q` or `load_json(PREFS, {}).get("lang", "es")`).
- [ ] **Step 4: Run** `uv run pytest tests/test_guide.py -q` → PASS.
- [ ] **Step 5: Commit** `feat(guide): serve the kit's guides to the desktop app`.

### Task 2: Renderer — `guide.js`, the parser, links, markers and search (pure)

**Files:**
- Create: `.camarones/desktop/renderer/src/guide.js`
- Test: `.camarones/desktop/renderer/src/guide.test.js`

**Interfaces:**
- Produces:
  - `slug(text: string) -> string` (portal rule, on the text with inline markup removed).
  - `parse(md: string) -> Block[]` with `Block` one of `{t:'h', level:2|3|4, text, id}` (ids unique per document:
    second `x` → `x-1`), `{t:'p', text}`, `{t:'ul'|'ol', items:[{text, items?}]}`, `{t:'table', head:[], rows:[[]]}`,
    `{t:'code', lang, text}`, `{t:'quote', kind:null|'note'|'tip'|'important'|'warning'|'caution', blocks}`,
    `{t:'actions', items:[{kind:'go'|'cmd'|'portal'|'tour', target}]}`; H1 dropped; other HTML comments dropped.
  - `inline(text: string) -> Tok[]`, `Tok` = `{t:'text'|'code'|'b'|'i'|'kbd', text}` or `{t:'a', text, href}`; HTML
    tags other than `<kbd>` stay as literal text.
  - `chapters(blocks) -> [{id, text, sections:[{id, text}]}]` (H2 and their H3).
  - `linkTarget(href, names: string[]) -> {kind:'guide', name, anchor} | {kind:'anchor', anchor} |
    {kind:'external', href} | null` (`app.md#x`, `./portal.md`, `#x`, `https://…`).
  - `guideAt(hash) -> {name, anchor}` and `guideHref(name, anchor?) -> '#/guide/<name>[/<anchor>]'`.
  - `searchGuides(guides:[{name, title, blocks}], q) -> [{name, guideTitle, chapter, id, title, snippet}]` — from two
    characters, every word (accents and case ignored) in a heading or a paragraph/list/table text; at most 20.
- [ ] **Step 1: Write the failing tests:**
  - `parse` of a sample with every block kind returns the expected blocks (exact objects), including a nested list,
    a `> [!TIP]` callout, a fenced block with `text` lang, two markers in a row → one `actions` block with two items.
  - duplicate headings `## Plan` twice → ids `plan`, `plan-1`; `## The \`camaron up\` command` → `the-camaron-up-command`;
    `## Datos y librerías` → `datos-y-librerías`.
  - `inline('Run \`camaron up\`, **then** *read* [x](app.md#plan) <kbd>Ctrl</kbd> <b>no</b>')` → the token list,
    with `<b>no</b>` as text.
  - `linkTarget` for the four href kinds and `mailto:` → `null`.
  - `searchGuides(..., 'c++ (')` does not throw and returns `[]`; `'tokén'` finds `token`; one-letter query → `[]`;
    results capped at 20.
- [ ] **Step 2: Run** `cd .camarones/desktop/renderer && npx vitest run src/guide.test.js` → FAIL.
- [ ] **Step 3: Implement** `guide.js` (a line-based block parser; inline by a regex tokenizer; search on
  `normalize('NFD')` text with `includes`, never `RegExp(query)`).
- [ ] **Step 4: Run** the test → PASS.
- [ ] **Step 5: Commit** `feat(desktop): parse the guides into blocks without a Markdown library`.

### Task 3: Renderer — the Guide place, nav, palette and the Machine card

**Files:**
- Create: `.camarones/desktop/renderer/src/sections/Guide.jsx`
- Modify: `src/nav.js` (`MACHINE = ['machine', 'guide', 'kitdev']`; `sections()` machine `['machine', 'guide']`
  without kitdev), `src/palette.js` (`GO.h = 'guide'`; `entries({..., guide = []})` adds a group `guide`;
  `pick` hides `guide` with no query, like `commands`), `src/App.jsx` (`SECTIONS.guide`, load the guide for the
  palette when it opens), `src/sections/Machine.jsx` (first card), `src/i18n.js`, `src/app.css`
- Test: `src/Guide.test.jsx`, `src/nav.test.js`, `src/palette.test.js`

**Interfaces:**
- Consumes: Task 2's `parse`, `inline`, `chapters`, `linkTarget`, `guideAt`, `guideHref`, `searchGuides`; Task 1's
  endpoint via `srv.get('app/guide', { lang: lang() })`; `catalog.js` `sectionFor`, `inPanel`; `docs.js` `portalUrl`.
- Produces:
  - `markerAction(item, { sections, commands, tours = [] }) -> {label, href} | {label, portal} | {label, tour} | null`
    (exported from `Guide.jsx`; `null` when the target is not available here).
  - `GuideView({ guides, at, sections, commands, tours, onPortal, onTour })` — the page for loaded guides (tabs,
    index, search box, content); `default Guide({ srv, app })` loads and renders it.
  - `guideEntries(guides) -> items` for the palette (`{id:'guide:<name>/<id>', label, sub: guideTitle, href}`).
  - i18n keys (es / en): `nav.guide` Guía / Guide; `gd.title`, `gd.search`, `gd.none`, `gd.failed`, `gd.copy`,
    `gd.copied`, `gd.go` "Ir a {s}" / "Go to {s}", `gd.cmd` "Abrir camaron {c}" / "Open camaron {c}", `gd.portal`
    "Abrir en el portal" / "Open in the portal", `gd.tour` "Enséñamelo" / "Show me", `gd.index` Capítulos / Chapters;
    `mc.guide` "Guía y recorrido" / "Guide and tour", `mc.guideBody`, `mc.guideOpen` "Abrir la guía" / "Open the
    guide"; `pal.guide` Guía / Guide.
- [ ] **Step 1: Write the failing tests:**
  - `nav.test.js`: `sections({kitdev:false}).machine` is `['machine','guide']`; `sectionOf('#/guide/app/plan', {})` is
    `guide`.
  - `palette.test.js`: `chord` with `g` then `h` goes to `guide`; `pick(entries({..., guide:[item]}), '')` has no
    `guide` group and `pick(..., 'plan')` has it.
  - `Guide.test.jsx`: `GuideView` with two small guides renders the tabs, the chapter index, a heading with its id, a
    `go:plan` marker as a button "Ir a Plan", a `cmd:check` marker as "Abrir camaron check" (catalog item
    `{name:'check', zone:'check'}`), `go:kitdev` with sections lacking it → no button, a `tour:x` with `tours=[]` → no
    button; `markerAction` cases for `cmd:` with an unknown command → `null`; no `dangerouslySetInnerHTML` in the
    output path (assert `<kbd>` rendered as an element and `<b>` as text `&lt;b&gt;`).
  - `Machine` renders a first card with "Abrir la guía".
- [ ] **Step 2: Run** `npx vitest run` → the new tests FAIL.
- [ ] **Step 3: Implement.** `Guide` keeps the place read in `localStorage['dk.guide.at']` (try/catch); the address
  `#/guide/<name>/<anchor>` scrolls the heading into view (`document.getElementById`); a code block has **Copy**
  (`navigator.clipboard.writeText`, try/catch); portal markers call `app.openExternal(portalUrl(location.origin,
  target))`.
- [ ] **Step 4: Run** `npx vitest run` → PASS (whole renderer suite).
- [ ] **Step 5: Commit** `feat(desktop): Machine › Guide — the kit's guides with chapters, search and buttons`.

### Task 4: The four guides in English

**Files:**
- Create: `.camarones/templates/docs/guides/{using,app,portal,internals}.md`
- Test: `tests/test_guide.py` (content checks)

**Interfaces:**
- Consumes: the chapter lists of spec §3; the markers of §3.1.
- Produces: the English guides; their H2 sequence and marker sequence are what Task 5 mirrors.

- [ ] **Step 1: Write the failing content tests** in `tests/test_guide.py`:
  - `test_the_kit_ships_the_four_guides`: `guides("en")` names equal `ORDER` (tutorial included), each with a non-empty
    title and description.
  - `test_cmd_markers_name_catalog_commands`: every `<!-- cmd:X -->` in every shipped guide (both languages) is a
    command of `catalog.catalog()`.
  - `test_portal_markers_are_portal_routes`: every `<!-- portal:#/head... -->` head is in the route heads of
    `portal/app/src/zones.js` (`ROUTES` keys) plus `''`, `search`, `ask`, `new`.
  - `test_guide_links_point_at_headings`: every `[..](<guide>.md#a)` / `(#a)` in a guide points at a heading slug
    (`docs.slugify`) of that guide in the same language.
  - `test_projects_get_the_guides_without_overwriting`: `env.init_templates()` in a `kit` project creates
    `docs/guides/app.md` (and the Spanish twin); a `docs/guides/app.md` the team edited is left as it was.
- [ ] **Step 2: Run** `uv run pytest tests/test_guide.py -q` → FAIL.
- [ ] **Step 3: Write the guides** (front matter like `tutorial.md`: `type: guide`, `title`, `description`, `tags`,
  `x-owner: human`; a `> **TL;DR:**` line under the H1; chapters of spec §3; markers where a chapter describes a
  section, command, portal view or tour). Verify each claim against the inventories and the source.
- [ ] **Step 4: Run** `uv run pytest tests/test_guide.py -q` → PASS; `npx vitest run` (renderer) → PASS.
- [ ] **Step 5: Commit** `docs(guide): using, app, portal and internals guides`.

### Task 5: The Spanish twins

**Files:**
- Create: `.camarones/templates/docs/i18n/es/guides/{using,app,portal,internals}.md`
- Test: `tests/test_guide.py`

- [ ] **Step 1: Write the failing test** `test_spanish_twins_mirror_the_english_guides`: for each guide, the Spanish
  file exists, has `x-translation-of: guides/<name>.md` like the tutorial's twin, the same count of H2 and H3 and the
  same marker sequence as the English one.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Write the twins** (adapted, not literal; anchors in links are the Spanish slugs).
- [ ] **Step 4: Run** `uv run pytest tests/test_guide.py -q` → PASS.
- [ ] **Step 5: Commit** `docs(guide): Spanish guides`.

### Task 6: Tour engine — `tour.js` (pure)

**Files:**
- Create: `.camarones/desktop/renderer/src/tour.js`
- Test: `src/tour.test.js`

**Interfaces:**
- Produces:
  - `TOURS: { [id]: [{ section: string|null, target: string }] }` with ids `app, summary, board, plan, interviews,
    team, quality, libs, docs, machine`; `section: null` = stay where you are; texts are i18n keys
    `tour.<id>.<n>.t` / `tour.<id>.<n>.b` (n from 1).
  - `tourIds() -> string[]`.
  - `place(rect|null, bubble:{w,h}, view:{w,h}, gap = 12) -> {top, left, side:'below'|'above'|'right'|'left'|'center'}`
    — prefers below, then above, right, left; clamps inside the view with an 8 px margin; `null` rect → centre.
  - `holes(rect, view, pad = 6) -> [{top,left,width,height} × 4]` (the dim around the target).
  - `tourKey(key) -> 'next'|'back'|'close'|null` (`ArrowRight`/`Enter` next, `ArrowLeft` back, `Escape` close).
  - `seen(storage) -> boolean`, `markSeen(storage) -> void` over `dk.tour.offered`, never throwing.
- [ ] **Step 1: Write the failing tests:** every tour has 3+ steps and `app` 14+; every step's text keys exist in both
  languages of `i18n.js`; `place` for a target at the bottom-right of an 800×600 view puts the bubble above/left and
  inside the view; a 300×200 view with a 320×180 bubble still returns a left/top ≥ 8; `null` → `center`; `holes`
  sums to the view minus the padded target; `tourKey` table; `seen`/`markSeen` with a storage whose methods throw.
- [ ] **Step 2: Run** `npx vitest run src/tour.test.js` → FAIL.
- [ ] **Step 3: Implement** `tour.js`; add the step texts to `i18n.js` (es + en).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(desktop): the tours as data, with pure placement`.

### Task 7: Tour overlay, targets and the ways in

**Files:**
- Create: `.camarones/desktop/renderer/src/Tour.jsx`
- Modify: `src/App.jsx` (provider + layer; `data-tour` on the rail, nav links `nav-<s>`, `find`, `portal`, `menu`),
  `src/JobsPanel.jsx` (`jobs`), the sections (`data-tour` on the cards each tour names), `src/sections/Guide.jsx`
  (`tours` from `tourIds()`), `src/sections/Machine.jsx` (**Take the tour**), `src/palette.js` (action `tour`),
  `src/sections/Summary.jsx` (the one-time offer), `src/i18n.js`, `src/app.css`
- Test: `src/Tour.test.jsx`, `src/Guide.test.jsx`, `src/Summary.test.jsx`, `src/palette.test.js`

**Interfaces:**
- Consumes: Task 6's `TOURS`, `place`, `holes`, `tourKey`, `seen`, `markSeen`.
- Produces: `TourContext` and `useTour() -> { start(id), stop(), active }`; `TourBubble({ title, body, n, m, missing,
  onBack, onNext, onClose })` (static-renderable); i18n `tour.take` "Hacer el recorrido" / "Take the tour",
  `tour.next`, `tour.back`, `tour.done`, `tour.close`, `tour.of` "{n} de {m}" / "{n} of {m}", `tour.missing`
  "Esta parte no está en pantalla ahora" / "This part is not on screen right now", `tour.offer`, `tour.notNow`.
- [ ] **Step 1: Write the failing tests:** `TourBubble` renders title, body, "2 de 5", Back/Next, `role="dialog"` and
  `aria-modal`; the last step says "Hecho"; `missing` adds the note; every `<!-- tour:X -->` in the shipped guides is in
  `tourIds()` (read the files with `node:fs`); every `<!-- go:X -->` is a section of `nav.js`; every `target` in
  `TOURS` appears as `data-tour="<target>"` somewhere in `src/` (read the sources with `node:fs`); Summary renders the
  offer when `seen()` is false and not after `markSeen()`; the palette lists **Hacer el recorrido**.
- [ ] **Step 2: Run** `npx vitest run` → FAIL.
- [ ] **Step 3: Implement** `Tour.jsx` (on step: navigate when `section` differs from the current one; poll every
  100 ms up to 1500 ms for the target; `scrollIntoView({block:'center'})`; redraw on `resize`/`scroll`; keys through
  `tourKey`; focus the bubble; no transitions under `prefers-reduced-motion`), the `data-tour` attributes and the
  entry points.
- [ ] **Step 4: Run** `npx vitest run` → PASS.
- [ ] **Step 5: Commit** `feat(desktop): the guided tour over the app's real controls`.

### Task 8: Copy that promises what the code does not do

**Files:**
- Modify: `.camarones/desktop/renderer/src/i18n.js` (`un.confirmBackup`: the backup goes to the system temp folder),
  `.camarones/portal/app/src/i18n/portal.js` (read-only banner; `noDocsHelp`), the `up` log line in
  `.camarones/lib/serve.py` or `lib/env.py`
- Test: existing tests that pin these strings (grep), updated first

- [ ] **Step 1:** grep the four strings and the tests that pin them; update the tests to the corrected text → FAIL.
- [ ] **Step 2:** change the strings (es + en): the banner says the browser portal edits, confirms and reviews, and
  that machine work is in the desktop app; `noDocsHelp` points at the desktop app's Plan (or `camaron run`); the `up`
  line drops "rebuild · wikis".
- [ ] **Step 3: Run** the affected tests → PASS.
- [ ] **Step 4: Commit** `fix(copy): say what the browser portal and the uninstall backup really do`.

### Task 9: The command guide and the wizard tutorial

**Files:**
- Modify: `.camarones/templates/docs/guides/tutorial.md`, `.camarones/templates/docs/i18n/es/guides/tutorial.md`
  (section 5 → a summary with links to `portal.md` and `app.md`; outdated facts fixed), `.camarones/lib/tutorial.py`
  (pages 11–14 and 18: seven zones, Stories in three steps, browser-only vs app-only buttons, `g l`/`g k`/`g h`,
  Machine › Guide), `.camarones/TUTORIAL.md` (regenerated)
- Test: `tests/test_wizard.py` (TUTORIAL.md in sync), `tests/test_guide.py::test_guide_links_point_at_headings`

- [ ] **Step 1:** edit `lib/tutorial.py` and both `tutorial.md`.
- [ ] **Step 2:** regenerate: from `.camarones/`,
  `uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"`.
- [ ] **Step 3: Run** `uv run pytest tests/test_wizard.py tests/test_guide.py -q` → PASS.
- [ ] **Step 4: Commit** `docs(tutorial): point the wizard tutorial and the command guide at the new guides`.

### Task 10: README and version

**Files:**
- Modify: `README.md` (restructured as spec §7), `.camarones/lib/common.py` (`VERSIONS["kit"] = "4.70.0"`)
- Test: any test pinning the badge/version (grep `4.69.2`)

- [ ] **Step 1:** rewrite the README in Spanish following spec §7; every removed detail has a home in a guide (check
  section by section against the old README).
- [ ] **Step 2:** bump the version and the badge; update tests that pin `4.69.2`.
- [ ] **Step 3: Run** `uv run pytest -n auto -q` → PASS.
- [ ] **Step 4: Commit** `docs(readme): a front door that links to the guides (kit 4.70.0)`.

### Task 11: Builds and the whole suite

- [ ] **Step 1:** `cd .camarones/desktop/renderer && npm run build`; `cd .camarones/portal/app && npm run build`.
- [ ] **Step 2: Run** `uv run pytest -n auto`, `npm test` in both, `node --test "test/*.test.cjs"` in
  `.camarones/desktop` → all PASS; `git status --porcelain -- .camarones/portal/app-build .camarones/desktop/renderer-build`
  shows only the rebuilt files.
- [ ] **Step 3: Commit** `build: renderer and portal builds for the guide and the tour`.
