import { afterEach, expect, test, vi } from 'vitest'
import { docsGet, scoreSearch } from './docsApi.js'

afterEach(() => vi.unstubAllGlobals())

const answer = (routes) => vi.fn(async (url) => {
  const body = routes[url]
  return body === undefined ? { ok: false, statusText: 'Not Found', json: async () => ({}) } : { ok: true, json: async () => body }
})

test('live: GET api/<name>?<params>, the server error as it is', async () => {
  const fetch = answer({ 'api/search?q=visit&track=1': [{ path: 'a.md' }] })
  vi.stubGlobal('fetch', fetch)
  expect(await docsGet('search', { q: 'visit', track: 1 }, { static: false })).toEqual([{ path: 'a.md' }])
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, statusText: 'Bad', json: async () => ({ error: 'no such page' }) })))
  await expect(docsGet('doc', { path: 'x.md' }, { static: false })).rejects.toThrow('no such page')
})

test('live: a read carries no token (the portal token only writes the board)', async () => {
  const fetch = answer({ 'api/tree': {} })
  vi.stubGlobal('fetch', fetch)
  await docsGet('tree', {}, { static: false })
  expect(fetch.mock.calls[0]).toEqual(['api/tree'])
})

test('export: a page in the reader language, else the English one marked as missing', async () => {
  const en = { path: 'a.md', exists: true, raw: '# A' }
  vi.stubGlobal('fetch', answer({ 'api/doc/es/a.md.json': { ...en, raw: '# A es' }, 'api/doc/_/a.md.json': en, 'api/doc/_/b.md.json': en }))
  expect((await docsGet('doc', { path: 'a.md', lang: 'es' }, { static: true })).raw).toBe('# A es')
  expect(await docsGet('doc', { path: 'b.md', lang: 'es' }, { static: true })).toEqual({ ...en, lang: 'es', exists: false, raw: '' })
  expect(await docsGet('doc', { path: 'b.md' }, { static: true })).toEqual(en)
  await expect(docsGet('doc', { path: 'c.md' }, { static: true })).rejects.toThrow('unknown page c.md')
})

test('export: the rest are json files; the code map by repo', async () => {
  vi.stubGlobal('fetch', answer({ 'api/tree.json': { docs: [] }, 'api/codemap/my%20repo.json': { nodes: [] } }))
  expect(await docsGet('tree', {}, { static: true })).toEqual({ docs: [] })
  expect(await docsGet('codemap', { repo: 'my repo' }, { static: true })).toEqual({ nodes: [] })
})

test('the export search scores by term counts, a path hit weighs 5, in the reader language when there is one', () => {
  const index = [
    { path: 'domain/visits.md', lang: '', text: 'A visit belongs to a pet.\nVisits have a date.' },
    { path: 'guides/x.md', lang: '', text: 'visit visit visit' },
    { path: 'domain/visits.md', lang: 'es', text: 'Una visita.' },
  ]
  const hits = scoreSearch(index, 'visit', '')
  expect(hits.map((h) => h.path)).toEqual(['domain/visits.md', 'guides/x.md'])
  expect(hits[0].score).toBe(2 + 5)
  expect(hits[0].lines).toEqual(['A visit belongs to a pet.', 'Visits have a date.'])
  expect(scoreSearch(index, 'visita', 'es').map((h) => h.path)).toEqual(['domain/visits.md'])
  expect(scoreSearch(index, 'visit', 'fr')).toHaveLength(2)                        // no French index: English
  expect(scoreSearch(index, 'a', '')).toEqual([])                                  // one-letter terms do not count
})
