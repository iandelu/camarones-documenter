import { expect, test } from 'vitest'
import { childrenOf, fit, moveOutcome, parentLabel, parentOf, placed } from './board.js'

const rows = [
  { id: 'WI-14', type: 'story', ordinal: 1 },
  { id: 'WI-2', type: 'epic', ordinal: 1 },
  { id: 'WI-20', type: 'task', ordinal: 3, epic: 'WI-14' },
  { id: 'WI-5', type: 'task', ordinal: 3, epic: 'wi-14' },
  { id: 'WI-9', type: 'task', ordinal: 1, epic: 'WI-14' },
  { id: 'WI-7', type: 'task', ordinal: 1, epic: 'WI-2' },
]
const byId = new Map(rows.map((r) => [r.id, r]))

test('a parent key wins over epic, in capitals', () => {
  expect(parentOf({ parent: 'wi-3', epic: 'WI-2' })).toBe('WI-3')
  expect(parentOf({ epic: 'wi-2' })).toBe('WI-2')
  expect(parentOf({ parent: null, epic: 'WI-2' })).toBe('WI-2')
  expect(parentOf({})).toBeNull()
  expect(parentOf({ epic: '' })).toBeNull()
})

test.each([
  ['a parent story on the board', { epic: 'WI-14' }, '↳ WI-14'],
  ['a parent epic', { epic: 'WI-2' }, ''],
  ['a parent missing from the board', { epic: 'WI-99' }, '↳ WI-99'],
  ['no parent', {}, ''],
  ['a lower-case id in the row', { epic: 'wi-14' }, '↳ WI-14'],
  ['a parent key arriving later', { parent: 'WI-14', epic: 'WI-2' }, '↳ WI-14'],
])('parentLabel: %s', (_, card, label) => {
  expect(parentLabel(card, byId)).toBe(label)
})

test('children come by ordinal, then numeric id, and only those of that parent', () => {
  expect(childrenOf(rows, 'WI-14').map((r) => r.id)).toEqual(['WI-9', 'WI-5', 'WI-20'])
  expect(childrenOf(rows, 'wi-2').map((r) => r.id)).toEqual(['WI-7'])
  expect(childrenOf(rows, 'WI-1')).toEqual([])
})

test('a 409 with the blocking ids is a gate; any other failure is an error with its message', () => {
  expect(moveOutcome({ status: 409, data: { blocked_by: ['WI-3'] } })).toEqual({ kind: 'gate', blockedBy: ['WI-3'] })
  expect(moveOutcome({ status: 409, message: 'no', data: {} })).toEqual({ kind: 'error', message: 'no' })
  expect(moveOutcome({ status: 409, message: 'no' })).toEqual({ kind: 'error', message: 'no' })
  expect(moveOutcome({ status: 400, message: 'x' })).toEqual({ kind: 'error', message: 'x' })
  expect(moveOutcome(new Error('offline'))).toEqual({ kind: 'error', message: 'offline' })
})

test('a card grabbed with the keyboard is drawn where it would land', () => {
  const cols = [{ status: 'Ready', cards: [{ id: 'A' }, { id: 'B' }] }, { status: 'Done', cards: [{ id: 'C' }] }]
  expect(placed(cols, null)).toBe(cols)
  expect(placed(cols, { grabbed: false, focus: 'A' })).toBe(cols)
  const out = placed(cols, { grabbed: true, focus: 'A', col: 1, row: 1 })
  expect(out.map((c) => c.cards.map((x) => x.id))).toEqual([['B'], ['C', 'A']])
  expect(cols[0].cards).toHaveLength(2)                     // the input is not touched
})

test('a row with no known status is drawn in the first column instead of vanishing', () => {
  const cards = [{ id: 'A', status: 'Done' }, { id: 'B' }, { id: 'C', status: 'Doing' }]
  expect(fit(cards, ['Backlog', 'Done']).map((c) => c.status)).toEqual(['Done', 'Backlog', 'Backlog'])
})
