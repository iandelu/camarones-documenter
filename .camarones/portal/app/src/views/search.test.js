import { expect, test } from 'vitest'
import { marked, paletteGroups, rankBySpace } from './search.js'

const byPath = { 'a.md': { path: 'a.md', title: 'Visits', space: 'docs' }, 'repos/api/w.md': { path: 'repos/api/w.md', title: 'Visit API', space: 'wiki' },
  'interview/n.md': { path: 'interview/n.md', title: 'Visit notes', space: 'notes' }, 'b.md': { path: 'b.md', title: 'Owners', space: 'docs' } }

test('docs first, then wikis, then working notes; unknown pages last', () => {
  const hits = [{ path: 'interview/n.md', score: 9 }, { path: 'x.md', score: 9 }, { path: 'repos/api/w.md', score: 1 }, { path: 'a.md', score: 1 }]
  expect(rankBySpace(hits, byPath).map((h) => h.path)).toEqual(['a.md', 'repos/api/w.md', 'interview/n.md', 'x.md'])
})

test('marked splits a text into plain and matched parts, case-insensitive, 2+ letter terms', () => {
  expect(marked('Visit a Pet', 'visit pet')).toEqual([{ text: 'Visit', hit: true }, { text: ' a ', hit: false }, { text: 'Pet', hit: true }])
  expect(marked('no match', 'zz')).toEqual([{ text: 'no match', hit: false }])
  expect(marked('a+bb (cc)', 'bb (cc')).toEqual([{ text: 'a+', hit: false }, { text: 'bb', hit: true }, { text: ' (', hit: false },
    { text: 'cc', hit: true }, { text: ')', hit: false }])                       // regex characters in the query are literal
  expect(marked('a b', 'a')).toEqual([{ text: 'a b', hit: false }])             // one-letter terms do not mark
})

const t = (k, v = {}) => (v.q ? `${k}:${v.q}` : k)
const base = { index: { docs: Object.values(byPath) }, order: ['b.md', 'a.md'], byPath, t,
  places: [{ key: 'zone.arch', href: '#/arch', zone: 'arch' }, { key: 'view.c4', href: '#/c4', zone: 'arch' }] }

test('without a query: the places and the docs in reading order', () => {
  const groups = paletteGroups({ ...base, q: '', mode: 'live' })
  expect(groups.map((g) => g.id)).toEqual(['places', 'titles'])
  expect(groups[1].items.map((i) => i.href)).toEqual(['#/docs/b.md', '#/docs/a.md'])
  expect(groups[0].items[1]).toMatchObject({ label: 'view.c4', where: 'zone.arch' })
})

test('with a query: ask first on the server, then places and titles that match, docs before wikis', () => {
  const groups = paletteGroups({ ...base, q: 'visit', mode: 'live' })
  expect(groups[0]).toMatchObject({ id: 'ask', items: [{ href: '#/ask/visit' }] })
  const titles = groups.find((g) => g.id === 'titles').items
  expect(titles.map((i) => i.path)).toEqual(['a.md', 'repos/api/w.md', 'interview/n.md'])
  expect(titles[1].space).toBe('wiki')
  expect(groups.find((g) => g.id === 'places').items).toEqual([])
})

test('the export cannot ask: no ask group', () => {
  expect(paletteGroups({ ...base, q: 'visit', mode: 'static' }).map((g) => g.id)).not.toContain('ask')
})

test('content hits skip what the titles already show, and end with the full results page', () => {
  const content = [{ path: 'a.md', lines: ['x'] }, { path: 'b.md', lines: ['Owners have visits'] }, { path: 'gone.md', lines: [] }]
  const groups = paletteGroups({ ...base, q: 'visit', mode: 'static', content })
  const items = groups.find((g) => g.id === 'content').items
  expect(items.map((i) => i.href)).toEqual(['#/docs/b.md', '#/search/visit'])
  expect(items[0].sub).toBe('Owners have visits')
})
