import { afterEach, expect, test } from 'vitest'
import { setLang, t } from './i18n.js'
import { board, COLUMNS, groups, openedWith, phases, sessionLine, tone, unitAction, waitsFor } from './plan.js'

afterEach(() => setLang('es'))

const u = (id, status, more = {}) => ({ id, status, phase: 1, runner: 'agent', type: id, deps: [], ready: false, awaiting: false, ...more })

test('the units by what they ask for: approve, retry, continue, start, wait; done apart', () => {
  const units = [
    u('d', 'done'), u('w', 'todo', { deps: ['b'] }), u('r2', 'todo', { ready: true, phase: 2 }), u('r1', 'todo', { ready: true }),
    u('g', 'doing', { ready: true }), u('b', 'blocked'), u('a', 'blocked', { awaiting: true }), u('x', 'dropped'),
  ]
  const g = groups(units)
  expect(Object.fromEntries(Object.entries(g).map(([k, v]) => [k, v.map((x) => x.id)]))).toEqual({
    awaiting: ['a'], blocked: ['b'], doing: ['g'], ready: ['r1', 'r2'], waiting: ['w'], done: ['d'],
  })
})

test('a waiting unit says what it waits for', () => {
  const units = [u('a', 'done'), u('b', 'todo'), u('c', 'dropped'), u('w', 'todo', { deps: ['a', 'b', 'c'] })]
  expect(waitsFor(units[3], units)).toEqual(['b'])
})

test('each unit has the one action that moves it', () => {
  expect(unitAction(u('a', 'blocked', { awaiting: true }))).toEqual({ kind: 'approve', label: 'unit.approve' })
  expect(unitAction(u('b', 'blocked'))).toEqual({ kind: 'retry', label: 'unit.retry' })
  expect(unitAction(u('g', 'doing'))).toEqual({ kind: 'agent', mode: 'continue', label: 'unit.continue' })
  expect(unitAction(u('r', 'todo', { ready: true }))).toEqual({ kind: 'agent', mode: 'new', label: 'unit.start' })
  expect(unitAction(u('setup', 'todo', { ready: true, runner: 'wizard' }))).toEqual({ kind: 'link', href: '#/machine', label: 'next.machine' })
  expect(unitAction(u('w', 'todo'))).toBeNull()
  expect(unitAction(u('d', 'done'))).toEqual({ kind: 'redo', label: 'unit.redo' })
  expect(unitAction(u('s', 'doing', { runner: 'wizard', type: 'answers' }))).toEqual({ kind: 'link', href: '#/interviews', label: 'next.answers' })
})

test('each unit has a tone: running yellow, done green, ready white, blocked red, awaiting you, waiting dim', () => {
  expect(tone(u('g', 'doing'))).toBe('running')
  expect(tone(u('d', 'done'))).toBe('done')
  expect(tone(u('r', 'todo', { ready: true }))).toBe('ready')
  expect(tone(u('w', 'todo'))).toBe('waiting')
  expect(tone(u('b', 'blocked'))).toBe('blocked')
  expect(tone(u('a', 'blocked', { awaiting: true }))).toBe('awaiting')
  expect(tone(u('x', 'dropped'))).toBe('dropped')
})

test('the board: one column per tone a person acts on, in plan order; dropped units stay out', () => {
  const units = [u('d', 'done'), u('r2', 'todo', { ready: true, phase: 2 }), u('r1', 'todo', { ready: true }),
    u('g', 'doing'), u('a', 'blocked', { awaiting: true }), u('b', 'blocked'), u('w', 'todo'), u('x', 'dropped')]
  const cols = board(units)
  expect(cols.map((c) => c.key)).toEqual(COLUMNS)
  expect(Object.fromEntries(cols.map((c) => [c.key, c.units.map((x) => x.id)]))).toEqual({
    ready: ['r1', 'r2'], running: ['g'], attention: ['a', 'b'], waiting: ['w'], done: ['d'] })
})

test('the phases: one lane per phase with how many are done', () => {
  const units = [u('a', 'done'), u('b', 'todo', { phase: 2 }), u('c', 'done', { phase: 2 }), u('x', 'dropped', { phase: 3 })]
  expect(phases(units).map((p) => [p.phase, p.units.map((x) => x.id), p.done])).toEqual([[1, ['a'], 1], [2, ['b', 'c'], 1]])
})

test('an interview unit asks for the mode until someone chose it', () => {
  const iv = u('interview-context', 'todo', { ready: true, type: 'interview-context' })
  expect(unitAction(iv, { interviews: null })).toEqual({ kind: 'mode', label: 'iv.choose' })
  expect(unitAction(iv, { interviews: 'live' })).toEqual({ kind: 'agent', mode: 'new', label: 'unit.start' })
  expect(unitAction(u('r', 'todo', { ready: true }), { interviews: null }).kind).toBe('agent')
  expect(unitAction(iv)).toEqual({ kind: 'agent', mode: 'new', label: 'unit.start' })    // unknown: as before
})

test('a unit in progress with no window open is paused: it needs you to continue it', () => {
  const p = u('p', 'doing', { paused: true, session: { live: false, agent: 'claude' } })
  const live = u('l', 'doing', { paused: false, session: { live: true, agent: 'claude' } })
  expect(tone(p)).toBe('paused')
  expect(tone(live)).toBe('running')
  expect(Object.fromEntries(board([p, live]).map((c) => [c.key, c.units.map((x) => x.id)]))).toMatchObject({
    running: ['l'], attention: ['p'] })
  expect(unitAction(p)).toEqual({ kind: 'agent', mode: 'continue', label: 'unit.continue' })
  expect(unitAction(live)).toEqual({ kind: 'live' })                     // open already: a second window would fight it
})

test('what an open session is doing, from its agent\'s last steps', () => {
  const now = Date.parse('2026-10-26T10:05:00Z') / 1000
  const s = (activity, more = {}) => ({ live: true, agent: 'claude', activity, ...more })
  expect(sessionLine(u('p', 'doing', { paused: true, session: { live: false } }), now)).toEqual({ key: 'sess.paused' })
  expect(sessionLine(u('l', 'doing', { session: s(null) }), now)).toEqual({ key: 'sess.open' })
  expect(sessionLine(u('l', 'doing', { session: s({ state: 'waiting', tool: 'Read', text: '¿Sigo?', ts: '2026-10-26T10:04:30Z' }) }), now))
    .toEqual({ key: 'sess.waiting', text: '¿Sigo?', ts: Date.parse('2026-10-26T10:04:30Z') / 1000 })
  expect(sessionLine(u('l', 'doing', { session: s({ state: 'working', tool: 'Edit', arg: 'docs/a.md', ts: '2026-10-26T10:04:50Z' }) }), now))
    .toEqual({ key: 'sess.tool', tool: 'Edit', arg: 'docs/a.md', ts: Date.parse('2026-10-26T10:04:50Z') / 1000 })
  expect(sessionLine(u('l', 'doing', { session: s({ state: 'working', tool: 'Bash', arg: 'npm i', ts: '2026-10-26T10:01:00Z' }) }), now).key)
    .toBe('sess.stuck')                                                   // a tool call with no answer for minutes: a permission prompt?
  expect(sessionLine(u('t', 'todo'), now)).toBeNull()
})

// The model the kit routed to the unit (lib/agents.py), when the server names it, next to the agent that opened.
test('the opened note says which model the session took', () => {
  expect(t('next.opened', { agent: openedWith('Claude Code', { launched: true, model: 'opus' }) }))
    .toBe('Abierta en una terminal con Claude Code (opus).')
  setLang('en')
  expect(t('next.opened', { agent: openedWith('Codex', { model: 'o5' }) })).toBe('Opened in a terminal with Codex (o5).')
  for (const res of [{ model: null }, {}, undefined]) expect(openedWith('OpenCode', res)).toBe('OpenCode')
})
