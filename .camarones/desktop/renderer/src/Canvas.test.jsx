import { readFileSync } from 'node:fs'
import { ReactFlowProvider } from '@xyflow/react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import Canvas, { TermNode, UnitNode } from './sections/Canvas.jsx'
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
  expect(out).toMatch(/role="log"[^>]*class="[^"]*\bnokey\b/)
  expect(out).toMatch(/role="log"[^>]*class="[^"]*\bnopan\b/)          // a drag in it selects text, not pans
})

// React drops keys from what it renders, so the source says it: a row's key is its seq, never its index.
test('rows are keyed by their seq, so a row dropped by the cap does not rewrite the ones after it', () => {
  const src = readFileSync(new URL('./sections/Canvas.jsx', import.meta.url), 'utf-8')
  expect(src).toMatch(/rows\.map\(\(r\) => <div key=\{r\.seq\}/)
  expect(src).not.toMatch(/key=\{i\}/)
})

test('a unit with no event yet says it waits for the agent', () => {
  const out = html(<TermNode data={{ unit, fu: { runner: 'claude', started: 0, ended: null, outcome: null, cost: 0, rows: [] }, now: 125000, ...on }} />)
  expect(out).toContain('Esperando al agente…')
  expect(out).toContain('2 min')
})

test('a unit whose agent ended without finishing it is not called done: it says where the plan has it', () => {
  const ok = (status) => ({ runner: 'claude', started: 0, ended: 16000, outcome: 'ok', status, cost: 0.05, rows: [{ kind: 'log', text: 'x' }] })
  const head = (u, fu) => html(<TermNode data={{ unit: u, fu, now: 9e9, ...on }} />).split('role="log"')[0]
  expect(head({ ...unit, status: 'done' }, ok('done'))).toContain('hecha')
  const doing = head({ ...unit, status: 'doing', paused: true }, ok('doing'))
  expect(doing).not.toContain('hecha')
  expect(doing).toContain('en pausa')
  const todo = head({ ...unit, status: 'todo', ready: true }, ok('todo'))
  expect(todo).not.toContain('hecha')
  expect(todo).toContain('por hacer')
  expect(head({ ...unit, status: 'blocked' }, ok('blocked'))).toContain('bloqueada')
  expect(head({ ...unit, status: 'doing', awaiting: true }, ok('doing'))).toContain('espera tu aprobación')
})

test('only a running unit waits for its agent: one that ended with no line says nothing more', () => {
  const failed = { runner: 'claude', started: 0, ended: 1000, outcome: 'failed', cost: 0, rows: [] }
  expect(html(<TermNode data={{ unit, fu: failed, now: 9e9, ...on }} />)).not.toContain('Esperando al agente')
  const stale = { runner: 'claude', started: 0, ended: null, outcome: null, cost: 0, rows: [] }
  expect(html(<TermNode data={{ unit, fu: stale, now: 9e9, finished: true, ...on }} />)).not.toContain('Esperando al agente')
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

test('a terminal folds only when it was opened by hand and its agent is done; it can always be maximised', () => {
  const fu = { runner: 'claude', started: 0, ended: null, outcome: null, cost: 0, rows: [] }
  const done = { ...fu, ended: 5000, outcome: 'ok', status: 'done' }
  const term = (f, extra) => html(<TermNode data={{ unit, fu: f, now: 9e9, ...on, ...extra }} />)
  expect(term(done, { viewed: false })).not.toContain('Plegar')
  expect(term(done)).not.toContain('Plegar')
  expect(term(fu, { viewed: true })).not.toContain('Plegar')
  expect(term(done, { viewed: true })).toContain('Plegar')
  expect(term(done, { viewed: true })).toContain('hecha')
  for (const out of [term(fu), term(done)]) expect(out).toContain('aria-label="Maximizar"')
})

test('a run that finished without closing a unit no longer calls it running', () => {
  const fu = { runner: 'claude', started: 0, ended: null, outcome: null, cost: 0, rows: [] }
  expect(html(<TermNode data={{ unit, fu, now: 1000, ...on }} />)).toContain('en marcha')
  expect(html(<TermNode data={{ unit, fu, now: 1000, finished: true, ...on }} />)).not.toContain('en marcha')
  expect(html(<TermNode data={{ unit, fu, now: 1000, finished: true, viewed: true, ...on }} />)).toContain('Plegar')
})

// A stopped autopilot leaves its unit with no end of its own: the header says where the plan has it, not nothing.
test('a unit cut off by a run that is over says where the plan has it', () => {
  const fu = { runner: 'claude', started: 0, ended: null, outcome: null, cost: 0, rows: [{ kind: 'read', text: 'Read a.md' }] }
  const head = (u) => html(<TermNode data={{ unit: u, fu, now: 1000, finished: true, ...on }} />).split('role="log"')[0]
  expect(head({ ...unit, status: 'todo', ready: true })).toContain('por hacer')
  expect(head({ ...unit, status: 'doing', paused: true })).toContain('en pausa')
  const late = html(<TermNode data={{ unit, fu: { ...fu, last: 90000 }, now: 9e9, finished: true, ...on }} />)
  expect(late).toContain('1 min')                       // until its last event, not until whenever the page looks
})

test('a unit that is done tells how long it took and what it cost', () => {
  const fu = { runner: 'claude', started: 0, ended: 120000, outcome: 'ok', cost: 0.31, rows: [{ kind: 'log', text: 'hecho' }] }
  const out = html(<UnitNode data={{ unit: { ...unit, status: 'done' }, fu, now: 9e9, ...on }} />)
  expect(out).toContain('2 min')
  expect(out).toContain('$0.31')
  expect(html(<UnitNode data={{ unit, fu: { ...fu, ended: null }, now: 9e9, ...on }} />)).not.toContain('$0.31')
})

test("the clock stops at the unit's end and never runs backwards", () => {
  const done = { runner: 'claude', started: 0, ended: 60000, outcome: 'ok', cost: 0, rows: [] }
  expect(html(<TermNode data={{ unit, fu: done, now: 9e9, ...on }} />)).toContain('1 min')
  expect(html(<TermNode data={{ unit, fu: { ...done, started: 5000, ended: null }, now: 1000, ...on }} />)).toContain('0 s')
})

// The container: the toolbar says what runs (the Plan's own Run card keeps Stop) and offers Fit and Re-layout.
const srv = { stream: () => new Promise(() => {}) }
const units = [unit, { id: 'review', title: 'Revisar', status: 'todo', runner: 'agent', phase: 3, deps: ['explain:api'] }]
const live = () => ({ run: 'r-1', started: new Date(Date.now() - 90000).toISOString(), finished: false, units: 2, done: 1, failed: 0, seconds: 90, cost_usd: 1.2 })
const canvas = (props) => renderToStaticMarkup(<Canvas srv={srv} units={units} run={live()} pilot={null} onOpen={() => {}} {...props} />)

test('the toolbar says what the autopilot or a run is doing, and offers Fit and Re-layout', () => {
  const out = canvas({ pilot: { id: 'j-1' } })
  expect(out).toContain('Piloto automático · 1/2 · 1 min · $1.20')
  expect(out).toMatch(/<button[^>]*>Encajar<\/button>/)
  expect(out).toMatch(/<button[^>]*>Reordenar<\/button>/)
  expect(canvas()).toContain('Ejecución · 1/2')
})

test('with no run live, the toolbar says nothing is running', () => {
  expect(canvas({ run: { ...live(), finished: true } })).toContain('Nada en marcha')
  expect(canvas({ run: null })).toContain('Nada en marcha')
})

test('the canvas speaks English', () => {
  setLang('en')
  const out = canvas({ pilot: { id: 'j-1' } })
  expect(out).toContain('Autopilot · 1/2')
  expect(out).toContain('>Fit<')
  expect(out).toContain('>Re-layout<')
})

test('a paused unit says so and offers to continue it', () => {
  const out = html(<UnitNode data={{ unit: { ...unit, status: 'doing', paused: true }, now: 0, canStart: true, onSession() {}, ...on }} />)
  expect(out).toContain('En pausa: su sesión se cerró')
  expect(out).toMatch(/<button[^>]*>Seguir<\/button>/)
})

// A stopped autopilot leaves its unit paused with the run's log: both buttons fit beside the note, the log's as a glyph.
test("a paused unit a run worked on still offers the run's terminal", () => {
  const fu = { runner: 'claude', started: 0, ended: null, outcome: null, cost: 0, rows: [{ kind: 'read', text: 'Read a.md' }] }
  const out = html(<UnitNode data={{ unit: { ...unit, status: 'doing', paused: true }, fu, now: 0, canStart: false, onSession() {}, ...on }} />)
  expect(out).toMatch(/<button[^>]*disabled=""[^>]*>Seguir<\/button>/)
  expect(out).toMatch(/<button[^>]*aria-label="Ver terminal"[^>]*>&gt;_<\/button>/)
})

const atWork = { runner: 'claude', started: 0, ended: null, outcome: null, cost: 0, rows: [], session: 's-1' }
const takes = { ...on, canTake: true, canStart: true, onTake() {}, onStop() {} }

test("the autopilot's running unit can be stopped or taken, on no other run", () => {
  const out = html(<TermNode data={{ unit, fu: atWork, now: 0, ...takes }} />)
  expect(out).toContain('Parar')
  expect(out).toContain('Tomar el control')
  const parallel = html(<TermNode data={{ unit, fu: atWork, now: 0, ...on, canTake: false, canStart: true }} />)
  expect(parallel).not.toContain('Tomar el control')
  expect(parallel).not.toContain('Parar')
})

test('a unit that is not running has nothing to stop or take', () => {
  const ended = { ...atWork, ended: 1000, outcome: 'ok', status: 'done' }
  expect(html(<TermNode data={{ unit, fu: ended, now: 2000, ...takes }} />)).not.toContain('Tomar el control')
  expect(html(<TermNode data={{ unit, fu: atWork, now: 2000, finished: true, ...takes }} />)).not.toContain('Tomar el control')
})

test('taking a unit shows it is under way, and only one click goes', () => {
  const out = html(<TermNode data={{ unit, fu: atWork, now: 0, ...takes, taking: true }} />)
  expect(out).toContain('Tomando el control')
  expect(out).toMatch(/<button[^>]*disabled[^>]*>Tomando el control/)
})

test('with no agent installed a unit cannot be taken', () => {
  const out = html(<TermNode data={{ unit, fu: atWork, now: 0, ...takes, canStart: false }} />)
  expect(out).toMatch(/<button[^>]*disabled[^>]*>Tomar el control/)
})

test('a runner with no conversation says a new session opens without it', () => {
  expect(html(<TermNode data={{ unit, fu: atWork, now: 0, ...takes }} />)).not.toContain('sin esta conversación')
  expect(html(<TermNode data={{ unit, fu: { ...atWork, session: null }, now: 0, ...takes }} />)).toContain('sin esta conversación')
})

test('a handed unit says it is with you, and is no error', () => {
  const fu = { ...atWork, ended: 1000, outcome: 'handed', status: 'doing' }
  const out = html(<TermNode data={{ unit, fu, now: 2000, ...takes }} />)
  expect(out).toContain('contigo')
  expect(out).toContain('tone-running')
})

test('a failed unit can be opened with you', () => {
  const fu = { ...atWork, ended: 1000, outcome: 'failed' }
  const out = html(<TermNode data={{ unit, fu, now: 2000, ...on, canStart: true, onSession() {} }} />)
  expect(out).toContain('Abrir contigo')
  expect(html(<TermNode data={{ unit, fu, now: 2000, ...on, canStart: false, onSession() {} }} />)).toMatch(/<button[^>]*disabled[^>]*>Abrir contigo/)
})

test('the buttons of a handoff read in English too', () => {
  setLang('en')
  const out = html(<TermNode data={{ unit, fu: atWork, now: 0, ...takes }} />)
  expect(out).toContain('Take control')
  expect(out).toContain('>Stop<')
})

// Nothing here has a layout (the tests run without a DOM), so the source and the stylesheet say it.
const source = () => readFileSync(new URL('./sections/Canvas.jsx', import.meta.url), 'utf-8')
const styles = () => readFileSync(new URL('./app.css', import.meta.url), 'utf-8')

test('the wheel scrolls the page, so the canvas never traps it; a pinch or Ctrl + wheel still zooms', () => {
  expect(source()).toMatch(/zoomOnScroll=\{false\}/)
  expect(source()).toMatch(/preventScrolling=\{false\}/)
  expect(source()).not.toMatch(/zoomOnPinch=\{false\}/)
})

test('keys only go to a terminal the page has brought into view, near enough to read', () => {
  expect(source()).toMatch(/root\.current\.scrollIntoView\(\{ block: 'nearest' \}\)\s+reveal\(n, true\)\s+terms\.focus\(term\.id\)/)
})

test('maximised takes the whole main pane, above the jobs bar, wherever the page is scrolled', () => {
  expect(styles()).toMatch(/\.dk-main \{[^}]*anchor-name: --dk-main/)
  expect(styles()).toMatch(/\.dk-term-max \{[^}]*position: fixed; position-anchor: --dk-main;/)
  expect(styles()).toMatch(/\.dk:has\(\.dk-term-max\) \.dk-main \{[^}]*overflow: hidden/)
})
