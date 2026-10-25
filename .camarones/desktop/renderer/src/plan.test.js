import { expect, test } from 'vitest'
import { groups, unitAction, waitsFor } from './plan.js'

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
  expect(unitAction(u('d', 'done'))).toBeNull()
  expect(unitAction(u('s', 'doing', { runner: 'wizard', type: 'answers' }))).toEqual({ kind: 'link', href: '#/interviews', label: 'next.answers' })
})
