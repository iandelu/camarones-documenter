# Portal design system and ask-first Home — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the portal with Cofundo's visual language (Camarón brand, derived dark theme, self-hosted fonts) and
replace the 12-tab bar with an ask-first Home, zone covers, breadcrumbs and a ⌘K palette that also lists zones.

**Architecture:** A theme layer (`public/theme/tokens.css` + fonts) that the existing legacy variables alias, so the
legacy views and the React views change look without markup rewrites. A pure ES module `src/zones.js` (zone table,
availability per mode, breadcrumbs, palette entries, Home KPIs) exposed to the legacy router as
`window.CamaronZones`; `legacy/app.js` draws the new top bar, Home and zone covers from it.

**Tech Stack:** plain scripts in `public/legacy/`, React 19 + Vite 8 in `src/`, vitest 5, pytest, Python stdlib server.

**Spec:** `docs/superpowers/specs/2026-10-24-portal-design-system-design.md`

## Global Constraints

- Paths below are relative to the repo root; `APP` = `.camarones/portal/app`.
- macOS, Windows, Linux: `pathlib` only in Python, `encoding="utf-8"` on every read/write.
- Every UI string in `en` and `es` (legacy: `I18N` in `APP/public/legacy/core.js`; React: `S` in `APP/src/i18n.js`).
  No jokes in errors, warnings, decisions. No "No data" / "Something went wrong" copy.
- No request to a third party from the portal: no `fonts.googleapis.com`, no `fonts.gstatic.com`.
- No CLI command, flag, `workspace.yaml` key, frontmatter field or project file changes. Every existing route keeps
  working: `#/docs`, `#/doc/…`, `#/docs/<path>[::anchor]`, `#/wiki/…`, `#/wikis[/…]`, `#/c4[/…]`, `#/code[/…]`,
  `#/review`, `#/status`, `#/search/…`, `#/new`, `#/ask`, `#/boards[/…]`, `#/pipeline`, `#/libs`, `#/data`, `#/kpis`,
  `#/ci`.
- Text tokens ≥ 4.5:1 contrast on `--color-canvas` and `--color-canvas-elevated`, light and dark.
- Aurora colours are backgrounds only. Buttons and chips are pills. One `accent` (black/ink) button per block.
- Motion: only `transform`/`opacity`; 200 ms hover/focus, 400 ms state change; `prefers-reduced-motion` respected.
- `APP/../app-build/` is committed and must match the source (`npm ci && npm test && npm run build` in `APP`).
- Other sessions may edit the tree: stage only this plan's files. Conventional commits ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Deviation from the spec, on purpose: tokens live in `APP/public/theme/tokens.css` (linked in `<head>` before
  `legacy/app.css`), not `src/tokens.css`. A Vite-imported stylesheet loads after the legacy CSS and after first
  paint; the theme must apply first.

## Review Focus

1. **A project with no docs yet** (fresh `init`, `T.docs` empty, no C4 views): Home must show today's empty state
   (first-look button live, tutorial link), never KPI tiles reading `0/0`. → Task 5 `homeKpis` test + Task 6 step.
2. **A live-only deep link opened in the static export** (`#/pipeline`, `#/boards/x`, `#/plan`): lands on Home, no
   console error, no crumb for an unavailable zone. → Task 5 tests on `zonesFor`/`crumbs` in static mode.
3. **Old bookmarks** (`#/status`, `#/doc/<path>`, `#/wikis/api`): resolve as today, with crumbs. → Task 5 tests.
4. **Encoded hashes and anchors** (`#/docs/flows/alta%20mascota.md::paso-2`, accents in paths): crumbs decode and
   drop the `::anchor`. → Task 5 test.
5. **A page path not in the index** (deleted or not yet exported page): crumb falls back to the file name, no throw.
   → Task 5 test.

---

### Task 1: Install the design system as a kit skill

**Files:**
- Create: `.claude/skills/cofundo-design-system/` (verbatim copy of the package: `SKILL.md`, `guia-de-marca.md`,
  `tokens.css`, `tokens.json`, `componentes.css`, `muestrario.html`, `componentes/*.md`)
- Create: `.claude/skills/cofundo-design-system/CAMARON.md`
- Modify: `AGENTS.md` (§4 repo map, `portal/` row)

- [ ] **Step 1: Copy the package**

Source: `C:\Users\aneri\Downloads\cofundo-design-system.zip` (already extracted once to the session scratchpad
`…/scratchpad/ds/cofundo-design-system/`). Copy every file unchanged, LF line endings.

- [ ] **Step 2: Write `CAMARON.md`** (English, short). It states that, for the Camarón portal, it wins over the
package where they differ, and lists exactly the spec's §2.1 adaptations: wordmark «camarón» lowercase in Big
Shoulders 700, no Bricolage; favicon stays `legacy/favicon.svg`; derived dark theme allowed (values in
`APP/public/theme/tokens.css`); voice is AGENTS.md §3 plus Cofundo's no-dead-end copy rules; the package's three legal
rules do not apply; fonts are self-hosted, never Google Fonts; the package's `-sm` sizes and console radii are the
portal's density.

- [ ] **Step 3: Point agents at it.** In `AGENTS.md` §4, append to the `.camarones/portal/` row: "UI work follows the
`cofundo-design-system` skill (`.claude/skills/`) and its `CAMARON.md`."

- [ ] **Step 4: Verify**

Run: `git status --short .claude AGENTS.md` → the skill folder and `AGENTS.md` only.
Run: `uv run pytest -q` → green (nothing else touched).

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/cofundo-design-system AGENTS.md
git commit -m "chore(portal): install the Cofundo design system as a kit skill"
```
(Body: nothing a user can notice; the kit repo only.)

---

### Task 2: Theme tokens, self-hosted fonts, contrast guard

**Files:**
- Create: `APP/public/theme/tokens.css`
- Create: `APP/public/theme/fonts/Inter.woff2`, `APP/public/theme/fonts/BigShoulders.woff2`,
  `APP/public/theme/fonts/OFL-Inter.txt`, `APP/public/theme/fonts/OFL-BigShoulders.txt`
- Create: `APP/src/tokens.test.js`
- Modify: `APP/index.html` (link before `legacy/app.css`)
- Modify: `.gitattributes` (`*.woff2 binary`)
- Modify: `tests/test_portal_app.py` (`test_the_build_is_committed_and_complete` ref regex)
- Modify: `tests/test_portal_data.py` (static export assertions)

**Interfaces:**
- Produces (CSS custom properties on `:root`, both themes): `--color-canvas`, `--color-canvas-elevated`,
  `--color-ink`, `--color-ink-soft`, `--color-ink-dim`, `--color-rule`, `--color-accent`, `--color-on-accent`,
  `--color-acento-texto`, `--color-estado-bien`, `--color-estado-aviso`, `--color-estado-mal`,
  `--color-aurora-{cyan,violet,pink,coral,amber}`, `--font-impact`, `--font-sans`, `--font-mono`, the `--text-*`
  scale, `--radius-{tarjeta,campo,pildora}`, `--consola-radio-{tarjeta,control,chico}`, `--sombra-{hover,modal,menu}`,
  `--ease-out-soft`, `--duration-{quick,normal,slow}`. `--color-on-accent` is new (text on the accent: `#ffffff`
  light, `--color-canvas` dark).

- [ ] **Step 1: Write the failing test `APP/src/tokens.test.js`**

Parse `../public/theme/tokens.css` with `fs`/`url` (vitest runs in node). Extract the light block (`:root { … }`
first occurrence) and the dark block (`:root[data-theme="dark"] { … }`); the dark block's values override light.
Contrast = WCAG relative luminance ratio of hex colours (write `contrast(a, b)` in the test file).

```js
test.each(['light', 'dark'])('text tokens reach 4.5:1 on the canvas (%s)', (theme) => {
  const t = tokens(theme)
  for (const fg of ['--color-ink', '--color-ink-soft', '--color-ink-dim', '--color-acento-texto',
                    '--color-estado-bien', '--color-estado-aviso', '--color-estado-mal'])
    for (const bg of ['--color-canvas', '--color-canvas-elevated'])
      expect(contrast(t[fg], t[bg]), `${fg} on ${bg}`).toBeGreaterThanOrEqual(4.5)
  expect(contrast(t['--color-on-accent'], t['--color-accent'])).toBeGreaterThanOrEqual(4.5)
})
test('the dark block repeats under prefers-color-scheme', () => {
  expect(declarations(block(css, '@media (prefers-color-scheme: dark)')))
    .toEqual(declarations(block(css, ':root[data-theme="dark"]')))
})
test('fonts are self-hosted', () => {
  expect(css).not.toMatch(/fonts\.(googleapis|gstatic)\.com/)
  expect(css).toMatch(/url\(["']?fonts\/Inter\.woff2/)
  expect(css).toMatch(/url\(["']?fonts\/BigShoulders\.woff2/)
})
```

- [ ] **Step 2: Run** `npm test -- tokens` in `APP` → FAIL (file missing).

- [ ] **Step 3: Get the fonts.** Variable TTFs and `OFL.txt` from `github.com/google/fonts` (`ofl/inter/`,
`ofl/bigshoulders/`), subset to Latin + Latin-1 + Latin Extended-A and converted to woff2 with fontTools:
`uv run --with fonttools --with brotli pyftsubset <ttf> --unicodes="U+0000-017F,U+2000-206F,U+20AC,U+2190-21FF" --flavor=woff2 --layout-features='*' --output-file=<dst>`.
Keep the variable `wght` axis (Inter 400–600, Big Shoulders 600–700 are used).

- [ ] **Step 4: Write `APP/public/theme/tokens.css`.** Header comment: source (Cofundo package, 2026-10-02 web
version), what the dark block is, "aurora is background only". Content:
  - `@font-face` for `Inter` (`font-weight: 400 600`) and `Big Shoulders` (`font-weight: 600 700`), `font-display:
    swap`, `url("fonts/….woff2") format("woff2")` (relative to the stylesheet, so a sub-path export works).
  - `:root` light block: Cofundo's values from the package `tokens.css` (canvas `#fafaf7`, elevated `#ffffff`, ink
    `#0a0a0a`, soft `#4a4a4a`, dim `#6b6b6b`, rule `rgba(10,10,10,.08)`, accent `#0a0a0a`, on-accent `#ffffff`,
    acento-texto `#6d28d9`, estados `#166534 / #92400e / #b91c1c`, aurora, type scale, radii, shadows, motion,
    console radii), `--font-impact: "Big Shoulders", "Arial Narrow", Impact, sans-serif`, `--font-sans: Inter, …`.
    No `--font-display` (no Bricolage). `color-scheme: light`.
  - Dark overrides under `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {…} }` and again under
    `:root[data-theme="dark"] {…}`: canvas `#121211`, elevated `#1b1b19`, ink `#f2f1ec`, soft `#c4c3bd`, dim `#9a9993`,
    rule `rgba(242,241,236,.10)`, accent `#f2f1ec`, on-accent `#121211`, acento-texto `#b9a3ff`, estados
    `#6fcf8f / #f0b36b / #ff8f8f`, shadows with alpha `.5`, `color-scheme: dark`. Aurora hues unchanged (their
    strength drops in the `.aurora-bg` mixes, Task 3). If a value fails Step 1, change only that value.
  - Link it in `APP/index.html`: `<link rel="stylesheet" href="theme/tokens.css">` right before `legacy/app.css`.

- [ ] **Step 5: Run** `npm test -- tokens` → PASS.

- [ ] **Step 6: Extend the pytest guards (failing first)**
  - `tests/test_portal_app.py::test_the_build_is_committed_and_complete`: the ref regex accepts `theme/` too
    (`(?:assets|legacy|theme)/`), and add `assert '<link rel="stylesheet" href="theme/tokens.css">' in html` before
    the `legacy/app.css` link (`html.index(...) <`).
  - `tests/test_portal_data.py::test_static_export_carries_the_new_fields`: add
    ```python
    assert (site / "theme" / "tokens.css").is_file() and (site / "theme" / "fonts" / "Inter.woff2").is_file()
    texts = [f.read_text(encoding="utf-8", errors="ignore") for f in site.rglob("*") if f.suffix in (".html", ".css", ".js")]
    assert not any(re.search(r"fonts\.(googleapis|gstatic)\.com", t) for t in texts)
    ```
  Run `uv run pytest tests/test_portal_app.py tests/test_portal_data.py -q` → FAIL until the build is redone.

- [ ] **Step 7: Rebuild and verify.** In `APP`: `npm run build`. Then
`uv run pytest tests/test_portal_app.py tests/test_portal_data.py -q` → PASS. Add `*.woff2 binary` to
`.gitattributes`.

- [ ] **Step 8: Commit**

```bash
git add .gitattributes .camarones/portal/app/public/theme .camarones/portal/app/src/tokens.test.js .camarones/portal/app/index.html .camarones/portal/app-build tests/test_portal_app.py tests/test_portal_data.py
git commit -m "feat(portal): Cofundo theme tokens with a derived dark theme and self-hosted fonts"
```

---

### Task 3: Legacy and React styles become aliases of the theme; components restyled

**Files:**
- Modify: `APP/public/legacy/app.css` (token block lines 1-33 and the component rules that set shape/colour)
- Modify: `APP/src/styles.css`, `APP/src/Native.jsx` (loading fallback)
- Create: `APP/src/styles.test.js`

**Interfaces:**
- Consumes: Task 2 tokens.
- Produces: legacy variable names kept (`--bg --panel --raise --ink --ink-2 --muted --line --accent --accent-ink
  --accent-soft --on-accent --ok --warn --draft --info --danger --code-bg --shadow --hl-* --sans --mono`) as aliases;
  utility classes used by Tasks 5-6: `.eyebrow`, `.t-eco`, `.t-impact` (Big Shoulders 600), `.aurora-bg`,
  `.aviso` (Cofundo `co-aviso`), `.skeleton` (Cofundo `co-esqueleto`), `.tile` (card link with hover lift),
  `.tiles` (auto-fill grid, `minmax(14rem, 1fr)`), `.kpi` (eyebrow + Big Shoulders figure + caption).

- [ ] **Step 1: Write the failing test `APP/src/styles.test.js`**

```js
test.each(['../public/legacy/app.css', './styles.css'])('%s defines no raw colours', (rel) => {
  const css = read(rel).replace(/\/\*[\s\S]*?\*\//g, '')
  expect(css.match(/#[0-9a-f]{3,8}\b|rgba?\(\s*\d/gi) ?? []).toEqual([])
})
test('legacy variables alias the theme in one place', () => {
  const css = read('../public/legacy/app.css')
  for (const v of ['--bg', '--raise', '--ink', '--muted', '--line', '--accent', '--on-accent', '--ok', '--warn', '--danger'])
    expect(css).toMatch(new RegExp(`${v}:\\s*var\\(--`))
  expect(css).not.toMatch(/prefers-color-scheme/)          // theming lives in theme/tokens.css only
})
```
Run `npm test -- styles` → FAIL.

- [ ] **Step 2: Replace the three token blocks of `app.css` with one alias block** (`:root { --bg:
var(--color-canvas); --panel: var(--color-canvas); --raise: var(--color-canvas-elevated); --ink: var(--color-ink);
--ink-2: var(--color-ink-soft); --muted: var(--color-ink-dim); --line: var(--color-rule); --accent:
var(--color-accent); --accent-ink: var(--color-acento-texto); --accent-soft: color-mix(in oklch, var(--color-ink) 6%,
transparent); --on-accent: var(--color-on-accent); --ok: var(--color-estado-bien); --warn: var(--color-estado-aviso);
--danger: var(--color-estado-mal); --draft: var(--color-ink-dim); --info: var(--color-ink); --code-bg:
color-mix(in oklch, var(--color-ink) 4%, var(--color-canvas-elevated)); --shadow: var(--sombra-menu); --sans:
var(--font-sans); --mono: var(--font-mono); … }`). Highlight colours (`--hl-*`) map to ink / ink-soft / ink-dim /
acento-texto. Every remaining hex/rgb in the file becomes a token or `color-mix` of tokens.

- [ ] **Step 3: Restyle components in `app.css`** (no markup changes): `button`/`a.button` → `border-radius:
var(--radius-pildora)`, ghost variant keeps `--line` border; `input, textarea, select` → `var(--radius-campo)`;
`.card`, `.box`, panels → `var(--consola-radio-tarjeta)`, 1px `--line`, `--raise`, no shadow except hover lift
(`translateY(-2px)` + `--sombra-hover`, 200 ms `--ease-out-soft`); headings `h1, h2` of `.page` → `--font-impact`
600, `letter-spacing: -.01em`, `line-height: .95`; dialogs (`#palette`, `#zoomer`) → `--sombra-modal`; trust dots
keep their label; body `font-size: var(--text-body)`. Add the utility classes listed in Interfaces (`.aurora-bg`
copies the package's five radial gradients; in dark, each `color-mix` strength halves — use a
`--aurora-strength` custom property set to `1` light / `.5` dark in `tokens.css`, added in this task).
`@media (prefers-reduced-motion: reduce)` disables transitions/animations.

- [ ] **Step 4: Same aliasing in `APP/src/styles.css`** (`#native` rules): replace hex/rgb with tokens; `#native h1`
→ `--font-impact`; `.seg`/chips → pills; radii from console tokens. In `APP/src/Native.jsx` the `Suspense` fallback
becomes `<div className="skeleton" aria-busy="true" />` (a block the size of a view header and a card row), not `…`.

- [ ] **Step 5: Run** `npm test` → all PASS (existing vitest included).

- [ ] **Step 6: Look at it.** `npm run build`; `uv run scripts/sandbox.py cli up --foreground` (after
`uv run scripts/sandbox.py reset` and `uv run scripts/sandbox.py cli init` if the sandbox has no `cam-docs`) in the
background; open `http://127.0.0.1:8080` in the browser pane; check a docs page, C4, Pipeline, KPIs in light and
dark. Text readable, pills, no pure-white page background.

- [ ] **Step 7: Commit**

```bash
git add .camarones/portal/app/public/legacy/app.css .camarones/portal/app/src/styles.css .camarones/portal/app/src/Native.jsx .camarones/portal/app/src/styles.test.js .camarones/portal/app/public/theme/tokens.css .camarones/portal/app-build
git commit -m "feat(portal): legacy and React styles alias the Cofundo theme"
```

---

### Task 4: Ask takes a question from the route

**Files:**
- Modify: `APP/src/Ask.jsx`

**Interfaces:**
- Produces: route `#/ask/<encodeURIComponent(question)>` opens Ask with the question filled in and searched once on
  mount. `#/ask` unchanged.

- [ ] **Step 1: Implement.** `Ask({ arg })`: initial question state = `arg ? decodeURIComponent(arg) : ''`; a
`useEffect` with `[]` deps submits once when it is non-empty (same function the form's submit calls).
(`Native` already re-mounts the view per `arg` through its `key`.)

- [ ] **Step 2: Verify in the sandbox** (portal from Task 3 running, rebuilt): open
`#/ask/%C2%BFQu%C3%A9%20expone%20la%20API%3F` → the box shows «¿Qué expone la API?» and results appear without
pressing Ask. `npm test` → PASS.

- [ ] **Step 3: Commit**

```bash
git add .camarones/portal/app/src/Ask.jsx .camarones/portal/app-build
git commit -m "feat(portal): Ask opens with a question from the route"
```

---

### Task 5: `zones.js` — zones, availability, breadcrumbs, palette entries, Home KPIs

**Files:**
- Create: `APP/src/zones.js`
- Create: `APP/src/zones.test.js`
- Modify: `APP/src/main.jsx` (expose `window.CamaronZones` before dispatching `camaron:native-ready`)

**Interfaces:**
- Consumes: the index object the legacy code calls `T` (`{ project, repos: string[], docs: [{path, title, space,
  trust}], views: [{id, kind}], codeGraphs: string[], codeMaps: string[], summary: {confirmed, draft,
  'needs-reconfirm', total}, feedback?: number }`); `mode: 'static' | 'live'`.
- Produces (named exports, also on `window.CamaronZones`):
  - `ZONES`: ordered `[{ id, href, views: [{ id, href, live?: true, needs?: (index) => boolean }] }]` —
    `docs` `#/docs` [`pages` `#/docs`, `wikis` `#/wikis` needs (live || any `space==='wiki'`)];
    `arch` `#/arch` [`c4` `#/c4`, `code` `#/code` needs (codeMaps.length || codeGraphs.length), `data` `#/data` live,
    `libs` `#/libs` live, `boards` `#/boards` live]; `plan` `#/plan` [`pipeline` `#/pipeline` live];
    `quality` `#/quality` [`kpis` `#/kpis` live, `ci` `#/ci` live]; `review` `#/review` [`review` `#/review`].
    Labels are i18n keys: zone `zone.<id>`, its line `zoned.<id>`, view `view.<id>`.
  - `zonesFor(mode, index) → [{ id, href, views: [{ id, href }] }]` — only available views, zones with none dropped.
  - (internal, not exported) route aliases: `doc` → `docs`, `wiki`/`wikis` → the `wikis` view, `status` → `review`.
  - `crumbs(hash, mode, index) → [{ key?: string, text?: string, href: string | null }]`.
  - `paletteEntries(mode, index) → [{ key, href, zone }]` — one per available zone cover and view (a view whose href
    equals its zone cover appears once).
  - `homeKpis(index) → [{ id, value: string, tone: 'ok' | 'warn' | null }]` — `[]` when `summary.total` is 0;
    otherwise `confirmed` (`"41/57"`, tone `ok`), `reconfirm` (`summary['needs-reconfirm']`, tone `warn` if > 0),
    `drafts` (`summary.draft`), and `feedback` only when `index.feedback` is a number (tone `warn` if > 0).

- [ ] **Step 1: Write the failing tests `APP/src/zones.test.js`**

Fixture `idx` = project with 3 docs (`index.md`, `flows/alta-mascota.md` titled «Alta de mascota», wiki
`repos/api/http-api.md` titled «HTTP API»), one view, no code, `summary {confirmed:1, draft:1, 'needs-reconfirm':1, total:3}`,
`feedback: 2`.

```js
test('static export: live-only zones and views are gone', () => {
  const z = zonesFor('static', idx)
  expect(z.map((x) => x.id)).toEqual(['docs', 'arch', 'review'])
  expect(z.find((x) => x.id === 'arch').views.map((v) => v.id)).toEqual(['c4'])
  expect(paletteEntries('static', idx).map((e) => e.href)).not.toContain('#/pipeline')
})
test('live: every zone, code only with a graph', () => {
  expect(zonesFor('live', idx).map((x) => x.id)).toEqual(['docs', 'arch', 'plan', 'quality', 'review'])
  expect(zonesFor('live', idx).find((x) => x.id === 'arch').views.map((v) => v.id)).toEqual(['c4', 'data', 'libs', 'boards'])
  expect(zonesFor('live', { ...idx, codeMaps: ['api'] }).find((x) => x.id === 'arch').views[1].id).toBe('code')
})
test('crumbs of a docs page decode, drop the anchor and use the title', () => {
  expect(crumbs('#/docs/flows/alta-mascota.md::paso-2', 'live', idx)).toEqual([
    { key: 'zone.docs', href: '#/docs' }, { key: 'sec.flows', href: null }, { text: 'Alta de mascota', href: '#/docs/flows/alta-mascota.md' }])
  expect(crumbs('#/docs/flows/alta%20nueva.md', 'live', idx).at(-1)).toEqual({ text: 'alta nueva.md', href: '#/docs/flows/alta%20nueva.md' })
})
test('old routes keep their crumbs', () => {
  expect(crumbs('#/status', 'live', idx)).toEqual([{ key: 'zone.review', href: '#/review' }])
  expect(crumbs('#/doc/index.md', 'live', idx)[0]).toEqual({ key: 'zone.docs', href: '#/docs' })
  expect(crumbs('#/wiki/api/http-api.md', 'live', idx).map((c) => c.key || c.text)).toEqual(['zone.docs', 'view.wikis', 'api', 'HTTP API'])
  expect(crumbs('#/c4/flow_checkout', 'live', idx)).toEqual([
    { key: 'zone.arch', href: '#/arch' }, { key: 'view.c4', href: '#/c4' }, { text: 'flow_checkout', href: null }])
})
test('home, unknown and unavailable routes have no crumbs', () => {
  for (const h of ['', '#/', '#/nope', '#/nope/x']) expect(crumbs(h, 'live', idx)).toEqual([])
  expect(crumbs('#/pipeline', 'static', idx)).toEqual([])
  expect(crumbs('#/plan', 'static', idx)).toEqual([])
})
test('search keeps its query as a crumb', () => {
  expect(crumbs('#/search/fecha%20cita', 'live', idx)).toEqual([{ key: 'search', href: null }, { text: 'fecha cita', href: null }])
})
test('home KPIs come from the index only, none for an empty project', () => {
  expect(homeKpis(idx)).toEqual([
    { id: 'confirmed', value: '1/3', tone: 'ok' }, { id: 'reconfirm', value: '1', tone: 'warn' },
    { id: 'drafts', value: '1', tone: null }, { id: 'feedback', value: '2', tone: 'warn' }])
  expect(homeKpis({ ...idx, docs: [], summary: { confirmed: 0, draft: 0, 'needs-reconfirm': 0, total: 0 } })).toEqual([])
  expect(homeKpis({ ...idx, feedback: undefined }).map((k) => k.id)).not.toContain('feedback')
})
```

- [ ] **Step 2: Run** `npm test -- zones` → FAIL (module missing).

- [ ] **Step 3: Implement `APP/src/zones.js`** with the exports above. Crumb rules: strip `#`, split once on the
first `/` after the leading one, decode with `decodeURIComponent` (on failure use the raw text), drop everything
from `::`. Docs page: zone crumb, then for each folder segment `{ key: 'sec.<seg>' }` for the first segment and
`{ text: seg }` deeper (both `href: null`), then `{ text: title ?? fileName, href: '#/docs/' + rawPath }`. A zone
cover route (`#/arch`) gives its zone crumb only; a view route gives zone + view (+ the rest as one `{ text }`).
A route whose view is unavailable in `mode` gives `[]`. Wiki page `#/wiki/<repo>/<rel>`: zone, `view.wikis`
(`#/wikis`), `{ text: repo, href: '#/wiki/<repo>' }`, then the title of `repos/<repo>/<rel>` from the index (file
name if absent). The Code view stays hidden without a graph, as the Code tab is today; so a zone cover never lists an
unavailable view and never renders empty.

- [ ] **Step 4: Run** `npm test -- zones` → PASS.

- [ ] **Step 5: Expose it.** In `APP/src/main.jsx`: `import * as zones from './zones.js'` and
`window.CamaronZones = zones` next to `window.CamaronContent`, before the `camaron:native-ready` dispatch. `npm test`
→ PASS.

- [ ] **Step 6: Commit**

```bash
git add .camarones/portal/app/src/zones.js .camarones/portal/app/src/zones.test.js .camarones/portal/app/src/main.jsx
git commit -m "feat(portal): zones module for navigation, breadcrumbs and Home KPIs"
```

---

### Task 6: New top bar, Home, zone covers, palette with zones

**Files:**
- Modify: `APP/index.html` (header markup)
- Modify: `APP/public/legacy/app.js` (`drawChrome`, `showHome` → `showDocsHome`, new `showStart`, `showZone`,
  `routeNow`, palette, boot)
- Modify: `APP/public/legacy/core.js` (`I18N` en + es keys)
- Modify: `APP/public/legacy/app.css` (top bar, crumbs, hero, tiles, KPIs)
- Modify: `tests/test_portal_app.py` (`test_the_react_views_are_tabs_of_the_portal`)

**Interfaces:**
- Consumes: `window.CamaronZones` (Task 5), utility classes (Task 3), `#/ask/<q>` (Task 4).
- Produces: routes `#/` (Home), `#/arch`, `#/plan`, `#/quality` (zone covers); `#/docs` = today's docs home.

- [ ] **Step 1: Update the characterization test first** — rename to
`test_the_react_views_are_reached_through_zones` and assert on the new contract:

```python
zones = (kit.kit_dir / "portal" / "app" / "src" / "zones.js").read_text(encoding="utf-8")
for href in ("#/boards", "#/pipeline", "#/kpis", "#/ci", "#/libs", "#/data"):      # Ask is reached from the Home hero
    assert f"'{href}'" in zones
assert "#/ask/" in app
assert "window.CamaronNative.show(view, rest)" in app
assert "id=\"tabs\"" not in (kit.kit_dir / "portal" / "app" / "index.html").read_text(encoding="utf-8")
for key in ("'zone.arch'", "'home.title'"):
    assert core.count(key) == 2                                                   # en + es
```
Run `uv run pytest tests/test_portal_app.py -q` → FAIL.

- [ ] **Step 2: Header.** In `index.html` replace `<nav class="tabs" id="tabs"></nav>` with
`<nav class="crumbs" id="crumbs" aria-label="breadcrumb"></nav>`; the brand link shows the wordmark
`<span class="wordmark">camarón</span>` (keep `#project` text for the project name as the brand's sub-line; remove the
🦐 `.logo` span from the bar, favicon unchanged). Search button, language, theme unchanged.

- [ ] **Step 3: Boot waits for the zones.** At the end of `app.js`, replace `loadTree().then(…)` with
`Promise.all([loadTree(), zonesReady()]).then(…)` where `zonesReady()` resolves at once if `window.CamaronZones`
exists, else on the `camaron:native-ready` event (`{ once: true }`). Keep the existing `.catch`.

- [ ] **Step 4: `drawChrome(active, opts)`** keeps its signature and options but renders `#crumbs` from
`CamaronZones.crumbs(location.hash, STATIC ? 'static' : 'live', T)` — each crumb `t(key)` or `esc(text)`, a link when
`href`, separated by `/` (`<span aria-hidden="true">/</span>`); the last crumb has `aria-current="page"`. `#tabs`
code is removed. `#ro` (read-only notice) gets class `aviso`.

- [ ] **Step 5: Routing.** In `routeNow`: `view === ''` → `showStart()`; `view === 'docs' && !rest` →
`showDocsHome()` (today's `showHome`, renamed, its empty-project branch moved to `showStart`); `['arch', 'plan',
'quality'].includes(view)` → `showZone(view)`; the final fallback → `showStart()`. Every other branch unchanged.
Live-only views in static fall through to `showStart()` as today's fall to the docs home.

- [ ] **Step 6: `showStart()`** (no side tree, no TOC):
  - Empty project (`homeKpis(T)` is `[]` and `!T.views.length`): today's empty state (first-look button live, tutorial
    link), restyled with `.aurora-bg`.
  - Otherwise: hero `.aurora-bg` with eyebrow `t('home.eyebrow', { project: T.project, n: T.repos.length })`,
    title `<h1 class="t-impact">${t('home.title')}<br><span class="t-eco">${t('home.eco')}</span></h1>`, a form with
    one input (placeholder `t('home.askPh')`) that on submit goes to `#/ask/<q>` live or `#/search/<q>` static.
  - Section `t('home.state')` (eyebrow `t('home.stateSub')`) with one `.kpi` per `homeKpis(T)` entry: label
    `t('kpi.<id>')`, value, tone class `ok`/`warn` plus the label word (never colour alone).
  - Section `t('home.zones')`: one `.tile` per `zonesFor(mode, T)` zone: `t('zone.<id>')`, `t('zoned.<id>')`, link to
    its `href`.

- [ ] **Step 7: `showZone(id)`**: two-tone title `t('zone.<id>')` / `t('zoned.<id>')` and one `.tile` per available
view (`t('view.<id>')`, `t('viewd.<id>')`, link). Unavailable zone in this mode → `location.replace('#/')`.

- [ ] **Step 8: Palette.** `paletteInput()` adds a first group `t('zonesGroup')` with
`paletteEntries(mode, T)` filtered by the query against the translated label (all of them when the query is empty,
max 8), before today's page groups. Item icon `→`.

- [ ] **Step 9: Strings** in `I18N` (en / es), exact copy:

| key | en | es |
|---|---|---|
| `zone.docs` | Docs | Docs |
| `zone.arch` | Architecture | Arquitectura |
| `zone.plan` | Plan | Plan |
| `zone.quality` | Quality | Calidad |
| `zone.review` | Review | Revisión |
| `zoned.docs` | Every page, its trust and the repo wikis | Todas las páginas, su estado y las wikis de cada repo |
| `zoned.arch` | C4 model, code, data, libraries and boards | Modelo C4, código, datos, librerías y pizarras |
| `zoned.plan` | The documentation plan and what the agents ran | El plan de documentación y lo que han ejecutado los agentes |
| `zoned.quality` | Is the documentation working? KPIs and CI | ¿Funciona la documentación? KPIs y CI |
| `zoned.review` | Pages and answers waiting for a person | Páginas y respuestas que esperan a una persona |
| `view.pages` / `view.wikis` | Pages / Wikis | Páginas / Wikis |
| `view.c4` / `view.code` / `view.data` | C4 model / Code graph / Data | Modelo C4 / Grafo de código / Datos |
| `view.libs` / `view.boards` | Libraries / Boards | Librerías / Pizarras |
| `view.pipeline` / `view.kpis` / `view.ci` / `view.review` | Pipeline / KPIs / CI / Review queue | Pipeline / KPIs / CI / Cola de revisión |
| `viewd.<id>` | one line each, what the view shows (reuse the current `secd.*` / React lead wording) | idem |
| `home.eyebrow` | {project} · {n} repos | {project} · {n} repos |
| `home.title` / `home.eco` | Ask anything about the project. / I answer with the page it comes from. | Pregunta lo que sea del proyecto. / Te contesto con la página de la que sale. |
| `home.askPh` | Where is an appointment date checked? | ¿Dónde se valida la fecha de una cita? |
| `home.state` / `home.stateSub` | State / from the docs index | Estado / según el índice de la doc |
| `home.zones` | Explore | Explora |
| `kpi.confirmed` / `kpi.reconfirm` / `kpi.drafts` / `kpi.feedback` | Confirmed / To reconfirm / Drafts / Pending feedback | Confirmadas / Por reconfirmar / Borradores / Feedback pendiente |
| `zonesGroup` | Go to | Ir a |

- [ ] **Step 10: CSS** in `app.css`: `.crumbs` (one line, `overflow: hidden`, `text-overflow: ellipsis` on the last
crumb, dim separators), `.wordmark` (`--font-impact` 700, 1.35rem), hero ask input as a pill on
`--color-canvas-elevated`, `.kpi`/`.tile` grids collapsing to one column under 640px, no horizontal scroll at 375px.

- [ ] **Step 11: Run** `npm test` and `uv run pytest tests/test_portal_app.py tests/test_portal_data.py -q` → PASS.

- [ ] **Step 12: End to end in the sandbox** (rebuild, `up --foreground` running): Home (live and with an empty
`cam-docs` after `reset` + `init`), each zone cover, a docs page, a wiki page, C4, ⌘K "libr" → Libraries, both
themes, `es`/`en`, 375 px wide. Then `uv run scripts/sandbox.py cli portal` and serve `.camarones/.cache/site` of the
sandbox statically (`python -m http.server` from that folder) to check the static mode: no Plan/Quality, the hero box
searches, `#/pipeline` lands on Home. Browser console: no errors.

- [ ] **Step 13: Commit**

```bash
git add .camarones/portal/app/index.html .camarones/portal/app/public/legacy/app.js .camarones/portal/app/public/legacy/core.js .camarones/portal/app/public/legacy/app.css .camarones/portal/app-build tests/test_portal_app.py
git commit -m "feat(portal): ask-first Home, zone covers and breadcrumbs replace the tab bar"
```

---

### Task 7: Version, README and tutorial

**Files:**
- Modify: `.camarones/lib/common.py` (`VERSIONS["kit"]`: `4.41.3` → `4.42.0`)
- Modify: `README.md` (badge `4.41.3` → `4.42.0`, portal description)
- Modify: `.camarones/lib/tutorial.py` (portal page, es + en), regenerate `.camarones/TUTORIAL.md`
- Modify: `.camarones/templates/docs/guides/tutorial.md`, `.camarones/templates/docs/i18n/es/guides/tutorial.md`
  (§5 Portal: "Tabs: …" sentence)

- [ ] **Step 1: Bump** the version and badge (alt text too: `Versión 4.42.0`).

- [ ] **Step 2: Rewrite the portal descriptions** (README, `tutorial.py` page «El portal: la documentación como web»
and its `en` twin, both template guides): Home asks first and shows the project state; five zones (Docs,
Architecture, Plan, Quality, Review) reached from Home tiles, breadcrumbs and ⌘K (which now also jumps to zones and
views); same two modes; the old addresses still work. Remove every mention of "tabs"/"pestañas" as navigation
(`grep -n -i "pestaña\|tab" ` over those files and fix the portal ones only).

- [ ] **Step 3: Regenerate** from `.camarones/`:
`uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())"`

- [ ] **Step 4: Full suite**

Run: `uv run pytest -q` → all pass (includes `test_wizard.py` TUTORIAL check). In `APP`: `npm test` → all pass;
`npm run build` → `git status --porcelain .camarones/portal/app-build` empty after staging (CI check).

- [ ] **Step 5: Commit** (body: "Projects created before 4.42 keep their copy of the command guide
(guides/tutorial.md); the portal itself updates with the kit.")

```bash
git add .camarones/lib/common.py README.md .camarones/lib/tutorial.py .camarones/TUTORIAL.md .camarones/templates/docs/guides/tutorial.md .camarones/templates/docs/i18n/es/guides/tutorial.md
git commit -m "docs(portal): Home, zones and the new look in README and tutorial; kit 4.42.0"
```
