# The guide and the tour: Camarón explained inside the desktop app — design

Asked by the user on 2026-10-27: "I have lost context of the changes, at a high and a low level. Update the README and
the tutorial of the app and the portal in depth. More than a tutorial, it will be a doc." Then, choosing where: "an
interactive tutorial in the app and/or portal, inside the options (Machine)", and, choosing the approach: "A as a
technical doc — MCP, API, how it works — and the interface and use of the app, and how to use the app; also a guided
tour".

## 1. Intent

The kit grew by accretion: the README is 839 lines of paragraphs that each describe one release, the wizard tutorial
and the command guide repeat parts of it, and several of those parts are now wrong (the portal has seven zones, not
five; Stories has three steps, not four; the browser portal never shows the app-only buttons the README describes).
Someone who uses Camarón every day can no longer answer "what does this button run?", "where does this file come
from?" or "which token lets me do this?".

This piece gives Camarón **one current, deep explanation of itself**, readable where the work happens — the desktop
app — and a **guided tour** that points at the real interface:

- four guides (how to use it, the app, the portal, how it works inside) in English and Spanish, shipped with the kit;
- a **Guide** place in the app (Machine group), with chapters, search and buttons that take you to what is explained;
- a **tour** that dims the window and walks through the real controls, section by section;
- a README restructured as a front door that links to the guides.

**Done when:** from Machine › Guide a person can read, in their language, how every app section and portal view works,
what each button runs, how the pieces (CLI, server, app, portal, agents, MCP) fit and what the HTTP/CLI/MCP surfaces
are; jump from any chapter to the section, command form or portal view it describes; and take a tour of the app or of
one section. The README fits on a few screens and sends the detail to the guides. Every statement in the guides matches
the code of this commit.

**Anti-goals — a failure even if it works:** a guide that describes what the code does not do; a second copy of the
same text to keep in sync by hand (README, tutorial and guides each saying everything); a guide that is stale in the
app because it was copied once into the project; a tour that breaks when a card is hidden (no board, no agent); new
npm dependencies or `innerHTML` for the guide; a 3.x/4.x project that needs a manual step.

### 1.1 Decisions taken with the user (2026-10-27)

| Question | Decision |
|---|---|
| Where the deep doc lives | Inside the desktop app, reachable from Machine; the portal may show it too |
| README | Restructure it: a front door that links to the detail, without losing information |
| Approach | A: Markdown guides as the single source, rendered by the app; plus C: a guided tour |
| Scope of the guides | Technical (how it works, API, MCP), the interface of the app and the portal, and how to use it |

## 2. Approach: Markdown guides shipped with the kit, rendered by the app

The guides are ordinary kit guides — Markdown files in `.camarones/templates/docs/guides/` (English, canonical) and
`.camarones/templates/docs/i18n/es/guides/` (Spanish) — like `tutorial.md` and `self-hosted-runner.md` today. That
makes one text serve four readers:

| Reader | How it reaches them |
|---|---|
| The desktop app | `GET /api/app/guide` reads the **installed kit's** files, so the app always shows the current text |
| The portal | `init_templates` copies the guides into each project's `docs/guides/` (new projects at creation, existing ones on their next `setup`; never overwriting), so Docs, Ask and the MCP find them |
| GitHub | the README links to the files in `.camarones/templates/docs/` |
| Agents | the MCP `search_docs`/`read_doc` already treat kit guides as guides (ranked after the project's pages unless the question is about Camarón) |

Interactivity comes from **invisible markers**: HTML comments on their own line, which the portal, GitHub and `check`
ignore and the app turns into buttons.

Rejected: **content as Python data served as JSON** (like `lib/tutorial.py`) — writing a long technical guide inside
Python strings is painful, and the portal and GitHub could not read it without a generator. **A tour only** — brittle,
app-only and shallow; it stays, but on top of the guides, not instead of them. **Rendering with `marked` in the app**
— a new dependency and `innerHTML` for text we write ourselves; a small parser for the subset the guides use is enough.

## 3. The guides

Four new guides, plus the existing command guide. Headings carry no emoji (the anchors must be the same in the
portal, which slugs like `lib/docs.py`, and on GitHub). Front matter as `tutorial.md`: `type: guide`, `title`,
`description`, `tags`, `x-owner: human`. Each H2 is a chapter; H3 are its sections.

| File | Title | Chapters (H2) |
|---|---|---|
| `using.md` | Using Camarón | The idea in one minute · First run · Joining your team · A normal day · Reviewing and confirming · Sharing with the team · The board and stories · Health, libraries and vulnerabilities · Keeping the docs current · Costs and KPIs · Starting over and uninstalling · When something fails |
| `app.md` | The desktop app | The window · The start screen · The first-run wizard · Summary · Board · Plan · Interviews · Team · Quality · Libraries · Docs · Machine · All commands · Kit dev · Keyboard |
| `portal.md` | The portal | Three ways to open it · The frame · Home, search and Ask · Docs · Wikis · Board · Stories · Architecture · Plan · Quality · Review · What pages can do · Addresses |
| `internals.md` | How Camarón works | The pieces · Where things live · The project server · The CLI is the API · The HTTP API · The plan and the harness · Agents and routing · Trust in pages: review and freshness · The MCP servers · Plugins and trust · Pages written without AI · Versions and compatibility |
| `tutorial.md` (exists) | Tutorial | unchanged structure; its portal and app parts shrink to a summary that links to `portal.md` and `app.md` |

The source of truth for every statement is the code at this commit; the three code inventories gathered for this
design (app sections, portal views, endpoints, tokens) are the checklist.

### 3.1 Markers

One marker per line, alone on its line, written after the paragraph it belongs to. Consecutive markers form one row of
buttons.

| Marker | Button (es / en) | Does |
|---|---|---|
| `<!-- go:<section> -->` | Ir a {sección} / Go to {section} | `#/<section>` in this window |
| `<!-- cmd:<command> -->` | Abrir `camaron <cmd>` / Open `camaron <cmd>` | the command's card in its section (`#/<section>/<cmd>`, as the palette does), or its panel |
| `<!-- portal:<#/address> -->` | Abrir en el portal / Open in the portal | the portal at that address, in the browser (the main process adds the session's portal token) |
| `<!-- tour:<id> -->` | Enséñamelo / Show me | starts that tour |

A marker whose target this window does not have (Kit dev outside a kit checkout, a command whose section is missing)
renders no button.

## 4. The Guide in the app

**Where.** A new place, `guide`, in the rail's machine group: Machine · Guide · Kit dev. Address
`#/guide[/<guide>[/<anchor>]]`; `g h` jumps there; ⌘K lists it among the sections and lists every chapter (H2) of every
guide in a **Guide** group. Machine gets a first card, **Guide and tour**, with **Open the guide** and **Take the
tour**.

**Layout.** A tab per guide (Using · The app · The portal · How it works · Commands); a chapter index at the side (H2
with their H3 folded under the current one); the text; a search box over all the guides. The page remembers the last
place read (`localStorage`, wrapped in try/catch).

**Search.** Client-side over the parsed guides: from two characters, the headings and paragraphs that contain every
word (accents and case ignored, like the palette), at most 20 results as "Guide › Chapter › Section" with a snippet;
Enter or a click goes there.

**Rendering.** `guide.js` (pure) parses the subset the guides use into blocks, and `Guide.jsx` renders them as React
elements:

- front matter (title, description) and the H1 are taken out; H2/H3/H4 become headings with the portal's slug as id;
- paragraphs; bullet and numbered lists, one nested level; pipe tables; fenced code (with a **Copy** button);
  `> ` quotes, and `> [!NOTE|TIP|IMPORTANT|WARNING|CAUTION]` callouts;
- inline: `code`, `**bold**`, `*italic*`, `[text](href)`, `<kbd>…</kbd>`; any other HTML is shown as text;
- links: `<guide>.md#anchor` and `#anchor` move inside the Guide; `http(s)` opens the browser; anything else is text;
- markers become button rows (§3.1).

**Server.** `lib/guide.py`: `guides(lang)` returns `[{name, title, description, markdown}]` in a fixed order (using,
app, portal, internals, tutorial), each from the Spanish twin when `lang == "es"` and it exists, else English. `GET
/api/app/guide?lang=` returns `{lang, guides}`; it is an app-token endpoint like the rest of `/api/app/`.

## 5. The tour

**Engine.** `tour.js` (pure): the tours as data — `{id, steps: [{section, target, key}]}`, with the texts in
`i18n.js` as `tour.<id>.<n>.title` / `.body` — and the helpers: the next and previous step, where the bubble goes
(below, above, right or left of the target, inside the window), the four rectangles that dim around the target.
`Tour.jsx`: mounted once in `App.jsx`, exposed through a small context (`useTour().start(id)`).

**A step.** If the step's section is not the current one, the tour navigates there; it waits up to 1.5 s for the
target (`[data-tour="…"]`) to be on screen, scrolls it into the middle and draws: a dimmed window with a hole and a ring
round the target, and a bubble (`role="dialog"`, `aria-modal`, focus inside it) with the step's title and text, "n of
m", **Back**, **Next** (**Done** on the last) and **Close**. ← → move, Esc closes, Enter is Next. The window resizing or
scrolling redraws it. A target that is not there (no board yet, no agent, Kit dev) shows the bubble centred with "This
part is not on screen right now" and the step's text, so the tour never breaks. With *reduce motion* nothing animates.

**Tours.** `app` (the whole app, about 14 steps: the rail, the sections, Search or go to…, View portal, the ⋯ menu,
the jobs panel and one stop per section) and one per section (`summary`, `board`, `plan`, `interviews`, `team`,
`quality`, `libs`, `docs`, `machine`), three to six steps each. The targets are `data-tour` attributes added to
existing elements; nothing else in the sections changes.

**Where it starts.** A guide chapter's **Show me** (`<!-- tour:plan -->`); Machine's **Take the tour**; ⌘K (**Take
the tour**); and once, in the Summary, a dismissible offer — "New here? I'll show you the app in a minute." with **Take
the tour** and **Not now** — that stays away after either button (`localStorage`).

## 6. The portal

No new portal UI. The guides reach every project as kit guides (§2), so they appear under Docs › Guides, in Ask and
for agents; the markers are invisible there. Three portal strings are corrected because they promise what the browser
portal cannot do (the code inventory found them): the read-only banner (it says `camaron up` lets you "generate
wikis"), the `up` log line ("live: edit · confirm · rebuild · wikis") and `noDocsHelp` ("run the next unit from the
Pipeline"). The app's uninstall dialog also says the backup is kept "next to the workspace", while `lib/uninstall.py`
writes it to the system temp folder: corrected too.

## 7. README and tutorial

**README** (Spanish), restructured; nothing is dropped without a home in a guide:

1. Hero, badges, one paragraph: what it is and for whom.
2. How the pieces fit: a diagram (repos → kit: CLI/wizard, desktop app, server → agents → `cam-docs/` → portal, MCP).
3. Start: requirements, install (global and classic), open the app or the wizard, team join.
4. The flow in five steps, with the app section and the command for each.
5. The app: a table section → what you do there; link to `app.md` and "Machine › Guide".
6. The portal: a table zone → views, the three modes and tokens in one table; link to `portal.md`.
7. Commands by task: a compact map (the catalog's zones).
8. Trust and quality: draft/confirmed/needs-reconfirm, freshness, `check`.
9. Inside: a summary of the harness, the MCP and the HTTP API; link to `internals.md`.
10. Team work, CI, exports and the board — short, each with its link.
11. Tools considered and rejected (kept, condensed); Development (unchanged rules).

**Wizard tutorial** (`lib/tutorial.py` → `TUTORIAL.md`): the outdated facts fixed (seven portal zones, Stories in three
steps, the browser portal's buttons, the app's sections and shortcuts) and the app pages point at Machine › Guide.
**Command guide** (`templates/docs/guides/tutorial.md` and its Spanish twin): its sections 5 (portal, app, board,
stories) become a summary with links to the new guides.

## 8. Testing

TDD, as AGENTS.md asks.

- **pytest** (`tests/test_guide.py`): `guides("es")` returns the Spanish twin and falls back to English per file; the
  order and the fields; `GET /api/app/guide` needs the app token; English and Spanish twins have the same number of
  H2 and the same marker sequence; every `cmd:` names a catalog command; every `portal:` address resolves to a portal
  route (the heads in `zones.js`/`router.js`); every internal link points at an existing heading of that language;
  `init_templates` copies the new guides into a project that lacks them and never overwrites one that has them.
- **Vitest** (desktop renderer): the parser (each block kind, inline formatting, markers, slugs equal to the portal's,
  HTML shown as text); the search; `Guide.jsx` (tabs, index, a marker button navigates, a missing section renders no
  button); every `go:` marker names a section of `nav.js` and every `tour:` marker a tour of `tour.js` (reading the
  guide files); `tour.js` (steps, placement at the window's edges, missing targets); `Tour.jsx` (keys, focus, close,
  the centred fallback); nav, palette (`g h`, the Guide group) and the Summary offer.
- Builds: `renderer-build/` and `app-build/` rebuilt and committed (CI compares them with their source).
- The suite green on this machine (`uv run pytest -n auto`, `npm test` in the renderer and the portal, `node --test`).

## 9. Versions and compatibility

- `VERSIONS["kit"]` 4.69.2 → **4.70.0** (a new place in the app); the README badge follows.
- Old projects: nothing to migrate. The new guide files are added by the next `setup` because `init_templates` only
  creates missing templates; an existing `tutorial.md` keeps the team's copy (templates are copied once) — said in the
  commit.
- No CLI command, flag, `workspace.yaml` key or file location changes.

## 10. Order of work

1. The server (`lib/guide.py`, the endpoint) and the app's Guide (parser, view, nav, palette, Machine card), with tests.
2. The four guides in English, then their Spanish twins, checked against the code.
3. The tour (engine, overlay, tours, `data-tour` targets, entry points), with tests.
4. The command guide and the wizard tutorial; the README; the copy fixes of §6; version bump; builds; full suite.

Follow-up, not in this piece: the portal's `app` mode (the AppOnly buttons, **Back to the app**) is unreachable since
the desktop window never hosts the portal; whether to remove it or host the portal again is its own decision.
