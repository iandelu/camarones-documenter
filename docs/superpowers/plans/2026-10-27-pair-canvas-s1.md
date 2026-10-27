# Pair canvas S1 · See — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A *Canvas* view in the desktop app's Plan: the unit graph, where every unit a run (autopilot or *Ejecutar*)
is working on opens as a live, read-only terminal of what its agent does.

**Architecture:** Renderer only — the run already logs every runner event with its unit
(`runs/<run>/events.jsonl`) and the server already streams it (`GET /api/runs/<run>/events`, SSE, ids are byte
offsets). The SSE parser moves from the portal to the shared `@camaron/ui`; the app's server client gains `stream()`;
pure helpers in `desktop/renderer/src/canvas.js` turn events into rows, feeds and a layout; `sections/Canvas.jsx`
draws them with React Flow; `Plan.jsx` gets the third view.

**Tech Stack:** React 19, `@xyflow/react` 12.12.0 (already pinned in the portal), Vite, Vitest (node environment,
`renderToStaticMarkup`); Python only for the version bump and the tutorial.

**Spec:** [docs/superpowers/specs/2026-10-27-pair-canvas-design.md](../specs/2026-10-27-pair-canvas-design.md) — this
plan is its slice **S1 · See** (§7), covering §2 and §2.1 minus per-unit buttons, PTYs and the loose lane (S2–S4).

## Global Constraints

- Every user-facing string in `es` and `en`, in `desktop/renderer/src/i18n.js`; no jokes on buttons, states or errors
  (AGENTS.md §3).
- `@xyflow/react` pinned exactly `12.12.0` (no `^`), the portal's version.
- Every commit that changes source a committed build bundles also rebuilds that build: `.camarones/portal/app-build/`
  and `.camarones/desktop/renderer-build/` (`npm run build` in `portal/app` / `desktop/renderer`); CI fails on any
  commit whose build differs from its source. Run the build even when unsure; commit it when `git status` shows it
  changed.
- S1 adds no server route and no machine action; the portal stays a reader.
- `localStorage` reads and writes always inside `try/catch` (private window, blocked storage).
- Design system (`.claude/skills/cofundo-design-system/CAMARON.md`): square radii with `--consola-radio-*`, text glyphs
  only (no SVG icons), colours from theme tokens; terminal bodies dark in both themes.
- Values from the spec: compact node 200×64, terminal node 440×280; a finished node folds back after 4000 ms; the
  row glyphs `✎ ⌕ ▶ · » ✕`.
- Values this plan fixes: at most 500 rows kept per unit, 400 characters per row, 20 rows per message; column gap 60,
  row gap 24; events applied to the screen in batches every 150 ms.
- Conventional commits, no `Co-Authored-By` line; other sessions may be editing the tree: stage only your own files.
- Commands run from the repo root; renderer commands inside `( … )` so the shell's folder does not change.

## Review Focus

1. **A long autopilot** (thousands of events, replayed from offset 0 when the canvas opens): memory and rendering stay
   bounded — 500 rows per unit, batched updates. Test: Task 3 `a long run keeps the last 500 rows of a unit`.
2. **A run that starts or changes while the canvas is open** (`camaron run` from a terminal, a second autopilot): the
   canvas drops the old feed and follows the new run. Test: Task 4 `a new run, or the shown one finishing, is noticed`.
3. **The stream drops mid-run** (server restart, laptop sleep): it resumes from the last SSE id, with no duplicated
   rows. Tests: Task 2 `stream reads a run's events with the token and says where it stopped` (the id) and Task 6
   `a dropped stream resumes from the last id it read, and ends with the run` (the resume).
4. **A unit that started but has said nothing yet** (the agent thinking for minutes): its node says it waits for the
   agent and its elapsed time keeps counting. Test: Task 5 `a unit with no event yet says it waits for the agent`.
5. **Huge multi-line output** (a test run, a stack trace in a `log`): cut to 20 rows of 400 characters with a count of
   what was left out. Test: Task 3 `long output is cut: 400 characters a row, 20 rows a message`.

---

### Task 1: The SSE parser moves to `@camaron/ui` and reports the last id

**Files:**
- Create: `.camarones/ui/src/sse.js`, `.camarones/ui/src/sse.test.js`
- Modify: `.camarones/ui/src/index.js` (export), `.camarones/portal/app/src/api.js:4` (import from `@camaron/ui`)
- Delete: `.camarones/portal/app/src/sse.js`, `.camarones/portal/app/src/sse.test.js`
- Rebuild: `.camarones/portal/app-build/`

**Interfaces:**
- Produces: `parseSSE(buf: string) -> { events: object[], rest: string, id: string | null }`, exported from
  `@camaron/ui`. `id` is the `id:` of the last complete message in this piece, `null` when none. Same behaviour as today
  otherwise (keep-alive comments skipped, a partial message left in `rest`).

- [ ] **Step 1: Write the failing test** in `.camarones/ui/src/sse.test.js` (it replaces the portal's):

```js
import { expect, test } from 'vitest'
import { parseSSE } from './sse.js'

test('server-sent events are read in pieces, with the last id seen', () => {
  let r = parseSSE('id: 1\ndata: {"type":"line","text":"a"}\n\nid: 2\ndata: {"type":"li')
  expect(r.events).toEqual([{ type: 'line', text: 'a' }])
  expect(r.id).toBe('1')
  r = parseSSE(r.rest + 'ne","text":"b"}\n\n: keep-alive\n\n')
  expect(r.events).toEqual([{ type: 'line', text: 'b' }])
  expect(r.id).toBe('2')
  expect(r.rest).toBe('')
})

test('a piece with only a keep-alive has no id', () => {
  expect(parseSSE(': keep-alive\n\n')).toEqual({ events: [], rest: '', id: null })
})
```

- [ ] **Step 2: Run it to verify it fails**

Run: `(cd .camarones/portal/app && npx vitest run sse)`
Expected: FAIL — `./sse.js` not found in `ui/src`.

- [ ] **Step 3: Move `parseSSE` to `.camarones/ui/src/sse.js`** with its header comment, now also tracking the last
  `id:` line of each complete message; `export { parseSSE } from './sse.js'` in `ui/src/index.js`; in the portal's
  `api.js` import it from `@camaron/ui` and delete the portal's `sse.js` and `sse.test.js`.

- [ ] **Step 4: Run the portal suite and rebuild both apps** (both import `@camaron/ui`)

Run: `(cd .camarones/portal/app && npx vitest run && npm run build) && (cd .camarones/desktop/renderer && npm run build)`
Expected: all PASS (the two new tests included); `git status --short .camarones/portal/app-build
.camarones/desktop/renderer-build` shows what the bundles changed (the desktop one may show nothing).

- [ ] **Step 5: Commit**

```bash
git add .camarones/ui/src/sse.js .camarones/ui/src/sse.test.js .camarones/ui/src/index.js \
  .camarones/portal/app/src/api.js .camarones/portal/app/src/sse.js .camarones/portal/app/src/sse.test.js \
  .camarones/portal/app-build .camarones/desktop/renderer-build
git commit -m "refactor(ui): the SSE parser lives in @camaron/ui and says the last id it read"
```

### Task 2: The app's server client can follow a stream

**Files:**
- Modify: `.camarones/desktop/renderer/src/server.js`
- Test: `.camarones/desktop/renderer/src/server.test.js`

**Interfaces:**
- Consumes: `parseSSE` from `@camaron/ui` (Task 1).
- Produces: `server(token, fetcher).stream(name: string, onEvent: (ev: object) => void, { from?: string | number,
  signal?: AbortSignal } = {}) -> Promise<{ id: string | null }>`. GETs `../api/<name>` (plus `?from=<from>` when
  `from` is given) with the `X-Camaron-Token` header, calls `onEvent` for each message in order, resolves when the
  server ends the stream with the last id read (or the `from` it started at when nothing came). A non-OK answer throws
  an `Error` with the server's `error` message and `status`, like `call` does.

- [ ] **Step 1: Write the failing tests** (append to `server.test.js`):

```js
const sse = (...pieces) => new ReadableStream({ start(c) {
  const enc = new TextEncoder(); pieces.forEach((p) => c.enqueue(enc.encode(p))); c.close() } })

test("stream reads a run's events with the token and says where it stopped", async () => {
  const calls = []
  const fetcher = async (url, init) => { calls.push([url, init]); return new Response(sse(
    'id: 10\ndata: {"type":"unit.started","unit":"a"}\n\nid: 2', '0\ndata: {"type":"log","unit":"a","text":"hi"}\n\n')) }
  const seen = []
  const end = await server('tok', fetcher).stream('runs/r-1/events', (ev) => seen.push(ev.type), { from: 5 })
  expect(calls[0][0]).toBe('../api/runs/r-1/events?from=5')
  expect(calls[0][1].headers['X-Camaron-Token']).toBe('tok')
  expect(seen).toEqual(['unit.started', 'log'])
  expect(end).toEqual({ id: '20' })
})

test('a refused stream throws the server message', async () => {
  const fetcher = async () => new Response(JSON.stringify({ error: 'no run r-9' }), { status: 404 })
  await expect(server('t', fetcher).stream('runs/r-9/events', () => {})).rejects.toThrow('no run r-9')
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `(cd .camarones/desktop/renderer && npx vitest run src/server.test.js)`
Expected: FAIL — `stream is not a function`.

- [ ] **Step 3: Implement `stream`** in `server.js`: the body read through
  `res.body.pipeThrough(new TextDecoderStream()).getReader()`, pieces fed to `parseSSE(rest + value)`, the last
  non-null `id` kept; pass `signal` to the fetcher. Extend the file's header comment by one line about `stream`.

- [ ] **Step 4: Run them to verify they pass, and rebuild** (`server.js` is in the app's bundle)

Run: `(cd .camarones/desktop/renderer && npx vitest run src/server.test.js && npm run build)`
Expected: PASS; `renderer-build/` rebuilt.

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src/server.js .camarones/desktop/renderer/src/server.test.js \
  .camarones/desktop/renderer-build
git commit -m "feat(desktop): the server client follows a server-sent stream and says where it stopped"
```

### Task 3: Events become rows, and a run becomes a feed per unit

**Files:**
- Create: `.camarones/desktop/renderer/src/canvas.js`, `.camarones/desktop/renderer/src/canvas.test.js`

**Interfaces:**
- Consumes: run events as `lib/harness/events.py` writes them: `{v, ts, type, run?, unit?, runner?, …}` with types
  `run.started`, `run.finished`, `unit.started {runner}`, `unit.finished {outcome, status, seconds}`,
  `tool.call {name, arg}`, `file.changed {path}`, `log {text, raw?}`, `error {text}`, `result {text}`,
  `usage {in, out, cache_read, cache_write, cost_usd?}`.
- Produces (all exported from `canvas.js`):
  - `MAX_ROWS = 500`, `LINE = 400`, `LINES = 20`
  - `GLYPH = { edit: '✎', read: '⌕', run: '▶', tool: '·', log: '»', error: '✕' }`
  - `row(ev) -> Row[]`, `Row = { kind: 'edit' | 'read' | 'run' | 'tool' | 'log' | 'error', text: string }`
  - `emptyFeed(run: string | null) -> Feed`, `Feed = { run, finished: boolean, units: { [uid]: UnitFeed } }`
  - `UnitFeed = { runner: string | null, started: number /* ms */, ended: number | null, outcome: string | null,
    cost: number, rows: Row[] }`
  - `feed(f: Feed, ev) -> Feed` — pure; returns a new object when anything changed.

Row rules (spec §2.1): `tool.call` named `Edit`, `Write`, `MultiEdit`, `NotebookEdit` → `edit`; `Read`, `Glob`,
`Grep`, `LS` → `read`; `Bash` or `$` (Codex) → `run`; any other name → `tool`; text is `name` plus ` arg` when `arg`
is not null or empty. `file.changed` → `edit` with `edit <path>`. `log` → one `log` row per line of `text` (empty lines
dropped), each cut to `LINE` characters ending in `…`, at most `LINES` rows and then a last row `… +<n>` with the lines
left out. `error` → one `error` row. `usage`, `result` and the rest → no rows. Feed rules: `unit.started` creates the
unit (a second one for the same unit keeps its rows and cost, adds a `log` row `— <runner>` and clears `ended` and
`outcome`); `usage` adds `cost_usd` (absent = 0); `unit.finished` sets `ended` from `ts` and `outcome`; any other event
with a `unit` appends `row(ev)` and keeps the last `MAX_ROWS`; an event for a unit never started creates it with
`started` from its `ts`; `run.finished` sets `finished`.

- [ ] **Step 1: Write the failing tests** in `canvas.test.js`:

```js
import { expect, test } from 'vitest'
import { emptyFeed, feed, MAX_ROWS, row } from './canvas.js'

const ev = (type, f = {}) => ({ v: 1, ts: '2026-10-27T10:00:00.000Z', type, unit: 'a', ...f })

test('a tool call, an edit, a command, a message and an error each become rows', () => {
  expect(row(ev('tool.call', { name: 'Edit', arg: 'cam-docs/api.md' }))).toEqual([{ kind: 'edit', text: 'Edit cam-docs/api.md' }])
  expect(row(ev('tool.call', { name: 'Grep', arg: 'RestController' }))).toEqual([{ kind: 'read', text: 'Grep RestController' }])
  expect(row(ev('tool.call', { name: 'Bash', arg: 'rg -n x' }))).toEqual([{ kind: 'run', text: 'Bash rg -n x' }])
  expect(row(ev('tool.call', { name: '$', arg: 'npm test' }))).toEqual([{ kind: 'run', text: '$ npm test' }])
  expect(row(ev('tool.call', { name: 'camarones.search_docs', arg: null }))).toEqual([{ kind: 'tool', text: 'camarones.search_docs' }])
  expect(row(ev('file.changed', { path: 'docs/a.md' }))).toEqual([{ kind: 'edit', text: 'edit docs/a.md' }])
  expect(row(ev('log', { text: 'two\n\nlines' }))).toEqual([{ kind: 'log', text: 'two' }, { kind: 'log', text: 'lines' }])
  expect(row(ev('error', { text: 'boom' }))).toEqual([{ kind: 'error', text: 'boom' }])
  expect(row(ev('usage', { in: 1, out: 2, cost_usd: 0.1 }))).toEqual([])
  expect(row(ev('result', { text: 'done' }))).toEqual([])
})

test('long output is cut: 400 characters a row, 20 rows a message', () => {
  const r = row(ev('log', { text: Array.from({ length: 30 }, () => 'x'.repeat(500)).join('\n') }))
  expect(r).toHaveLength(21)
  expect(r[0].text).toHaveLength(400)
  expect(r[0].text.endsWith('…')).toBe(true)
  expect(r[20]).toEqual({ kind: 'log', text: '… +10' })
})

test("the feed keeps each unit's rows, cost, end and outcome", () => {
  let f = emptyFeed('r-1')
  for (const e of [ev('unit.started', { runner: 'claude' }), ev('tool.call', { name: 'Read', arg: 'a.md' }),
    ev('usage', { cost_usd: 0.12 }), ev('usage', { cost_usd: 0.1 }), ev('usage', {}),
    ev('unit.finished', { outcome: 'ok', ts: '2026-10-27T10:04:00.000Z' })]) f = feed(f, e)
  expect(f.units.a).toMatchObject({ runner: 'claude', outcome: 'ok', rows: [{ kind: 'read', text: 'Read a.md' }] })
  expect(f.units.a.cost).toBeCloseTo(0.22)
  expect(f.units.a.ended - f.units.a.started).toBe(240000)
})

test('a long run keeps the last 500 rows of a unit', () => {
  let f = feed(emptyFeed('r-1'), ev('unit.started', { runner: 'claude' }))
  for (let i = 0; i < 10000; i++) f = feed(f, ev('tool.call', { name: 'Read', arg: `f${i}` }))
  expect(f.units.a.rows).toHaveLength(MAX_ROWS)
  expect(f.units.a.rows.at(-1).text).toBe('Read f9999')
})

test('a unit started again after a usage limit keeps its rows and says which agent took over', () => {
  let f = emptyFeed('r-1')
  for (const e of [ev('unit.started', { runner: 'claude' }), ev('tool.call', { name: 'Read', arg: 'a.md' }),
    ev('unit.finished', { outcome: 'limited' }), ev('unit.started', { runner: 'codex' })]) f = feed(f, e)
  expect(f.units.a).toMatchObject({ runner: 'codex', ended: null, outcome: null })
  expect(f.units.a.rows.map((r) => r.text)).toEqual(['Read a.md', '— codex'])
})

test('an event of a unit never started still lands, and run.finished closes the feed', () => {
  let f = feed(emptyFeed('r-1'), ev('log', { unit: 'b', text: 'hola' }))
  expect(f.units.b.rows).toEqual([{ kind: 'log', text: 'hola' }])
  expect(feed(f, { v: 1, ts: '2026-10-27T10:05:00.000Z', type: 'run.finished', done: 1 }).finished).toBe(true)
})

test('the feed is pure', () => {
  const f = emptyFeed('r-1')
  const g = feed(f, ev('unit.started', { runner: 'claude' }))
  expect(g).not.toBe(f)
  expect(f.units).toEqual({})
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `(cd .camarones/desktop/renderer && npx vitest run src/canvas.test.js)`
Expected: FAIL — `./canvas.js` not found.

- [ ] **Step 3: Implement `row`, `emptyFeed`, `feed` and the constants** in `canvas.js`, with a header comment in the
  style of `plan.js` saying what the canvas is and that these helpers are pure.

- [ ] **Step 4: Run them to verify they pass**

Run: `(cd .camarones/desktop/renderer && npx vitest run src/canvas.test.js)`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src/canvas.js .camarones/desktop/renderer/src/canvas.test.js
git commit -m "feat(desktop): a run's events as rows and a feed per unit, for the plan canvas"
```

### Task 4: Which units open as terminals, where every node goes, and how the keyboard moves

**Files:**
- Modify: `.camarones/desktop/renderer/src/canvas.js`
- Test: `.camarones/desktop/renderer/src/canvas.test.js`

**Interfaces:**
- Consumes: `phases(units)` from `plan.js` (lanes by phase, sorted, dropped units left out); `Feed` (Task 3).
- Produces (exported from `canvas.js`):
  - `FOLD_MS = 4000`, `SIZE = { unit: { w: 200, h: 64 }, term: { w: 440, h: 280 } }`, `GAP = { x: 60, y: 24 }`
  - `openUnits(units, f: Feed, viewed: Set<string>, now: number) -> Set<string>` — a unit is open when its feed entry
    is running (`ended === null` and the feed not `finished`), failed (`outcome === 'failed'`), ended less than
    `FOLD_MS` ago, or in `viewed`.
  - `layout(units, open: Set<string>) -> { nodes, edges }` — node
    `{ id, type: 'term' | 'unit', position: { x, y }, width, height, data: { unit } }`; phases left to right, each
    column as wide as its widest node plus `GAP.x`, nodes stacked with `GAP.y`; edge
    `{ id: '<dep>-><id>', source: dep, target: id, animated: unit.status === 'doing' }` only between present units.
  - `place(nodes, saved: { [id]: { x: number, y: number } }) -> nodes` — a saved position with two finite numbers
    replaces the automatic one; other nodes keep theirs.
  - `neighbour(nodes, id: string, dir: 'left' | 'right' | 'up' | 'down') -> string | null` — the nearest node whose
    centre lies in that direction (smallest distance, ties to the smaller cross-axis offset).
  - `defaultView(saved: string | null, live: boolean) -> 'board' | 'phases' | 'canvas'` — a known saved view wins;
    otherwise `canvas` when something is live, else `board`.
  - `atBottom({ scrollTop, scrollHeight, clientHeight }, slack = 24) -> boolean`
  - `changedRun(shown: { run, finished } | null, latest: { run, finished } | null) -> boolean` — the portal's rule
    (`portal/app/src/board.js`): a new run id, or the shown one's `finished` changed.

- [ ] **Step 1: Write the failing tests** (append to `canvas.test.js`):

```js
import { atBottom, changedRun, defaultView, FOLD_MS, layout, neighbour, openUnits, place, SIZE } from './canvas.js'

const U = (id, phase, extra = {}) => ({ id, title: id, phase, status: 'todo', deps: [], runner: 'agent', ...extra })
const units = [U('a', 1, { status: 'done' }), U('b', 1, { status: 'done' }), U('c', 2, { status: 'doing', deps: ['a', 'b'] }),
  U('d', 2, { deps: ['a'] }), U('e', 3, { deps: ['c'] }), U('x', 3, { status: 'dropped' })]
const overlap = (p, q) => p.position.x < q.position.x + q.width && q.position.x < p.position.x + p.width &&
  p.position.y < q.position.y + q.height && q.position.y < p.position.y + p.height

test('running, failed and just-finished units open as terminals; others fold', () => {
  const f = { run: 'r', finished: false, units: {
    c: { ended: null, outcome: null }, d: { ended: 1000, outcome: 'failed' },
    a: { ended: 10_000, outcome: 'ok' }, b: { ended: 10_000 - FOLD_MS - 1, outcome: 'ok' } } }
  expect([...openUnits(units, f, new Set(), 10_000)].sort()).toEqual(['a', 'c', 'd'])
  expect(openUnits(units, f, new Set(['e']), 10_000).has('e')).toBe(true)
  expect(openUnits(units, { ...f, finished: true }, new Set(), 10_000 + FOLD_MS + 1).has('c')).toBe(false)
})

test('the layout goes by phase, sizes open nodes as terminals and never overlaps', () => {
  const { nodes, edges } = layout(units, new Set(['c']))
  const at = Object.fromEntries(nodes.map((n) => [n.id, n]))
  expect(Object.keys(at).sort()).toEqual(['a', 'b', 'c', 'd', 'e'])
  expect(at.c).toMatchObject({ type: 'term', width: SIZE.term.w, height: SIZE.term.h })
  expect(at.d).toMatchObject({ type: 'unit', width: SIZE.unit.w, height: SIZE.unit.h })
  expect(at.a.position.x).toBeLessThan(at.c.position.x)
  expect(at.e.position.x).toBeGreaterThanOrEqual(at.c.position.x + SIZE.term.w)
  for (const p of nodes) for (const q of nodes) if (p !== q) expect(overlap(p, q)).toBe(false)
  expect(edges.map((e) => e.id).sort()).toEqual(['a->c', 'a->d', 'b->c', 'c->e'])
  expect(edges.find((e) => e.id === 'a->c').animated).toBe(true)
})

test('a dragged node keeps where the person left it', () => {
  const { nodes } = layout(units, new Set())
  const placed = place(nodes, { a: { x: 900, y: 40 }, b: { x: 'no', y: 1 } })
  expect(placed.find((n) => n.id === 'a').position).toEqual({ x: 900, y: 40 })
  expect(placed.find((n) => n.id === 'b').position).toEqual(nodes.find((n) => n.id === 'b').position)
})

test('arrows move to the nearest node in that direction', () => {
  const { nodes } = layout(units, new Set())
  expect(neighbour(nodes, 'a', 'right')).toBe('c')
  expect(neighbour(nodes, 'a', 'down')).toBe('b')
  expect(neighbour(nodes, 'a', 'left')).toBe(null)
})

test('the plan opens on the canvas while something runs, unless a view was picked', () => {
  expect(defaultView(null, true)).toBe('canvas')
  expect(defaultView(null, false)).toBe('board')
  expect(defaultView('phases', true)).toBe('phases')
  expect(defaultView('nonsense', false)).toBe('board')
})

test('the log follows the end only while the person is at the bottom', () => {
  expect(atBottom({ scrollTop: 776, scrollHeight: 1000, clientHeight: 200 })).toBe(true)
  expect(atBottom({ scrollTop: 500, scrollHeight: 1000, clientHeight: 200 })).toBe(false)
})

test('a new run, or the shown one finishing, is noticed', () => {
  expect(changedRun(null, { run: 'r-2', finished: false })).toBe(true)
  expect(changedRun({ run: 'r-1', finished: false }, { run: 'r-2', finished: false })).toBe(true)
  expect(changedRun({ run: 'r-1', finished: false }, { run: 'r-1', finished: true })).toBe(true)
  expect(changedRun({ run: 'r-1', finished: false }, { run: 'r-1', finished: false })).toBe(false)
  expect(changedRun({ run: 'r-1', finished: true }, null)).toBe(false)
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `(cd .camarones/desktop/renderer && npx vitest run src/canvas.test.js)`
Expected: FAIL — the new names are not exported.

- [ ] **Step 3: Implement the seven functions and three constants** in `canvas.js` (reuse `phases` from `plan.js` for
  the columns; `neighbour` compares node centres).

- [ ] **Step 4: Run them to verify they pass**

Run: `(cd .camarones/desktop/renderer && npx vitest run src/canvas.test.js)`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src/canvas.js .camarones/desktop/renderer/src/canvas.test.js
git commit -m "feat(desktop): the plan canvas's layout, open terminals, saved places and keyboard moves"
```

### Task 5: The terminal node and the unit node

**Files:**
- Create: `.camarones/desktop/renderer/src/sections/Canvas.jsx` (the two nodes now; the container in Task 6),
  `.camarones/desktop/renderer/src/Canvas.test.jsx`
- Modify: `.camarones/desktop/renderer/src/i18n.js` (es and en, every `cv.*` key and `plan.canvas`),
  `.camarones/desktop/renderer/src/app.css`, `.camarones/desktop/renderer/package.json` and `package-lock.json`
  (`"@xyflow/react": "12.12.0"`)

**Interfaces:**
- Consumes: `GLYPH`, `UnitFeed` (Task 3); `atBottom` (Task 4); `tone` from `plan.js`; `money`, `fmtDuration` from
  `@camaron/ui`; `Handle`, `Position` from `@xyflow/react` (target on the left, source on the right, as the portal's
  `UnitNode`).
- Produces: `export function TermNode({ data })` and `export function UnitNode({ data })` — React Flow node
  components; `data = { unit, fu /* UnitFeed | undefined */, now /* ms */, onOpen(uid), onView(uid), onMax(uid) }`.

**What each piece does:**
- `UnitNode`: the board card's look (`tone(u)` colour, title, `tone.*` word, id); click → `onOpen(uid)` (the Plan's
  existing detail); when `fu` has rows, a small `t('cv.view')` button → `onView(uid)`.
- `TermNode`: header — title (button → `onOpen`), runner, state word (`cv.st.running` while `ended === null`, else
  `cv.st.<outcome>`), elapsed `fmtDuration(((fu.ended ?? now) - fu.started) / 1000)`, `money(fu.cost)`, `⤢`
  (`aria-label` `cv.max`) → `onMax(uid)`; when viewed but not running, a `t('cv.hide')` button → `onView(uid)`.
  Body — `role="log" aria-live="polite" aria-label={t('cv.log', { unit })}` with classes `nowheel nodrag` (scroll and
  select text without panning); one line per row `<span aria-hidden="true">{GLYPH[kind]}</span> {text}` with class
  `k-<kind>`; no rows → `t('cv.waiting')`. Autoscroll: follows the end while `atBottom`; when the person scrolls up it
  stops and a `t('cv.follow')` button returns to the end. Failed outcome → the node takes `tone-blocked`.
- `i18n.js` keys, es / en: `plan.canvas` Lienzo / Canvas · `cv.label` Lienzo del plan / Plan canvas · `cv.fit` Encajar /
  Fit · `cv.relayout` Reordenar / Re-layout · `cv.pilot` Piloto automático / Autopilot · `cv.run` Ejecución / Run ·
  `cv.status` `{kind} · {done}/{units} · {time} · {cost}` (both) · `cv.idle` Nada en marcha / Nothing running ·
  `cv.waiting` Esperando al agente… / Waiting for the agent… · `cv.follow` Ir al final / Jump to the end · `cv.max`
  Maximizar / Maximise · `cv.restore` Volver al lienzo / Back to the canvas · `cv.view` Ver terminal / View terminal ·
  `cv.hide` Plegar / Fold · `cv.log` Lo que hace el agente en {unit} / What the agent does in {unit} ·
  `cv.st.running` en marcha / running · `cv.st.ok` hecha / done · `cv.st.failed` falló / failed · `cv.st.limited`
  límite de uso / usage limit · `cv.st.cancelled` cancelada / cancelled · `cv.st.retry` reintentando / retrying.
- `app.css`: `.dk-canvas` (`height: calc(100vh - 18rem); min-height: 28rem`, border `--color-rule`, radius
  `--consola-radio-tarjeta`); `.dk-term` body background `var(--color-ink)` and text `var(--color-canvas)` in the
  light theme, `var(--color-canvas-elevated)` / `var(--color-ink)` under both dark selectors of `tokens.css`
  (`@media (prefers-color-scheme: dark) :root:not([data-theme="light"])` and `:root[data-theme="dark"]`); rows in
  `--font-mono` `--text-micro`; glyph colours `k-edit` aurora-amber, `k-run` aurora-cyan, `k-error` estado-mal (glyph
  only, text stays in the body colour); `.dk-term-max` fills `.dk-canvas`; the running node's pulse off under the
  existing `prefers-reduced-motion` block.

- [ ] **Step 1: Write the failing tests** in `Canvas.test.jsx`:

```jsx
import { ReactFlowProvider } from '@xyflow/react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { TermNode, UnitNode } from './sections/Canvas.jsx'
import { setLang } from './i18n.js'

afterEach(() => setLang('es'))
const html = (el) => renderToStaticMarkup(<ReactFlowProvider>{el}</ReactFlowProvider>)
const unit = { id: 'explain:api', title: 'Explicar la API', status: 'doing', runner: 'agent', phase: 2, deps: [] }
const on = { onOpen() {}, onView() {}, onMax() {} }

test("a running unit's terminal shows what its agent does, as a live log", () => {
  const fu = { runner: 'claude', started: 0, ended: null, outcome: null, cost: 0.22,
    rows: [{ kind: 'edit', text: 'Edit cam-docs/api.md' }, { kind: 'run', text: 'Bash rg -n x' }] }
  const out = html(<TermNode data={{ unit, fu, now: 240000, ...on }} />)
  for (const s of ['Explicar la API', 'claude', 'en marcha', '4 min', '$0.22', '✎', 'Edit cam-docs/api.md', '▶']) expect(out).toContain(s)
  expect(out).toMatch(/role="log"[^>]*aria-live="polite"/)
  expect(out).toMatch(/class="[^"]*nowheel[^"]*nodrag/)
})

test('a unit with no event yet says it waits for the agent', () => {
  const out = html(<TermNode data={{ unit, fu: { runner: 'claude', started: 0, ended: null, outcome: null, cost: 0, rows: [] }, now: 125000, ...on }} />)
  expect(out).toContain('Esperando al agente…')
  expect(out).toContain('2 min')
})

test('a failed unit keeps its terminal, in the blocked tone', () => {
  const out = html(<TermNode data={{ unit, fu: { runner: 'codex', started: 0, ended: 60000, outcome: 'failed', cost: 0, rows: [{ kind: 'error', text: 'boom' }] }, now: 90000, ...on }} />)
  expect(out).toContain('tone-blocked')
  expect(out).toContain('falló')
  expect(out).toContain('✕')
})

test('a unit that ran offers its terminal again; one that did not, does not', () => {
  const fu = { runner: 'claude', started: 0, ended: 1, outcome: 'ok', cost: 0, rows: [{ kind: 'log', text: 'hecho' }] }
  expect(html(<UnitNode data={{ unit: { ...unit, status: 'done' }, fu, now: 9e9, ...on }} />)).toContain('Ver terminal')
  expect(html(<UnitNode data={{ unit: { ...unit, status: 'todo', ready: true }, now: 0, ...on }} />)).not.toContain('Ver terminal')
})

test('the terminal speaks English', () => {
  setLang('en')
  const out = html(<TermNode data={{ unit, fu: { runner: 'claude', started: 0, ended: null, outcome: null, cost: 0, rows: [] }, now: 0, ...on }} />)
  expect(out).toContain('Waiting for the agent…')
  expect(out).toContain('running')
})
```

- [ ] **Step 2: Add the dependency and run the tests to verify they fail**

Run: `(cd .camarones/desktop/renderer && npm install --save-exact @xyflow/react@12.12.0 && npx vitest run src/Canvas.test.jsx)`
Expected: FAIL — `./sections/Canvas.jsx` not found.

- [ ] **Step 3: Implement `TermNode` and `UnitNode` in `Canvas.jsx`, the i18n keys and the CSS** as described above.

- [ ] **Step 4: Run the whole renderer suite and build**

Run: `(cd .camarones/desktop/renderer && npx vitest run && npm run build)`
Expected: all PASS (including `i18n.test.js`, which checks es/en key parity, and `style.test.js`); `renderer-build/`
rebuilt (the CSS is bundled even before the nodes are used).

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src/sections/Canvas.jsx .camarones/desktop/renderer/src/Canvas.test.jsx \
  .camarones/desktop/renderer/src/i18n.js .camarones/desktop/renderer/src/app.css \
  .camarones/desktop/renderer/package.json .camarones/desktop/renderer/package-lock.json \
  .camarones/desktop/renderer-build
git commit -m "feat(desktop): the canvas's terminal node, a unit's agent live, and its compact node"
```

### Task 6: The canvas follows the run, and the Plan shows it

**Files:**
- Modify: `.camarones/desktop/renderer/src/canvas.js` (`followRun`), `.camarones/desktop/renderer/src/sections/Canvas.jsx`
  (the default export), `.camarones/desktop/renderer/src/sections/Plan.jsx` (views, default view, render)
- Test: `.camarones/desktop/renderer/src/canvas.test.js`

**Interfaces:**
- Consumes: `srv.stream` (Task 2); `emptyFeed`/`feed` (Task 3); `openUnits`/`layout`/`place`/`neighbour`/
  `defaultView`/`changedRun` (Task 4); `TermNode`/`UnitNode` (Task 5); the Plan's `data.units`, `data.run`
  (`runs.summary`: `run, started, finished, units, done, failed, seconds, cost_usd`) and `pilot` (the running
  `cmd:autopilot` job).
- Produces:
  - `followRun(srv, run: string, onEvent: (ev) => void, { signal?: AbortSignal, retry = 2000, sleep }) -> Promise<void>`
    in `canvas.js` — streams `runs/<run>/events` from the start; when a stream ends before a `run.finished` event and
    the signal is not aborted, waits `retry` ms and streams again `from` the id the last one returned; resolves after
    `run.finished` or on abort. A stream that throws after the abort resolves quietly; one refused with `status` 404
    (the run's log is gone) resolves too; any other error (network, server restarting) waits `retry` and tries again
    from the last id.
  - `export default function Canvas({ srv, units, run, pilot, onOpen })` in `Canvas.jsx`.

**What each piece does:**
- `Canvas`: wraps everything in `ReactFlowProvider`. A `useRunFeed(srv, run)` hook in the same file: on
  `changedRun` it aborts the old follow, starts from `emptyFeed(run.run)` and calls `followRun`; events are buffered
  and folded into the feed every 150 ms; abort on unmount. Nodes come from
  `place(layout(units, openUnits(units, feed, viewed, now)).nodes, saved)`, each `data` completed with
  `fu: feed.units[id]`, `now`, `onOpen`, `onView` (toggles the id in a `viewed` set kept in state) and `onMax`.
  `now` ticks every second while any node is open. Positions
  saved in `localStorage['dk.canvasPos']` on drag stop and applied with `place`. ReactFlow props: `nodeTypes`
  (module-level constant `{ unit: UnitNode, term: TermNode }`), `colorMode="system"`, `fitView`, `minZoom={0.2}`,
  `nodesConnectable={false}`, `edgesFocusable={false}`, `disableKeyboardA11y` (arrows must move focus, not nodes),
  `proOptions={{ hideAttribution: true }}` (as the portal). Keyboard on the wrapper: Enter/Space on a focused
  `.react-flow__node` → `onOpen(dataset.id)`; arrows → focus `neighbour(...)`; Esc → leave the maximised node. Toolbar
  above the graph: the status line `t('cv.status', { kind: t(pilot ? 'cv.pilot' : 'cv.run'), done, units, time, cost })`
  while `run` is live, else `t('cv.idle')`; `t('cv.fit')` (`fitView` on the open nodes, all when none) and
  `t('cv.relayout')` (clears `dk.canvasPos`). The run's Stop stays in the Plan's existing *Run* card above; no
  duplicate. Maximised: an overlay `.dk-term-max` with the same `TermNode` filling the canvas, `t('cv.restore')` to
  close.
- `Plan.jsx`: `VIEWS = ['board', 'phases', 'canvas']`; the view state starts from `localStorage['dk.planView']` or
  `null`, and what shows is `defaultView(saved, active || windows)`; `pick` keeps storing the choice; the canvas
  renders in place of the board/lanes, beside the existing `Detail` when a unit is open (`onOpen={setOpen}`).

- [ ] **Step 1: Write the failing tests** (append to `canvas.test.js`):

```js
import { followRun } from './canvas.js'

test('a dropped stream resumes from the last id it read, and ends with the run', async () => {
  const calls = []
  const srv = { stream: async (name, onEvent, opts) => {
    calls.push([name, opts.from])
    if (calls.length === 1) { onEvent({ type: 'unit.started', unit: 'a' }); onEvent({ type: 'log', unit: 'a', text: 'x' }); return { id: '20' } }
    onEvent({ type: 'run.finished' }); return { id: '31' } } }
  const seen = []
  await followRun(srv, 'r-1', (ev) => seen.push(ev.type), { sleep: async () => {} })
  expect(calls).toEqual([['runs/r-1/events', undefined], ['runs/r-1/events', '20']])
  expect(seen).toEqual(['unit.started', 'log', 'run.finished'])
})

test('following stops when the canvas goes away', async () => {
  const ac = new AbortController()
  let n = 0
  const srv = { stream: async () => { n += 1; ac.abort(); return { id: '5' } } }
  await followRun(srv, 'r-1', () => {}, { signal: ac.signal, sleep: async () => {} })
  expect(n).toBe(1)
})
```

- [ ] **Step 2: Run them to verify they fail**

Run: `(cd .camarones/desktop/renderer && npx vitest run src/canvas.test.js)`
Expected: FAIL — `followRun` is not exported.

- [ ] **Step 3: Implement `followRun`, the `Canvas` container and the `Plan.jsx` changes** as described above.

- [ ] **Step 4: Run the whole renderer suite and build**

Run: `(cd .camarones/desktop/renderer && npx vitest run && npm run build)`
Expected: all PASS; `renderer-build/` rebuilt.

- [ ] **Step 5: Commit**

```bash
git add .camarones/desktop/renderer/src/canvas.js .camarones/desktop/renderer/src/canvas.test.js \
  .camarones/desktop/renderer/src/sections/Canvas.jsx .camarones/desktop/renderer/src/sections/Plan.jsx \
  .camarones/desktop/renderer-build
git commit -m "feat(desktop): the Plan's canvas — every unit a run works on, live, as a terminal"
```

### Task 7: Seen working end to end, documented, versioned

**Files:**
- Modify: `.camarones/lib/common.py` (`VERSIONS["kit"]` → the next free minor, `4.70.0` unless `main` took it),
  `README.md` (badge; the Plan row at line ~388 and the paragraph at ~513), `.camarones/lib/tutorial.py` (the Plan
  page, es and en), `.camarones/TUTORIAL.md` (regenerated), `.camarones/templates/docs/guides/tutorial.md` (the Plan
  row, ~222) and `.camarones/templates/docs/i18n/es/guides/tutorial.md` (its twin)
- Scratch (not committed): a fake `claude` in the session's scratchpad

- [ ] **Step 1: Check it in the app on the sandbox with a fake agent.** Write this executable `claude` into a scratch
  folder (it answers any arguments with a slow stream-json session and exits 0):

```python
#!/usr/bin/env python3
import json, time
def say(ev):
    print(json.dumps(ev), flush=True); time.sleep(4)
say({"type": "assistant", "message": {"content": [{"type": "text", "text": "Leo el brief del repo"}]}})
for name, inp in [("Grep", {"pattern": "RestController"}), ("Edit", {"file_path": "cam-docs/repos/api/endpoints.md"}),
                  ("Bash", {"command": "rg -n @GetMapping src/"})]:
    say({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}})
print(json.dumps({"type": "result", "result": "ok", "total_cost_usd": 0.05,
                  "usage": {"input_tokens": 1000, "output_tokens": 50}}), flush=True)
```

Run: `PATH="<scratch folder>:$PATH" uv run scripts/sandbox.py cli app` (if the sandbox has no ready agent unit,
`uv run scripts/sandbox.py reset` first and take the wizard's setup until the plan has one). In the app: Plan →
*Piloto automático* with *máximo de unidades* 1.
Expected: the Plan opens on *Lienzo*; the unit's node is a terminal that fills with `»`, `⌕`, `✎`, `▶` rows over
~16 s, elapsed time counting, `$0.05` at the end; the node folds back about 4 s after the unit ends (the autopilot then
stops, saying the unit ended without `plan done` — expected with a fake agent). Scroll up in the node: autoscroll stops
and *Ir al final* appears. ⤢ maximises, Esc returns; Tab and the arrows move between nodes, Enter opens the detail.
Switch the app to English and to the dark theme: strings and the dark terminal hold. Take a screenshot as proof.

- [ ] **Step 2: Bump the version and update the user docs** (AGENTS.md §5.1): the README's Plan row gains the *Lienzo*
  view (the unit graph; what each unit's agent does, live, in its node; maximise, re-layout, positions kept); the
  tutorial's Plan page says the same in es and en; the shipped guides' Plan row too (existing projects keep their old
  copy — say so in the commit body).

Run: `(cd .camarones && uv run python -c "from lib import tutorial; open('TUTORIAL.md','w',encoding='utf-8',newline='\n').write(tutorial.markdown())")`
Expected: `TUTORIAL.md` regenerated.

- [ ] **Step 3: Run the whole suite**

Run: `uv run pytest -n auto` and `(cd .camarones/desktop && node --test "test/*.test.cjs")`
Expected: all PASS (`test_wizard.py` included: the tutorial and `TUTORIAL.md` agree).

- [ ] **Step 4: Commit**

```bash
git add .camarones/lib/common.py README.md .camarones/lib/tutorial.py .camarones/TUTORIAL.md \
  .camarones/templates/docs/guides/tutorial.md .camarones/templates/docs/i18n/es/guides/tutorial.md
git commit -m "docs(plan): the canvas in the README and the tutorial (kit 4.70.0)

Existing projects keep their copy of the command guide; new ones get the canvas row."
```
