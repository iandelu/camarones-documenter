import { expect, test } from 'vitest'
import { acceptBlock, addHit, counts, FILTERS, filterRows, nextPart, presentKey, route, STEPS, stepper } from './adr.js'
import { setLang, t } from './i18n.js'

const states = (phase, mode) => stepper(phase, mode).map((s) => s.state)

test('routes inside the section', () => {
  expect(route('#/decisions')).toEqual({ view: 'list' })
  expect(route('#/decisions/new')).toEqual({ view: 'new' })
  expect(route('#/decisions/candidates')).toEqual({ view: 'candidates' })
  expect(route('#/decisions/0012')).toEqual({ view: 'adr', id: '0012' })
  expect(route('#/decisions/x')).toEqual({ view: 'list' })
})

test('a route tolerates a trailing slash, a query and an empty hash', () => {
  expect(route('#/decisions/0012/')).toEqual({ view: 'adr', id: '0012' })
  expect(route('#/decisions/new?from=candidates')).toEqual({ view: 'new' })
  expect(route('#/decisions/12')).toEqual({ view: 'list' })
  expect(route('#/decisions/0012/extra')).toEqual({ view: 'list' })
  expect(route('')).toEqual({ view: 'list' })
  expect(route(undefined)).toEqual({ view: 'list' })
})

const rows = [{ id: '0002', title: 'Sesión en Redis', chip: 'review', repos: ['api'] },
              { id: '0001', title: 'JPA', chip: 'accepted', repos: ['vets'] }]

test('filters count and match accents', () => {
  expect(FILTERS).toEqual(['all', 'running', 'review', 'accepted', 'superseded'])
  expect(counts(rows)).toEqual({ all: 2, running: 0, review: 1, accepted: 1, superseded: 0 })
  expect(filterRows(rows, 'all', 'sesion').map((r) => r.id)).toEqual(['0002'])
  expect(filterRows(rows, 'accepted', '').map((r) => r.id)).toEqual(['0001'])
})

test('the query matches the id and the repos, case aside, and the filter narrows it', () => {
  expect(filterRows(rows, 'all', '0001').map((r) => r.id)).toEqual(['0001'])
  expect(filterRows(rows, 'all', 'VETS').map((r) => r.id)).toEqual(['0001'])
  expect(filterRows(rows, 'review', 'jpa')).toEqual([])
  expect(filterRows(rows, 'all', '  ').map((r) => r.id)).toEqual(['0002', '0001'])
})

test('a row a hand-edited file left half empty still counts and filters', () => {
  const odd = [{ id: '0003' }, { id: '0004', title: null, chip: 'rejected', repos: null }]
  expect(counts(odd)).toEqual({ all: 2, running: 0, review: 0, accepted: 0, superseded: 0 })
  expect(filterRows(odd, 'all', '0004').map((r) => r.id)).toEqual(['0004'])
  expect(counts(undefined).all).toBe(0)
})

test('the stepper walks the phase', () => {
  expect(STEPS).toEqual(['problem', 'evidence', 'research', 'synthesis', 'review', 'accepted'])
  expect(stepper('problem').map((s) => s.id)).toEqual(STEPS)
  expect(states('problem')).toEqual(['current', 'todo', 'todo', 'todo', 'todo', 'todo'])
  expect(states('evidence')).toEqual(['done', 'current', 'todo', 'todo', 'todo', 'todo'])
  expect(states('review')).toEqual(['done', 'done', 'done', 'done', 'current', 'todo'])
  expect(states('accepted')).toEqual(['done', 'done', 'done', 'done', 'done', 'current'])
})

test('a hand-written ADR skips the AI steps', () => {
  expect(stepper('review', 'manual').map((s) => s.state)).toEqual(['done', 'done', 'skipped', 'skipped', 'current', 'todo'])
  expect(states('problem', 'manual')).toEqual(['current', 'todo', 'skipped', 'skipped', 'todo', 'todo'])
})

test('the stepper stays calm with a phase it does not know', () => {
  expect(states(undefined)).toEqual(['todo', 'todo', 'todo', 'todo', 'todo', 'todo'])
  expect(stepper('nonsense').every((s) => s.state === 'todo')).toBe(true)
})

test('a rejected ADR ends on a Rejected step, never on Accepted', () => {
  const ids = (phase, mode) => stepper(phase, mode).map((s) => s.id)
  expect(ids('rejected')).toEqual(['problem', 'evidence', 'research', 'synthesis', 'review', 'rejected'])
  expect(states('rejected')).toEqual(['done', 'done', 'done', 'done', 'done', 'current'])
  expect(ids('rejected', 'manual')).toEqual(['problem', 'evidence', 'research', 'synthesis', 'review', 'rejected'])
  expect(states('rejected', 'manual')).toEqual(['done', 'done', 'skipped', 'skipped', 'done', 'current'])
  expect(ids('accepted')).toEqual(STEPS)
})

const parts = [{ id: 'context', status: 'pending' }, { id: 'drivers', status: 'approved' }, { id: 'options', status: 'pending' }]

test('next and previous part clamp at both ends', () => {
  expect(nextPart(parts, 'context', 1)).toBe('drivers')
  expect(nextPart(parts, 'drivers', -1)).toBe('context')
  expect(nextPart(parts, 'options', 1)).toBe('options')
  expect(nextPart(parts, 'context', -1)).toBe('context')
})

test('a part that is not in the list falls back to the first, and no parts keep the current one', () => {
  expect(nextPart(parts, 'gone', 1)).toBe('context')
  expect(nextPart(parts, undefined, -1)).toBe('context')
  expect(nextPart([], 'context', 1)).toBe('context')
})

test('presentation keys, never while typing', () => {
  expect(presentKey('ArrowRight', { typing: false, options: 3 })).toEqual({ do: 'next' })
  expect(presentKey('2', { typing: false, options: 3 })).toEqual({ do: 'choose', n: 2 })
  expect(presentKey('4', { typing: false, options: 3 })).toBeNull()
  expect(presentKey('ArrowRight', { typing: true, options: 3 })).toBeNull()
})

test('every presentation key does one thing', () => {
  const ctx = { typing: false, options: 9 }
  expect(presentKey('ArrowLeft', ctx)).toEqual({ do: 'prev' })
  expect(presentKey('e', ctx)).toEqual({ do: 'edit' })
  expect(presentKey('d', ctx)).toEqual({ do: 'defer' })
  expect(presentKey('a', ctx)).toEqual({ do: 'accept' })
  expect(presentKey('Escape', ctx)).toEqual({ do: 'exit' })
  expect(presentKey('p', ctx)).toEqual({ do: 'toggle' })
  expect(presentKey('9', ctx)).toEqual({ do: 'choose', n: 9 })
  for (const k of ['0', 'x', 'E', 'Enter', ' ', '']) expect(presentKey(k, ctx), k).toBeNull()
  for (const k of ['ArrowLeft', 'e', 'd', 'a', 'Escape', 'p', '1']) expect(presentKey(k, { ...ctx, typing: true }), k).toBeNull()
})

test('a number key chooses only an option that exists', () => {
  expect(presentKey('1', { typing: false, options: 1 })).toEqual({ do: 'choose', n: 1 })
  expect(presentKey('2', { typing: false, options: 1 })).toBeNull()
  expect(presentKey('1', { typing: false, options: 0 })).toBeNull()
  expect(presentKey('1', { typing: false })).toBeNull()
})

test('a hit adds its files once, sorted', () => {
  expect(addHit(['api:b.java'], { kind: 'group', touch: 'api:orders', files: ['api:c.java', 'api:b.java'] }))
    .toEqual(['api:b.java', 'api:c.java'])
  expect(addHit([], { kind: 'page', touch: 'cam-docs:docs/orders.md' })).toEqual(['cam-docs:docs/orders.md'])
})

test('a file hit adds its touch, a group with no files adds nothing, and the list is never mutated', () => {
  const current = ['b', 'a']
  expect(addHit(current, { kind: 'file', touch: 'api:A.java' })).toEqual(['a', 'api:A.java', 'b'])
  expect(addHit(current, { kind: 'file', touch: 'a' })).toEqual(['a', 'b'])
  expect(addHit(current, { kind: 'group', touch: 'api:orders' })).toEqual(['a', 'b'])
  expect(addHit(undefined, { kind: 'page', touch: 'x:y' })).toEqual(['x:y'])
  expect(current).toEqual(['b', 'a'])
})

const adr = (points, decision = 'To be decided in review: see the decision points.') => ({ points, sections: { decision } })

test('accept explains why it cannot run yet', () => {
  expect(acceptBlock(adr([{ id: 'p1', deferred: true }]))).toEqual({ key: 'adr.why.deferred', point: 'P1' })
  expect(acceptBlock(adr([{ id: 'p1' }]))).toEqual({ key: 'adr.why.unchosen', point: 'P1' })
  expect(acceptBlock(adr([]))).toEqual({ key: 'adr.why.noDecision' })
  expect(acceptBlock(adr([{ id: 'p1', chosen: 'A' }]))).toBeNull()
})

test('accept names the first point in the way, deferred before unchosen as the server does', () => {
  expect(acceptBlock(adr([{ id: 'p1', chosen: 'A' }, { id: 'p2' }, { id: 'p3', deferred: true }])))
    .toEqual({ key: 'adr.why.unchosen', point: 'P2' })
  expect(acceptBlock(adr([{ id: 'p1', deferred: true, chosen: 'A' }]))).toEqual({ key: 'adr.why.deferred', point: 'P1' })
  expect(acceptBlock(adr([{ id: 'p1', other: 'Hazelcast' }]))).toBeNull()
})

test('with no points, a written Decision is enough and the placeholder is not', () => {
  expect(acceptBlock(adr([], 'We use Redis for sessions.'))).toBeNull()
  expect(acceptBlock(adr([], ''))).toEqual({ key: 'adr.why.noDecision' })
  expect(acceptBlock(adr([], '  \n '))).toEqual({ key: 'adr.why.noDecision' })
  expect(acceptBlock(adr([], '  To be decided in review: see the decision points.\n'))).toEqual({ key: 'adr.why.noDecision' })
  expect(acceptBlock({ sections: {} })).toEqual({ key: 'adr.why.noDecision' })
  expect(acceptBlock(null)).toEqual({ key: 'adr.why.noDecision' })
})

test('a why key reads as a sentence with its point in both languages', () => {
  const block = acceptBlock(adr([{ id: 'p2', deferred: true }]))
  setLang('es')
  expect(t(block.key, { point: block.point })).toBe('El punto P2 está aplazado: decídelo o quítalo')
  setLang('en')
  expect(t(block.key, { point: block.point })).toBe('Point P2 is deferred: decide it or remove it')
  setLang('es')
})
