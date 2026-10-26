import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { BoardView } from './sections/Board.jsx'
import { setLang } from './i18n.js'

const STATUSES = ['Backlog', 'Ready', 'In Progress', 'In Review', 'Done', 'Blocked']
const card = (o) => ({ id: 'WI-1', title: 't', type: 'task', status: 'Ready', ordinal: 1, assignee: [], labels: [], priority: null,
  epic: null, repos: [], docs: [], links: [], ...o })
const board = (cards, o = {}) => ({ enabled: true, writable: true, statuses: STATUSES, cards, problems: [], ...o })
const view = (b, lang = 'es', props = {}) => (setLang(lang), renderToStaticMarkup(
  <BoardView board={b} lang={lang} kb={null} onMove={() => {}} onOpen={() => {}} onKey={() => {}} dragging={null} {...props} />))

afterEach(() => setLang('es'))

const sample = board([
  card({ id: 'WI-2', type: 'epic', title: 'Payments', status: 'Backlog' }),
  card({ id: 'WI-14', type: 'story', title: 'Retry a failed charge', status: 'Ready', priority: 'high', epic: 'WI-2' }),
  card({ id: 'WI-15', type: 'task', title: 'Back off between retries', status: 'In Progress', epic: 'WI-14' }),
])

test('six columns with their labels, in Spanish and in English', () => {
  const es = view(sample)
  for (const l of ['Backlog', 'Listo', 'En curso', 'En revisión', 'Hecho', 'Bloqueado']) expect(es).toContain(`>${l}<`)
  expect(es.match(/role="group"/g)).toHaveLength(6)
  const en = view(sample, 'en')
  for (const l of ['Backlog', 'Ready', 'In Progress', 'In Review', 'Done', 'Blocked']) expect(en).toContain(`>${l}<`)
})

test('a card shows its id, type, priority and title; a child of a story points at it, a child of an epic does not', () => {
  const out = view(sample)
  expect(out).toContain('WI-15')
  expect(out).toContain('Back off between retries')
  expect(out).toContain('↳ WI-14')
  expect(out).toContain('Historia')
  expect(out).toContain('high')
  expect(out).not.toContain('↳ WI-2')
  expect(view(sample, 'en')).toContain('Story')
})

// Review Focus: a row edited by hand can miss fields or have them in another shape; it still draws.
test('a hand-edited row still shows its id and title', () => {
  const out = view(board([{ id: 'WI-9', title: 'x', type: '', priority: null, labels: 'p', assignee: null }]))
  expect(out).toContain('WI-9')
  expect(out).toContain('>x<')
})

test('a board that is not on offers to turn it on, with the button', () => {
  expect(view(board([], { enabled: false }))).toMatch(/<button [^>]*>Activar el tablero<\/button>/)
  expect(view(board([], { enabled: false }), 'en')).toMatch(/<button [^>]*>Turn the board on<\/button>/)
})

test('a read-only board cannot be turned on or dragged, and says so', () => {
  const ro = board([card({})], { writable: false })
  expect(view(ro)).toContain('solo lectura')
  expect(view(ro)).not.toContain('draggable="true"')
  expect(view(sample)).toContain('draggable="true"')
  expect(view(board([], { enabled: false, writable: false }))).toMatch(/<button [^>]*disabled=""[^>]*>Activar el tablero/)
})

test('a failed move is shown as an alert above the columns', () => {
  const out = view(sample, 'es', { notice: 'WI-14 is blocked' })
  expect(out).toMatch(/role="alert".*WI-14 is blocked/)
  expect(out.indexOf('role="alert"')).toBeLessThan(out.indexOf('role="group"'))
})

test('an enabled board with no cards says what to do, without a joke', () => {
  expect(view(board([]))).toContain('Aún no hay tarjetas')
  expect(view(board([]), 'en')).toContain('No cards yet')
})

test('the card being grabbed with the keyboard is marked', () => {
  const kb = { focus: 'WI-14', grabbed: true, col: 1, row: 0 }
  expect(view(sample, 'es', { kb })).toMatch(/aria-grabbed="true"/)
})
