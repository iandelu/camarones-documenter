import { expect, test } from 'vitest'
import { changedRepos, FILTERS, filterQueue, queueCounts } from './review.js'

const queue = [
  { path: 'domain/visits.md', title: 'Visits', trust: 'draft' },
  { path: 'domain/pets.md', title: 'Pets', trust: 'draft' },
  { path: 'architecture/containers.md', title: 'Containers', trust: 'needs-reconfirm' },
]

test('filters: everything, the AI drafts, the pages whose code changed', () => {
  expect(FILTERS).toEqual(['all', 'draft', 'needs-reconfirm'])
  expect(filterQueue(queue, 'all')).toHaveLength(3)
  expect(filterQueue(queue, 'draft').map((r) => r.path)).toEqual(['domain/visits.md', 'domain/pets.md'])
  expect(filterQueue(queue, 'needs-reconfirm').map((r) => r.title)).toEqual(['Containers'])
})

test('counts per filter', () => {
  expect(queueCounts(queue)).toEqual({ all: 3, draft: 2, 'needs-reconfirm': 1 })
  expect(queueCounts([])).toEqual({ all: 0, draft: 0, 'needs-reconfirm': 0 })
})

test('repos whose code moved since they were documented, with their file count', () => {
  const changes = { api: { status: 'up-to-date' }, web: { status: 'changed', files: ['a', 'b'] }, ops: { status: 'never-documented' } }
  expect(changedRepos(changes)).toEqual([{ repo: 'web', status: 'changed', files: 2 }, { repo: 'ops', status: 'never-documented', files: 0 }])
})
