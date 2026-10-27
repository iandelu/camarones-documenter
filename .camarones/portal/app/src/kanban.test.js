import { expect, test } from 'vitest'
import { applyFilters, blockedText, parentOf, parseArg, parseNewArg, waveOf } from './kanban.js'
import { STRINGS } from './i18n.js'

const link = (trust, fresh = null) => ({ link: 'X', trust, fresh, changed: false, missing: false })
const card = (id, status, ordinal, more = {}) => ({ id, status, ordinal, repos: [], labels: [], epic: null, links: [], ...more })

const cards = [
  card('WI-3', 'Ready', 2000, { repos: ['api'], labels: ['pay'], epic: 'WI-1', links: [link('confirmed', 'suspect')] }),
  card('WI-2', 'Ready', 1000, { repos: ['web'], links: [link('draft')] }),
  card('WI-4', 'Done', 1000, { repos: ['api'], labels: ['pay'], links: [link('confirmed', 'fresh')] }),
  card('WI-1', 'Backlog', 1000, { type: 'epic' }),
  card('WI-5', 'In Progress', 1000, { epic: 'WI-1', links: [link('confirmed', 'stale')] }),
]

test('filters: repo, epic, label and docs state, alone and together', () => {
  const ids = (f) => applyFilters(cards, f).map((c) => c.id)
  expect(ids({})).toEqual(['WI-3', 'WI-2', 'WI-4', 'WI-1', 'WI-5'])
  expect(ids({ repo: 'api' })).toEqual(['WI-3', 'WI-4'])
  expect(ids({ epic: 'WI-1' })).toEqual(['WI-3', 'WI-1', 'WI-5'])            // the epic itself and its stories
  expect(ids({ label: 'pay' })).toEqual(['WI-3', 'WI-4'])
  expect(ids({ docs: 'suspect' })).toEqual(['WI-3', 'WI-5'])                 // suspect or stale
  expect(ids({ docs: 'unconfirmed' })).toEqual(['WI-2'])
  expect(ids({ repo: 'api', label: 'pay', docs: 'suspect' })).toEqual(['WI-3'])
  expect(ids({ repo: 'api', epic: 'WI-1', docs: 'unconfirmed' })).toEqual([])
  expect(ids({ repo: '', epic: '', label: '', docs: '' })).toHaveLength(5)
})

test('a missing or unreadable link counts as unconfirmed (R15, as the CLI)', () => {
  const missing = { link: 'FLOW-zzzz', trust: null, fresh: null, changed: false, missing: true }
  const only = [card('WI-7', 'Ready', 0, { links: [missing] }), card('WI-8', 'Ready', 0, { links: [link('confirmed')] })]
  expect(applyFilters(only, { docs: 'unconfirmed' }).map((c) => c.id)).toEqual(['WI-7'])
})

test('every Board string exists in es and en, the docs count too', () => {
  const kb = (l) => Object.keys(STRINGS[l]).filter((k) => /^kb/.test(k)).sort()
  expect(kb('es')).toEqual(kb('en'))
  for (const l of ['es', 'en']) for (const k of ['kbDocsOne', 'kbDocsMany']) expect(STRINGS[l][k]).toContain('{n}')
})

test('parseNewArg reads the add form address of a doc section', () => {
  expect(parseNewArg('new?path=flows/payments.md&section=retries')).toEqual({ path: 'flows/payments.md', section: 'retries' })
  expect(parseNewArg('new?path=flows/a%20b.md')).toEqual({ path: 'flows/a b.md', section: '' })
  expect(parseNewArg('new')).toEqual({ path: '', section: '' })
  expect(parseNewArg('WI-3')).toBeNull()
  expect(parseNewArg(null)).toBeNull()
})

// Historias: a story's subtasks on the board (spec §4.7) — `?parent=WI-14` keeps the story and its children.
const family = [
  card('WI-10', 'Backlog', 1000, { type: 'story', parent: 'WI-1', epic: 'WI-1' }),
  card('WI-11', 'Backlog', 2000, { type: 'task', parent: 'WI-10', epic: 'WI-10', wave: 0 }),
  card('WI-12', 'Ready', 1000, { type: 'task', parent: 'wi-10', epic: 'wi-10', wave: 1, blocked_by: [{ id: 'WI-20', kind: 'conflict' }] }),
  card('WI-13', 'Done', 1000, { type: 'task', parent: 'WI-10', epic: 'WI-10', wave: null }),
  card('WI-20', 'In Progress', 1000, { type: 'task', parent: 'WI-19', wave: null }),
  card('WI-21', 'Backlog', 3000, { type: 'task', wave: 2 }),
]

test('applyFilters: parent keeps the parent itself and its children, any case, with the other filters', () => {
  const ids = (f) => applyFilters(family, f).map((c) => c.id)
  expect(ids({ parent: 'WI-10' })).toEqual(['WI-10', 'WI-11', 'WI-12', 'WI-13'])
  expect(ids({ parent: 'wi-10' })).toEqual(['WI-10', 'WI-11', 'WI-12', 'WI-13'])
  expect(ids({ parent: 'WI-19' })).toEqual(['WI-20'])
  expect(ids({ parent: 'WI-99' })).toEqual([])
  expect(ids({ parent: '' })).toHaveLength(6)
  expect(applyFilters(cards, { parent: 'WI-1' }).map((c) => c.id)).toEqual(['WI-1'])   // `epic` is not `parent`
})

test('waveOf: 1-based waves for Backlog and Ready cards, from the cards or from a waves list', () => {
  expect(waveOf(family)).toEqual({ 'WI-11': 1, 'WI-12': 2, 'WI-21': 3 })
  expect(waveOf(family, [[{ id: 'WI-12' }], ['WI-11', 'WI-21'], ['WI-20']])).toEqual({ 'WI-12': 1, 'WI-11': 2, 'WI-21': 2 })
  expect(waveOf([])).toEqual({})
  expect(waveOf([card('WI-30', 'Backlog', 0, { wave: -1 })])).toEqual({})
})

test('parentOf: the story a task hangs from, only when that parent is a story', () => {
  const byId = Object.fromEntries(family.map((c) => [c.id, c]))
  expect(parentOf(byId['WI-11'], byId)).toBe('WI-10')
  expect(parentOf(byId['WI-12'], byId)).toBe('WI-10')
  expect(parentOf(byId['WI-10'], byId)).toBeNull()          // a story under an epic
  expect(parentOf(byId['WI-20'], byId)).toBeNull()          // its parent is not on the board
  expect(parentOf(byId['WI-21'], byId)).toBeNull()
})

test('parseArg: a card, the add form, the parent filter, or nothing', () => {
  expect(parseArg('?parent=WI-14')).toEqual({ parent: 'WI-14' })
  expect(parseArg('?parent=wi-14&x=1')).toEqual({ parent: 'WI-14' })
  expect(parseArg('?parent=')).toEqual({})
  expect(parseArg('WI-3')).toEqual({ open: 'WI-3' })
  expect(parseArg('wi-3')).toEqual({ open: 'WI-3' })
  expect(parseArg('new?path=a.md')).toEqual({ add: { path: 'a.md', section: '' } })
  expect(parseArg('')).toEqual({})
  expect(parseArg(undefined)).toEqual({})
})

test('blockedText: the ids and kinds the start gate gave', () => {
  expect(blockedText([{ id: 'WI-20', kind: 'conflict', files: ['a:b'] }, { id: 'WI-7', kind: 'dependency' }]))
    .toBe('WI-20 (conflict), WI-7 (dependency)')
  expect(blockedText([])).toBe('')
  expect(blockedText(undefined)).toBe('')
})
