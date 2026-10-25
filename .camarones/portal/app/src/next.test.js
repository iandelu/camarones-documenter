import { expect, test } from 'vitest'
import { isEmptyProject, pickNext } from './next.js'

const u = (id, status, available = true, runner = 'agent') => ({ id, status, available, runner })

test('next unit is the first available', () => {
  expect(pickNext([u('setup', 'done', false), u('discovery:api', 'todo'), u('discovery:web', 'todo')]).id).toBe('discovery:api')
})

test('an agent unit comes before a wizard one when none is in progress', () => {
  expect(pickNext([u('setup', 'todo', true, 'wizard'), u('discovery:api', 'todo'), u('b', 'todo')]).id).toBe('discovery:api')
  expect(pickNext([u('setup', 'todo', true, 'wizard'), u('portal', 'todo', true, 'wizard')]).id).toBe('setup')
  expect(pickNext([u('setup', 'todo', true, 'wizard'), u('b', 'doing', true, 'wizard'), u('c', 'todo')]).id).toBe('b')
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

test('a project with only the kit guides and interview notes has no docs yet', () => {
  const tree = (docs, views = []) => ({ docs, views, kitGuides: ['guides/tutorial.md'] })
  expect(isEmptyProject(tree([{ path: 'guides/tutorial.md', space: 'docs' }, { path: 'interview/a.md', space: 'notes', type: 'interview' }]))).toBe(true)
  expect(isEmptyProject(tree([{ path: 'x.md', space: 'docs', type: 'interview' }]))).toBe(true)
  expect(isEmptyProject(tree([{ path: 'overview/index.md', space: 'docs', type: 'doc' }]))).toBe(false)
  expect(isEmptyProject(tree([], [{ id: 'system' }]))).toBe(false)
})
