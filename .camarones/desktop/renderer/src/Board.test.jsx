import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { AddForm, BoardView, StoryPanel } from './sections/Board.jsx'
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

// The story panel and the add form (BoardPanels.jsx, re-exported by Board.jsx).
const story = { id: 'WI-14', title: 'Retry a failed charge', type: 'story', status: 'Ready', description: 'Charges retry with a back-off.',
  criteria: [{ n: 1, text: 'Retries three times', done: true }, { n: 2, text: 'Gives up after a minute', done: false }], dod: [], links: [], history: [] }
const kids = [card({ id: 'WI-15', title: 'Back off between retries', status: 'In Progress', epic: 'WI-14' }),
  card({ id: 'WI-16', title: 'Log each retry', status: 'Backlog', epic: 'WI-14' })]
const html = (el, lang = 'es') => (setLang(lang), renderToStaticMarkup(el))

test('a story panel lists its tasks with their status and offers to add one', () => {
  const out = html(<StoryPanel item={story} children={kids} lang="es" writable onAddTask={() => {}} onOpen={() => {}} />)
  expect(out).toContain('aria-label="WI-14"')
  expect(out).toContain('Back off between retries')
  expect(out).toContain('Log each retry')
  expect(out).toContain('En curso')
  expect(out).toMatch(/<button [^>]*>Añadir tarea<\/button>/)
  expect(html(<StoryPanel item={story} children={kids} lang="en" writable onAddTask={() => {}} onOpen={() => {}} />, 'en'))
    .toMatch(/<button [^>]*>Add a task<\/button>/)
})

test('a panel for anything but a story shows description and criteria, with no tasks block and no add button', () => {
  const out = html(<StoryPanel item={{ ...story, id: 'WI-15', type: 'task' }} children={[]} lang="en" writable onAddTask={() => {}} onOpen={() => {}} />, 'en')
  expect(out).toContain('Charges retry with a back-off.')
  expect(out).toContain('WI-15/AC-1')
  expect(out).toContain('Gives up after a minute')
  expect(out).not.toContain('Add a task')
  expect(out).not.toContain('dk-bd-kids')
})

test('a read-only window cannot add a task', () => {
  expect(html(<StoryPanel item={story} children={[]} lang="en" writable={false} onAddTask={() => {}} onOpen={() => {}} />, 'en'))
    .toMatch(/<button [^>]*disabled=""[^>]*>Add a task/)
})

test('a panel whose item could not be read says so as an alert', () => {
  expect(html(<StoryPanel id="WI-14" error="no such item" lang="en" onOpen={() => {}} />, 'en')).toMatch(/role="alert".*no such item/)
})

const cards = [card({ id: 'WI-2', type: 'epic', title: 'Payments' }), card({ id: 'WI-14', type: 'story', title: 'Retry', epic: 'WI-2' })]

test('the add form opened from a story has the task type and that story selected', () => {
  const out = html(<AddForm cards={cards} prefill={{ type: 'task', parent: 'WI-14' }} onSubmit={() => {}} onClose={() => {}} />)
  expect(out).toMatch(/<option value="task" selected="">/)
  expect(out).toMatch(/<option value="WI-14" selected="">/)
  expect(out).not.toMatch(/<option value="WI-2" selected/)
})

test('an add form that failed shows the server message as an alert and keeps what was typed', () => {
  const out = html(<AddForm cards={cards} prefill={{ type: 'task', parent: 'WI-14', title: 'Back off' }} error="bad parent"
    onSubmit={() => {}} onClose={() => {}} />, 'en')
  expect(out).toMatch(/role="alert".*bad parent/)
  expect(out).toMatch(/<input[^>]*value="Back off"/)
})

test('the add form is in the language and blocks a second submit while it saves', () => {
  expect(html(<AddForm cards={cards} busy onSubmit={() => {}} onClose={() => {}} />)).toMatch(/<fieldset[^>]*disabled=""/)
  expect(html(<AddForm cards={cards} onSubmit={() => {}} onClose={() => {}} />, 'en')).toContain('>Add<')
})

test('the header button adds an item; a read-only board disables it', () => {
  expect(view(sample)).toMatch(/<button [^>]*>Añadir<\/button>/)
  expect(view(sample, 'en')).toMatch(/<button [^>]*>Add<\/button>/)
  expect(view(board([card({})], { writable: false }))).toMatch(/<button [^>]*disabled=""[^>]*>Añadir<\/button>/)
})

test('the side panel sits beside the columns', () => {
  const out = view(sample, 'es', { side: <aside aria-label="WI-14" /> })
  expect(out).toContain('with-side')
  expect(out.indexOf('role="group"')).toBeLessThan(out.indexOf('aria-label="WI-14"'))
})

test('an empty board points at the Add button', () => {
  expect(view(board([]))).toContain('Pulsa Añadir')
  expect(view(board([]))).not.toContain('portal')
  expect(view(board([]), 'en')).toContain('Press Add')
  expect(view(board([]), 'en')).not.toContain('camaron board add')
})
