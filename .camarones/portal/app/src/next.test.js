import { expect, test } from 'vitest'
import { pickNext } from './next.js'

const u = (id, status, available = true, runner = 'agent') => ({ id, status, available, runner })

test('next unit is the first available', () => {
  expect(pickNext([u('setup', 'done', false), u('discovery:api', 'todo'), u('discovery:web', 'todo')]).id).toBe('discovery:api')
})

test('the unit in progress comes first, even after a todo', () => {
  expect(pickNext([u('a', 'todo'), u('b', 'doing')]).id).toBe('b')
})

test('units that are not available are skipped, and a blocked one only when nothing else is left', () => {
  expect(pickNext([u('a', 'todo', false), u('b', 'blocked'), u('c', 'todo')]).id).toBe('c')
  expect(pickNext([u('a', 'todo', false), u('b', 'blocked')]).id).toBe('b')
})

test('a finished plan has no next unit', () => {
  expect(pickNext([u('a', 'done', false), u('b', 'dropped', false)])).toBeNull()
  expect(pickNext([])).toBeNull()
  expect(pickNext(undefined)).toBeNull()
})
