import { expect, test } from 'vitest'
import { applyFilters, columns, dropAnchor, keyMove, parseNewArg, STATUS_LABELS } from './kanban.js'
import { STRINGS } from './i18n.js'

const STATUSES = ['Backlog', 'Ready', 'In Progress', 'In Review', 'Done', 'Blocked']
const link = (trust, fresh = null) => ({ link: 'X', trust, fresh, changed: false, missing: false })
const card = (id, status, ordinal, more = {}) => ({ id, status, ordinal, repos: [], labels: [], epic: null, links: [], ...more })

const cards = [
  card('WI-3', 'Ready', 2000, { repos: ['api'], labels: ['pay'], epic: 'WI-1', links: [link('confirmed', 'suspect')] }),
  card('WI-2', 'Ready', 1000, { repos: ['web'], links: [link('draft')] }),
  card('WI-4', 'Done', 1000, { repos: ['api'], labels: ['pay'], links: [link('confirmed', 'fresh')] }),
  card('WI-1', 'Backlog', 1000, { type: 'epic' }),
  card('WI-5', 'In Progress', 1000, { epic: 'WI-1', links: [link('confirmed', 'stale')] }),
]

test('labels: the files say English, the Spanish UI says its own words', () => {
  expect(Object.keys(STATUS_LABELS.en)).toEqual(STATUSES)
  expect(STATUSES.map((s) => STATUS_LABELS.es[s])).toEqual(['Backlog', 'Listo', 'En curso', 'En revisión', 'Hecho', 'Bloqueado'])
  expect(STATUSES.map((s) => STATUS_LABELS.en[s])).toEqual(STATUSES)
})

test('columns keeps all six statuses in order, empty ones too, cards by ordinal', () => {
  const cols = columns(cards, STATUSES)
  expect(cols.map((c) => c.status)).toEqual(STATUSES)
  expect(cols[1].cards.map((c) => c.id)).toEqual(['WI-2', 'WI-3'])
  expect(cols[3].cards).toEqual([])
  expect(cols[5].cards).toEqual([])
  expect(columns([card('WI-10', 'Ready', 0), card('WI-9', 'Ready', 0)], STATUSES)[1].cards.map((c) => c.id))
    .toEqual(['WI-9', 'WI-10'])                                              // a tie goes by the id's number
})

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

test('keyMove skips empty columns when picking, and stays put when there is none', () => {
  const cols = columns(cards, STATUSES)              // In Review (3) and Blocked (5) are empty
  const inProgress = { focus: 'WI-5', grabbed: false, col: 2, row: 0 }
  expect(keyMove(inProgress, 'ArrowRight', cols)).toMatchObject({ focus: 'WI-4', col: 4, row: 0 })
  const done = { focus: 'WI-4', grabbed: false, col: 4, row: 0 }
  expect(keyMove(done, 'ArrowLeft', cols)).toMatchObject({ focus: 'WI-5', col: 2 })
  expect(keyMove(done, 'ArrowRight', cols)).toMatchObject({ focus: 'WI-4', col: 4 })   // only empty columns to the right
  expect(keyMove({ focus: 'WI-1', grabbed: false, col: 0, row: 0 }, 'ArrowLeft', cols)).toMatchObject({ focus: 'WI-1', col: 0 })
})

test('dropAnchor: first place, last place, onto itself', () => {
  const col = [card('WI-2', 'Ready', 1000), card('WI-3', 'Ready', 2000)]
  expect(dropAnchor(col, 0, 'WI-9')).toEqual({ before: 'WI-2' })
  expect(dropAnchor(col, 2, 'WI-9')).toEqual({ after: 'WI-3' })
  expect(dropAnchor(col, 1, 'WI-9')).toEqual({ after: 'WI-2' })
  expect(dropAnchor(col, 0, 'WI-2')).toEqual({})
  expect(dropAnchor(col, 1, 'WI-2')).toEqual({})
  expect(dropAnchor(col, 2, 'WI-2')).toEqual({ after: 'WI-3' })
  expect(dropAnchor([], 0, 'WI-9')).toEqual({})
})

test('keyMove: arrows pick, Space grabs, arrows move, Enter drops, Escape cancels', () => {
  const cols = columns(cards, STATUSES)
  const start = { focus: 'WI-2', grabbed: false, col: 1, row: 0 }
  const right = keyMove(start, 'ArrowRight', cols)
  expect(right).toMatchObject({ focus: 'WI-5', grabbed: false, col: 2, row: 0 })
  expect(keyMove(start, 'ArrowDown', cols)).toMatchObject({ focus: 'WI-3', row: 1 })
  expect(keyMove({ ...start, col: 5 }, 'ArrowRight', cols).col).toBe(5)    // the last column stays the last

  const grabbed = keyMove(start, ' ', cols)
  expect(grabbed.grabbed).toBe(true)
  const moved = keyMove(grabbed, 'ArrowRight', cols)
  expect(moved).toMatchObject({ focus: 'WI-2', grabbed: true, col: 2 })
  const dropped = keyMove(moved, 'Enter', cols)
  expect(dropped.grabbed).toBe(false)
  expect(dropped.drop).toEqual({ id: 'WI-2', status: 'In Progress', before: 'WI-5' })
  expect(keyMove(keyMove(moved, 'ArrowDown', cols), 'Enter', cols).drop).toEqual({ id: 'WI-2', status: 'In Progress', after: 'WI-5' })

  const cancelled = keyMove(moved, 'Escape', cols)
  expect(cancelled).toMatchObject({ focus: 'WI-2', grabbed: false, col: 1, row: 0 })
  expect(cancelled.drop).toBeUndefined()
  expect(keyMove(start, 'Enter', cols).open).toBe('WI-2')                   // Enter without a grab opens the card
})

test('parseNewArg reads the add form address of a doc section', () => {
  expect(parseNewArg('new?path=flows/payments.md&section=retries')).toEqual({ path: 'flows/payments.md', section: 'retries' })
  expect(parseNewArg('new?path=flows/a%20b.md')).toEqual({ path: 'flows/a b.md', section: '' })
  expect(parseNewArg('new')).toEqual({ path: '', section: '' })
  expect(parseNewArg('WI-3')).toBeNull()
  expect(parseNewArg(null)).toBeNull()
})
