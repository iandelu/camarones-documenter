# Portal: Cofundo design system and an "ask first" dashboard layout

Date: 2026-10-24 · Status: **approved design, not built** · Sub-project 1 of 3

## 1. Context and decisions

The portal (`.camarones/portal/app/`) is the team's **viewer**: deployed as a static export from CI (read-only) and,
optionally, as a server (sub-project 3). CLI parity is **not** a portal goal: it goes to a future desktop app
(Electron or Tauri). The portal shows the project and lets people update *global* things (review, team config,
C4/boards), never machine-level work.

Decisions taken with the user:

| Topic | Decision |
|---|---|
| Visual identity | Cofundo's visual language (tokens, type, components, console density); the product stays **Camarón** (its name, its intern-shrimp voice). No "cofundo" wordmark |
| Dark mode | Keep it: a dark theme derived from Cofundo's tokens (Cofundo itself has none) |
| Installing the design system | As a skill in this kit repo (`.claude/skills/`), not shipped to projects |
| Home layout | "Ask first": the ask box on the aurora hero, the project **state** right below, then zone tiles |
| Navigation inside a zone | Breadcrumbs + ⌘K only. No tab bar, no zone pills |

### Sub-projects (each gets its own spec → plan → build)

1. **This spec.** Design system + dashboard structure. Restyle only; every current view keeps its behaviour.
2. **Dashboard data and the command catalog.** Home KPIs beyond the docs index (plan, CVEs, unanswered questions,
   runs, team usage) as JSON snapshots written by `camaron portal` (and served by the API live). A catalog of every
   CLI command with its verdict (portal / desktop app / CLI only / merge / deprecate) and a CLI triage report in
   `docs/research/` generated from it; it is also the contract for the desktop app.
3. **Deployable team server.** Docker, identity from the reverse proxy, writes for review, team config and C4/boards
   committed and **pushed straight to `main`** of `cam-docs` (user decision; `docs/research/team-server.md` says the
   opposite today and is updated then), a periodic pull.

Later: the desktop app.

## 2. Visual system

### 2.1 The skill

- Copy the package verbatim to `.claude/skills/cofundo-design-system/` (`SKILL.md`, `guia-de-marca.md`, `tokens.css`,
  `tokens.json`, `componentes.css`, `componentes/*.md`, `muestrario.html`).
- Add `.claude/skills/cofundo-design-system/CAMARON.md`: how the portal adapts it, and it wins over the package where
  they differ:
  - Wordmark «camarón», lowercase, Big Shoulders 700. Bricolage Grotesque is not loaded. The favicon stays the
    existing `legacy/favicon.svg`.
  - The derived dark theme (§2.2) is allowed; the package's "no dark mode" note does not apply to the portal.
  - Voice: AGENTS.md §3 (intern shrimp, at most one joke per screen, none in errors, warnings, decisions,
    destructive actions). Cofundo's copy rules that agree with it apply too: no copy without a way out
    ("No data", "Something went wrong"), a server rejection shown as it is, figures from real data only.
  - The three legal rules of the package are about Cofundo's sales product and do not apply.
  - Fonts are served by the portal (§2.3), never from Google Fonts.
- `AGENTS.md` (kit repo) gets one line in the repo map / working rules: portal UI work follows that skill and its
  `CAMARON.md`.

### 2.2 Tokens and theming

- New `portal/app/src/tokens.css` (imported by the React entry and linked from `index.html` before `legacy/app.css`):
  Cofundo's `:root` values (canvas, ink ×3, rule, aurora ×5, accent, `acento-texto`, `estado-*`, type scale, radii,
  shadows, easing, durations, console radii).
- Dark theme, under the same selectors the portal already uses (`@media (prefers-color-scheme: dark)` guarded by
  `:root:not([data-theme="light"])`, and `:root[data-theme="dark"]`):

  | Token | Light (Cofundo) | Dark (derived) |
  |---|---|---|
  | `--color-canvas` | `#fafaf7` | `#121211` |
  | `--color-canvas-elevated` | `#ffffff` | `#1b1b19` |
  | `--color-ink` | `#0a0a0a` | `#f2f1ec` |
  | `--color-ink-soft` | `#4a4a4a` | `#c4c3bd` |
  | `--color-ink-dim` | `#6b6b6b` | `#9a9993` |
  | `--color-rule` | `rgba(10,10,10,.08)` | `rgba(242,241,236,.10)` |
  | `--color-accent` | `#0a0a0a` | `#f2f1ec` (text on it: `--color-canvas`) |
  | `--color-acento-texto` | `#6d28d9` | `#b9a3ff` |
  | `--color-estado-bien / -aviso / -mal` | `#166534 / #92400e / #b91c1c` | `#6fcf8f / #f0b36b / #ff8f8f` |
  | aurora | as Cofundo | the same hues mixed at lower strength in `aurora-bg*` (background only, never text) |

  Final dark values are whatever passes the contrast test (§5) with the fewest changes from this table.
- `legacy/app.css` keeps its variable names (`--bg`, `--panel`, `--raise`, `--ink`, `--ink-2`, `--muted`, `--line`,
  `--accent`, `--on-accent`, `--ok`, `--warn`, `--danger`, `--sans`…) but they become **aliases** of the new tokens,
  in one place, for both themes. `portal/app/src/styles.css` does the same. The legacy views and the React views
  change look without rewriting their markup.

### 2.3 Fonts

- Inter (400/500/600) and Big Shoulders (600/700) as woff2 in `portal/app/public/fonts/` with their OFL licence
  files, declared with `@font-face` in `tokens.css`. Same pattern as the vendored Excalidraw fonts.
- No request to a third party from the portal: the static export is hosted on internal networks.

### 2.4 Components

Restyle, not new widgets:

- Buttons and chips: pills (`--radius-pildora`); one black (`accent`) button per block, the rest ghost.
- Cards, panels, tiles: `--radius-tarjeta` (console density uses `--consola-radio-*`), 1px `--color-rule`,
  `canvas-elevated`. Shadow only on what floats (palette dialog, zoomer, hover lift of a tile).
- Section titles: Big Shoulders 600 with an eyebrow above; the home hero and each zone's cover use the two-tone
  title (`t-eco`).
- Notices ("out of date", "AI draft", "read-only"): `co-aviso` style. Loading: `co-esqueleto` with the shape of
  what comes, not a spinner.
- State colours only with their word (never colour alone), as today's trust dots plus label.
- Motion: only `transform`/`opacity`, `--ease-out-soft`, 200 ms hover/focus, 400 ms state changes;
  `prefers-reduced-motion` respected.

## 3. Structure and navigation

### 3.1 Top bar

Wordmark (link to `#/`) · breadcrumbs (`camarón / Arquitectura / C4`) · search button (⌘K) · language · theme.
The `#tabs` bar is removed. The mobile menu button stays for views with a side tree (Docs, wikis).

### 3.2 Zones

| Zone | Route of its cover | Views (existing routes, unchanged) | Static export |
|---|---|---|---|
| Docs | `#/docs` (today's docs home) | pages `#/docs/…`, wikis `#/wikis`, `#/wiki/…` | yes |
| Arquitectura | `#/arch` (new) | C4 `#/c4`, Code `#/code`, Data `#/data`, Libraries `#/libs`, Boards `#/boards` | C4, Code only |
| Plan | `#/plan` (new) | Pipeline `#/pipeline` | no |
| Calidad | `#/quality` (new) | KPIs `#/kpis`, CI `#/ci` | no |
| Revisión | `#/review` (today's review view, unchanged) | — | yes |
| *(Ask, not a zone)* | the Home hero | `#/ask` | search only |

- A zone cover is the two-tone title + a tile per view (name, one line of what it shows). A zone whose views are all
  unavailable in this mode is not shown (Home tiles and ⌘K). A cover with a single available view still renders,
  as a one-tile page, so breadcrumbs always resolve.
- Breadcrumbs come from the route: `camarón` / zone / view / page path segments (docs) — computed by a pure module
  (§3.4).

### 3.3 Home (`#/`)

1. **Hero** on `aurora-bg`: eyebrow (project · repo count), two-tone title, the ask box. Live: it opens Ask with the
   question. Static: it opens search with the text (today's behaviour of the static portal).
2. **Estado**: KPI tiles built only from the index payload the portal already receives (`tree()` in `lib/serve.py`
   and its static equivalent): confirmed / total pages, needs-reconfirm, drafts, pending feedback. KPIs that need new
   data are sub-project 2 and are **absent** until then (no empty tiles, no "no data").
3. **Zones**: one tile per available zone with one figure from the same payload where there is one (pages, C4 views,
   items to review).

### 3.4 Routing and compatibility

- `#/` changes from "docs home" to Home; the docs home moves to `#/docs`, which already resolves to it today. Every
  other route (`#/docs/…`, `#/wiki/…`, `#/wikis`, `#/c4/…`, `#/code/…`, `#/review`, `#/status`, `#/search/…`,
  `#/new`, the React views) keeps working unchanged.
- New pure module `portal/app/src/zones.js`: the zone table above, `zonesFor(mode, index)` (available zones and views
  for static/live and what the index holds), `crumbs(hash, index)` and `paletteEntries(mode, index)`. The legacy
  `app.js` calls it through `window.CamaronZones` (same bridge pattern as `window.CamaronContent`).
- ⌘K palette: today's page search plus zones and views ("C4", "Librerías", "Revisión"), filtered by mode.

## 4. Error handling and empty states

- An API failure in live mode is shown as ours ("No he podido leer X del servidor: <message>"), never as "you
  can't". A view unavailable in static mode is not linked at all.
- A zone with nothing yet says why and what produces it (e.g. Code: "no code graph yet — `camaron graph` builds it"),
  in `es` and `en`.

## 5. Testing (TDD)

- **vitest** (`portal/app/src/*.test.js`):
  - `zones.test.js`: zones per mode, hidden empty zones, crumbs for each route kind (docs page, wiki page, view,
    cover, unknown), palette entries.
  - `tokens.test.js`: parses `tokens.css`; every text token (`ink`, `ink-soft`, `ink-dim`, `acento-texto`,
    `estado-*`, text on `accent`) reaches 4.5:1 on `canvas` and `canvas-elevated`, in light **and** dark.
- **pytest**:
  - The static export (`camaron portal`) contains `fonts/*.woff2` and `tokens.css`, and no file in it references
    `fonts.googleapis.com` / `fonts.gstatic.com`.
  - Existing check that `app-build/` matches its source stays green after rebuilding.
- **End to end**: `uv run scripts/sandbox.py` (reset if needed, `init`, `up --foreground`), then in a browser: Home,
  each zone cover and view, a docs page, ⌘K, both themes, `es`/`en`, the static export. No console errors.

## 6. Compatibility, versions, docs

- No CLI command, flag, `workspace.yaml` key, frontmatter field or project file changes. Old portal URLs resolve.
- Bump `VERSIONS["kit"]` (visible change) and the README badge.
- Same commit: README (portal description), `lib/tutorial.py` + regenerated `.camarones/TUTORIAL.md`,
  `templates/docs/guides/tutorial.md` and `templates/docs/i18n/es/guides/tutorial.md` (portal navigation: Home,
  zones, ⌘K). The commit says projects keep their old copy of the guide.
- All new UI strings in `es` and `en` (`portal/app/src/i18n.js` and the legacy `T` strings).
- macOS/Windows/Linux: nothing OS-specific is added; the font files keep LF-agnostic binary handling
  (`.gitattributes`: `*.woff2 binary` if not already covered).

## 7. Out of scope

New KPIs and snapshots, the command catalog and CLI triage (sub-project 2); the team server and its writes
(sub-project 3); the desktop app; porting legacy views to React; new icons (the package has no icon system: text
glyphs such as `→` only).
