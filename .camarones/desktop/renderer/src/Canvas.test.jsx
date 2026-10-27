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

test('a terminal that ended can be folded, one that runs cannot, and both can be maximised', () => {
  const fu = { runner: 'claude', started: 0, ended: null, outcome: null, cost: 0, rows: [] }
  const running = html(<TermNode data={{ unit, fu, now: 0, ...on }} />)
  const ended = html(<TermNode data={{ unit, fu: { ...fu, ended: 5000, outcome: 'ok' }, now: 9e9, ...on }} />)
  expect(running).not.toContain('Plegar')
  expect(ended).toContain('Plegar')
  expect(ended).toContain('hecha')
  for (const out of [running, ended]) expect(out).toContain('aria-label="Maximizar"')
})

test("the clock stops at the unit's end and never runs backwards", () => {
  const done = { runner: 'claude', started: 0, ended: 60000, outcome: 'ok', cost: 0, rows: [] }
  expect(html(<TermNode data={{ unit, fu: done, now: 9e9, ...on }} />)).toContain('1 min')
  expect(html(<TermNode data={{ unit, fu: { ...done, started: 5000, ended: null }, now: 1000, ...on }} />)).toContain('0 s')
})
