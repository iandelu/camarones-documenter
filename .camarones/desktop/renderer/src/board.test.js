import { afterEach, expect, test } from 'vitest'
import { allowedParents, cardAt, childrenOf, fit, gateKey, gateMessage, moveOutcome, parentLabel, parentOf, placed, sendMove, shouldFocus } from './board.js'
import { setLang, t } from './i18n.js'

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

// The gate and the revert: what the Board does with a move the server holds back or refuses.
const gate = () => Object.assign(new Error('blocked'), { status: 409, data: { blocked_by: ['WI-3', 'WI-4'] } })
const fakePost = (...answers) => {
  const calls = []
  return { calls, post: async (body) => { calls.push(body); const a = answers[calls.length - 1]; if (a instanceof Error) throw a; return a ?? {} } }
}
const body = { id: 'WI-9', status: 'Done', after: 'WI-2' }

test('sendMove: a move that goes through is sent once, without force', async () => {
  const f = fakePost({ id: 'WI-9' })
  expect(await sendMove(f.post, () => { throw new Error('asked') }, body)).toEqual({ kind: 'sent' })
  expect(f.calls).toEqual([body])
})

test('sendMove: a gate asks with the blocking ids and, on yes, sends again with force', async () => {
  const f = fakePost(gate(), {})
  const asked = []
  expect(await sendMove(f.post, (ids) => { asked.push(ids); return true }, body)).toEqual({ kind: 'sent' })
  expect(asked).toEqual([['WI-3', 'WI-4']])
  expect(f.calls).toEqual([body, { ...body, force: true }])
})

test('sendMove: a gate the person refuses is declined, without a second call and without a message', async () => {
  const f = fakePost(gate())
  expect(await sendMove(f.post, () => false, body)).toEqual({ kind: 'declined' })
  expect(f.calls).toEqual([body])
})

test('sendMove: any other failure is an error with the server message, and nothing is asked', async () => {
  const f = fakePost(Object.assign(new Error('no such status'), { status: 400, data: {} }))
  expect(await sendMove(f.post, () => { throw new Error('asked') }, body)).toEqual({ kind: 'error', message: 'no such status' })
  expect(f.calls).toEqual([body])
})

test('sendMove: the forced re-send failing is an error too', async () => {
  const f = fakePost(gate(), new Error('disk full'))
  expect(await sendMove(f.post, () => true, body)).toEqual({ kind: 'error', message: 'disk full' })
  expect(f.calls).toHaveLength(2)
})

// The parent a new item may be given (the server's table: epic -> story/bug/spike/task, story -> task). Archived and
// Done parents stay in the list (the board never sends archived ones): a finished story can still get a late task.
test('allowedParents: a task goes under stories and epics, a story/bug/spike under epics, an epic under nothing', () => {
  const cards = [
    { id: 'WI-14', type: 'story' }, { id: 'WI-2', type: 'epic' }, { id: 'WI-9', type: 'task' },
    { id: 'WI-30', type: 'story', status: 'Done' }, { id: 'WI-3', type: 'epic' }, { id: 'WI-11', type: 'bug' },
  ]
  const ids = (type) => allowedParents(type, cards).map((c) => c.id)
  expect(ids('task')).toEqual(['WI-2', 'WI-3', 'WI-14', 'WI-30'])
  for (const t of ['story', 'bug', 'spike']) expect(ids(t)).toEqual(['WI-2', 'WI-3'])
  expect(ids('epic')).toEqual([])
  expect(ids('nonsense')).toEqual([])
})

// The keyboard's focus effect: the card kb points at takes the focus unless the person is working elsewhere.
const el = { id: 'bd-B' }
const inBoard = { tagName: 'DIV', closest: (sel) => (sel === '.dk-bd' ? {} : null) }
const outside = { tagName: 'INPUT', closest: () => null }

test('shouldFocus: a card picked by arrow from another card takes the focus; a field outside the board does not', () => {
  expect(shouldFocus({ focus: 'B' }, inBoard, el)).toBe(true)          // ArrowDown on card A: the focus moves to B
  expect(shouldFocus({ focus: 'B' }, outside, el)).toBe(false)         // a form field in the side panel or elsewhere
  expect(shouldFocus({ focus: 'B' }, el, el)).toBe(true)
  expect(shouldFocus({ focus: 'B' }, null, el)).toBe(true)
  expect(shouldFocus({ focus: 'B' }, { tagName: 'BODY', closest: () => null }, el)).toBe(true)   // nothing focused
  expect(shouldFocus({ focus: 'B', grabbed: true }, outside, el)).toBe(true)
  expect(shouldFocus({ focus: 'B' }, inBoard, null)).toBe(false)       // the card is not drawn
})

test('cardAt: the keyboard state for a card, from where it is drawn', () => {
  const cols = [{ status: 'Ready', cards: [{ id: 'A' }, { id: 'B' }] }, { status: 'Done', cards: [{ id: 'C' }] }]
  expect(cardAt(cols, 'C')).toEqual({ focus: 'C', grabbed: false, col: 1, row: 0 })
  expect(cardAt(cols, 'B')).toEqual({ focus: 'B', grabbed: false, col: 0, row: 1 })
  expect(cardAt(cols, 'nope')).toBeNull()
})

test('gateKey: one blocking card reads in the singular, several in the plural', () => {
  expect(gateKey(['WI-3'])).toBe('bd.gate.one')
  expect(gateKey(['WI-3', 'WI-4'])).toBe('bd.gate.many')
})

// The start gate's 409 names its blockers as {id, kind, files?} (lib/serve.py, Historias); older servers sent bare ids.
const blockedBy = [{ id: 'WI-3', kind: 'dependency' }, { id: 'WI-7', kind: 'conflict', files: ['api:src/a.py'] }]
afterEach(() => setLang('es'))

test('gateMessage: the confirmation names each blocker by id and says why, in es and en', () => {
  expect(gateMessage(blockedBy, t)).toBe('WI-3 (dependencia), WI-7 (conflicto) bloquean esta tarjeta. ¿Moverla de todos modos?')
  expect(gateMessage([{ id: 'WI-9', kind: 'missing' }], t)).toBe('WI-9 (no está en el tablero) bloquea esta tarjeta. ¿Moverla de todos modos?')
  setLang('en')
  expect(gateMessage(blockedBy, t)).toBe('WI-3 (dependency), WI-7 (conflict) block this card. Move it anyway?')
  expect(gateMessage([{ id: 'WI-9', kind: 'missing' }], t)).toBe('WI-9 (not on the board) blocks this card. Move it anyway?')
})

test('gateMessage: bare ids, unknown kinds and junk entries still read as ids, never [object Object]', () => {
  expect(gateMessage(['WI-3', 'WI-4'], t)).toBe('WI-3, WI-4 bloquean esta tarjeta. ¿Moverla de todos modos?')
  expect(gateMessage([{ id: 'WI-3', kind: 'later' }, null, {}, 'WI-5'], t)).toBe('WI-3, WI-5 bloquean esta tarjeta. ¿Moverla de todos modos?')
  expect(gateMessage(blockedBy, t)).not.toContain('[object')
})

test("sendMove hands the server's blocker objects to confirm as they came", async () => {
  const calls = []
  const post = async (b) => { calls.push(b); if (calls.length === 1) throw Object.assign(new Error('blocked'), { status: 409, data: { blocked_by: blockedBy } }) }
  let seen = null
  expect(await sendMove(post, (bs) => ((seen = bs), true), { id: 'WI-1', status: 'Ready' })).toEqual({ kind: 'sent' })
  expect(seen).toEqual(blockedBy)
  expect(calls[1]).toEqual({ id: 'WI-1', status: 'Ready', force: true })
})
