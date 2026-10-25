import { expect, test } from 'vitest'
import { wikiTarget } from './wiki.js'

const rows = [
  { repo: 'api', pages: 2, nav: { home: 'repos/api/wiki/index.md', pages: [{ path: 'repos/api/wiki/index.md', title: 'API' },
    { path: 'repos/api/wiki/auth.md', title: 'Auth' }], backlinks: { 'repos/api/wiki/auth.md': ['repos/api/wiki/index.md'] } } },
  { repo: 'web', pages: 0 },
]

test('a wiki page: its path, the wiki reading order and the pages that link to it', () => {
  const w = wikiTarget(rows, 'api', 'wiki/auth.md')
  expect(w.path).toBe('repos/api/wiki/auth.md')
  expect(w.order).toEqual(['repos/api/wiki/index.md', 'repos/api/wiki/auth.md'])
  expect(w.backlinks).toEqual([{ path: 'repos/api/wiki/index.md', title: 'API' }])
})

test('no page asked: the wiki home; a wiki without pages or an unknown repo has none', () => {
  expect(wikiTarget(rows, 'api', '').path).toBe('repos/api/wiki/index.md')
  expect(wikiTarget(rows, 'web', '').path).toBeNull()
  expect(wikiTarget(rows, 'nope', 'x.md')).toMatchObject({ wiki: null, path: 'repos/nope/x.md', order: [] })
})

test('a linking page outside the nav is named by its file', () => {
  const odd = [{ repo: 'api', nav: { home: 'h', pages: [], backlinks: { 'repos/api/a.md': ['repos/api/deep/b.md'] } } }]
  expect(wikiTarget(odd, 'api', 'a.md').backlinks).toEqual([{ path: 'repos/api/deep/b.md', title: 'b.md' }])
})
