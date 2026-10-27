import { expect, test } from 'vitest'
import { acceptBlock, addAttendees, addHit, blockedPart, choiceBody, counts, crumb, FILTERS, filterRows, firstOpen, keyEffect, newPointBody,
  nextPart, partKind, presentKey, reviewKey, reviewParts, route, screen, stale, startScreen, STEPS, stepper, viewOf } from './adr.js'
import { setLang, t } from './i18n.js'

const states = (phase, mode) => stepper(phase, mode).map((s) => s.state)

test('routes inside the section', () => {
  expect(route('#/decisions')).toEqual({ view: 'list' })
  expect(route('#/decisions/new')).toEqual({ view: 'new' })
  expect(route('#/decisions/candidates')).toEqual({ view: 'candidates' })
  expect(route('#/decisions/0012')).toEqual({ view: 'adr', id: '0012' })
  expect(route('#/decisions/x')).toEqual({ view: 'list' })
})

test('a route tolerates a trailing slash, a query and an empty hash', () => {
  expect(route('#/decisions/0012/')).toEqual({ view: 'adr', id: '0012' })
  expect(route('#/decisions/new?from=candidates')).toEqual({ view: 'new' })
  expect(route('#/decisions/12')).toEqual({ view: 'list' })
  expect(route('#/decisions/0012/extra')).toEqual({ view: 'list' })
  expect(route('')).toEqual({ view: 'list' })
  expect(route(undefined)).toEqual({ view: 'list' })
})

const rows = [{ id: '0002', title: 'Sesión en Redis', chip: 'review', repos: ['api'] },
              { id: '0001', title: 'JPA', chip: 'accepted', repos: ['vets'] }]

test('filters count and match accents', () => {
  expect(FILTERS).toEqual(['all', 'running', 'review', 'accepted', 'superseded'])
  expect(counts(rows)).toEqual({ all: 2, running: 0, review: 1, accepted: 1, superseded: 0 })
  expect(filterRows(rows, 'all', 'sesion').map((r) => r.id)).toEqual(['0002'])
  expect(filterRows(rows, 'accepted', '').map((r) => r.id)).toEqual(['0001'])
})

test('the query matches the id and the repos, case aside, and the filter narrows it', () => {
  expect(filterRows(rows, 'all', '0001').map((r) => r.id)).toEqual(['0001'])
  expect(filterRows(rows, 'all', 'VETS').map((r) => r.id)).toEqual(['0001'])
  expect(filterRows(rows, 'review', 'jpa')).toEqual([])
  expect(filterRows(rows, 'all', '  ').map((r) => r.id)).toEqual(['0002', '0001'])
})

test('a row a hand-edited file left half empty still counts and filters', () => {
  const odd = [{ id: '0003' }, { id: '0004', title: null, chip: 'rejected', repos: null }]
  expect(counts(odd)).toEqual({ all: 2, running: 0, review: 0, accepted: 0, superseded: 0 })
  expect(filterRows(odd, 'all', '0004').map((r) => r.id)).toEqual(['0004'])
  expect(counts(undefined).all).toBe(0)
})

test('the stepper walks the phase', () => {
  expect(STEPS).toEqual(['problem', 'evidence', 'research', 'synthesis', 'review', 'accepted'])
  expect(stepper('problem').map((s) => s.id)).toEqual(STEPS)
  expect(states('problem')).toEqual(['current', 'todo', 'todo', 'todo', 'todo', 'todo'])
  expect(states('evidence')).toEqual(['done', 'current', 'todo', 'todo', 'todo', 'todo'])
  expect(states('review')).toEqual(['done', 'done', 'done', 'done', 'current', 'todo'])
  expect(states('accepted')).toEqual(['done', 'done', 'done', 'done', 'done', 'current'])
})

test('a hand-written ADR skips the AI steps', () => {
  expect(stepper('review', 'manual').map((s) => s.state)).toEqual(['done', 'done', 'skipped', 'skipped', 'current', 'todo'])
  expect(states('problem', 'manual')).toEqual(['current', 'todo', 'skipped', 'skipped', 'todo', 'todo'])
})

test('the stepper stays calm with a phase it does not know', () => {
  expect(states(undefined)).toEqual(['todo', 'todo', 'todo', 'todo', 'todo', 'todo'])
  expect(stepper('nonsense').every((s) => s.state === 'todo')).toBe(true)
})

test('a rejected ADR ends on a Rejected step, never on Accepted', () => {
  const ids = (phase, mode) => stepper(phase, mode).map((s) => s.id)
  expect(ids('rejected')).toEqual(['problem', 'evidence', 'research', 'synthesis', 'review', 'rejected'])
  expect(states('rejected')).toEqual(['done', 'done', 'done', 'done', 'done', 'current'])
  expect(ids('rejected', 'manual')).toEqual(['problem', 'evidence', 'research', 'synthesis', 'review', 'rejected'])
  expect(states('rejected', 'manual')).toEqual(['done', 'done', 'skipped', 'skipped', 'done', 'current'])
  expect(ids('accepted')).toEqual(STEPS)
})

const parts = [{ id: 'context', status: 'pending' }, { id: 'drivers', status: 'approved' }, { id: 'options', status: 'pending' }]

test('next and previous part clamp at both ends', () => {
  expect(nextPart(parts, 'context', 1)).toBe('drivers')
  expect(nextPart(parts, 'drivers', -1)).toBe('context')
  expect(nextPart(parts, 'options', 1)).toBe('options')
  expect(nextPart(parts, 'context', -1)).toBe('context')
})

test('a part that is not in the list falls back to the first, and no parts keep the current one', () => {
  expect(nextPart(parts, 'gone', 1)).toBe('context')
  expect(nextPart(parts, undefined, -1)).toBe('context')
  expect(nextPart([], 'context', 1)).toBe('context')
})

test('presentation keys, never while typing', () => {
  expect(presentKey('ArrowRight', { typing: false, options: 3 })).toEqual({ do: 'next' })
  expect(presentKey('2', { typing: false, options: 3 })).toEqual({ do: 'choose', n: 2 })
  expect(presentKey('4', { typing: false, options: 3 })).toBeNull()
  expect(presentKey('ArrowRight', { typing: true, options: 3 })).toBeNull()
})

test('every presentation key does one thing', () => {
  const ctx = { typing: false, options: 9 }
  expect(presentKey('ArrowLeft', ctx)).toEqual({ do: 'prev' })
  expect(presentKey('e', ctx)).toEqual({ do: 'edit' })
  expect(presentKey('d', ctx)).toEqual({ do: 'defer' })
  expect(presentKey('a', ctx)).toEqual({ do: 'accept' })
  expect(presentKey('Escape', ctx)).toEqual({ do: 'exit' })
  expect(presentKey('p', ctx)).toEqual({ do: 'toggle' })
  expect(presentKey('9', ctx)).toEqual({ do: 'choose', n: 9 })
  for (const k of ['0', 'x', 'E', 'Enter', ' ', '']) expect(presentKey(k, ctx), k).toBeNull()
  for (const k of ['ArrowLeft', 'e', 'd', 'a', 'Escape', 'p', '1']) expect(presentKey(k, { ...ctx, typing: true }), k).toBeNull()
})

test('a number key chooses only an option that exists', () => {
  expect(presentKey('1', { typing: false, options: 1 })).toEqual({ do: 'choose', n: 1 })
  expect(presentKey('2', { typing: false, options: 1 })).toBeNull()
  expect(presentKey('1', { typing: false, options: 0 })).toBeNull()
  expect(presentKey('1', { typing: false })).toBeNull()
})

test('a hit adds its files once, sorted', () => {
  expect(addHit(['api:b.java'], { kind: 'group', touch: 'api:orders', files: ['api:c.java', 'api:b.java'] }))
    .toEqual(['api:b.java', 'api:c.java'])
  expect(addHit([], { kind: 'page', touch: 'cam-docs:docs/orders.md' })).toEqual(['cam-docs:docs/orders.md'])
})

test('a file hit adds its touch, a group with no files adds nothing, and the list is never mutated', () => {
  const current = ['b', 'a']
  expect(addHit(current, { kind: 'file', touch: 'api:A.java' })).toEqual(['a', 'api:A.java', 'b'])
  expect(addHit(current, { kind: 'file', touch: 'a' })).toEqual(['a', 'b'])
  expect(addHit(current, { kind: 'group', touch: 'api:orders' })).toEqual(['a', 'b'])
  expect(addHit(undefined, { kind: 'page', touch: 'x:y' })).toEqual(['x:y'])
  expect(current).toEqual(['b', 'a'])
})

const adr = (points, decision = 'To be decided in review: see the decision points.') => ({ points, sections: { decision } })

test('accept explains why it cannot run yet', () => {
  expect(acceptBlock(adr([{ id: 'p1', deferred: true }]))).toEqual({ key: 'adr.why.deferred', point: 'P1' })
  expect(acceptBlock(adr([{ id: 'p1' }]))).toEqual({ key: 'adr.why.unchosen', point: 'P1' })
  expect(acceptBlock(adr([]))).toEqual({ key: 'adr.why.noDecision' })
  expect(acceptBlock(adr([{ id: 'p1', chosen: 'A' }]))).toBeNull()
})

test('accept names the first point in the way, deferred before unchosen as the server does', () => {
  expect(acceptBlock(adr([{ id: 'p1', chosen: 'A' }, { id: 'p2' }, { id: 'p3', deferred: true }])))
    .toEqual({ key: 'adr.why.unchosen', point: 'P2' })
  expect(acceptBlock(adr([{ id: 'p1', deferred: true, chosen: 'A' }]))).toEqual({ key: 'adr.why.deferred', point: 'P1' })
  expect(acceptBlock(adr([{ id: 'p1', other: 'Hazelcast' }]))).toBeNull()
})

test('with no points, a written Decision is enough and the placeholder is not', () => {
  expect(acceptBlock(adr([], 'We use Redis for sessions.'))).toBeNull()
  expect(acceptBlock(adr([], ''))).toEqual({ key: 'adr.why.noDecision' })
  expect(acceptBlock(adr([], '  \n '))).toEqual({ key: 'adr.why.noDecision' })
  expect(acceptBlock(adr([], '  To be decided in review: see the decision points.\n'))).toEqual({ key: 'adr.why.noDecision' })
  expect(acceptBlock({ sections: {} })).toEqual({ key: 'adr.why.noDecision' })
  expect(acceptBlock(null)).toEqual({ key: 'adr.why.noDecision' })
})

test('a why key reads as a sentence with its point in both languages', () => {
  const block = acceptBlock(adr([{ id: 'p2', deferred: true }]))
  setLang('es')
  expect(t(block.key, { point: block.point })).toBe('El punto P2 está aplazado: decídelo o quítalo')
  setLang('en')
  expect(t(block.key, { point: block.point })).toBe('Point P2 is deferred: decide it or remove it')
  setLang('es')
})

// The header's last breadcrumb inside the section (App.jsx): the form, the candidates or the ADR; none on the list.
test('a place inside the section has its crumb', () => {
  setLang('es')
  expect(crumb('#/decisions/new', t)).toBe('Nuevo ADR')
  expect(crumb('#/decisions/candidates', t)).toBe('Candidatas')
  expect(crumb('#/decisions/0012', t)).toBe('ADR 0012')
  expect(crumb('#/decisions', t)).toBeNull()
  expect(crumb('#/decisions/x', t)).toBeNull()
  setLang('en')
  expect(crumb('#/decisions/new', t)).toBe('New ADR')
  setLang('es')
})

// One ADR's screen as state (Decisions.jsx AdrScreen, keyed by the ADR: another one starts from startScreen).
const run = (...actions) => actions.reduce(screen, startScreen(null))
const OLD = { summary: { files: 1 }, markdown: 'm' }

test('a screen starts empty and idle, with the notice it was opened with', () => {
  expect(startScreen(null)).toEqual({ adr: null, error: '', reads: 0, pack: undefined, packError: '', packing: false, busy: false,
    actError: '', notice: null })
  expect(startScreen({ key: 'adr.renumbered', vars: { from: '0012', to: '0013' } }).notice.key).toBe('adr.renumbered')
  const s = run({ type: 'read', adr: { id: '0012' } }, { type: 'pack', pack: null })
  expect(s.adr.id).toBe('0012')
  expect(s.pack).toBeNull()
})

test('a failed read says why; Try again clears it and reads again', () => {
  const s = run({ type: 'readFailed', error: 'boom' })
  expect(s.error).toBe('boom')
  expect(screen(s, { type: 'retry' })).toMatchObject({ error: '', reads: 1 })
})

test('gathering is under way until the pack comes, or until it fails with the pack it had kept', () => {
  const s = run({ type: 'read', adr: { id: '0012' } }, { type: 'pack', pack: OLD }, { type: 'packFailed', error: 'x' }, { type: 'packing' })
  expect(s).toMatchObject({ packing: true, packError: '', pack: OLD })
  const moved = { id: '0012', state: { phase: 'evidence' } }
  expect(screen(s, { type: 'packed', pack: { summary: {} }, adr: moved })).toMatchObject({ packing: false, adr: moved, pack: { summary: {} } })
  expect(screen(s, { type: 'packed', pack: OLD, adr: null }).adr).toBe(s.adr)          // the ADR could not be read again
  expect(screen(s, { type: 'packFailed', error: 'disk full' })).toMatchObject({ packing: false, packError: 'disk full', pack: OLD })
  expect(run({ type: 'packFailed', error: 'e' }).pack).toBeNull()                       // never read: none to show
})

test('an action is busy until it ends, with the ADR it returned or why not', () => {
  const s = run({ type: 'read', adr: { id: '0012' } }, { type: 'actFailed', error: 'old' }, { type: 'busy' })
  expect(s).toMatchObject({ busy: true, actError: '' })
  expect(screen(s, { type: 'done', adr: { id: '0012', sha: 'b' } })).toMatchObject({ busy: false, adr: { sha: 'b' } })
  expect(screen(s, { type: 'actFailed', error: 'refused' })).toMatchObject({ busy: false, actError: 'refused', adr: { id: '0012' } })
})

test('a save the file outran ends what was under way and says the ADR was read again', () => {
  const s = run({ type: 'read', adr: { id: '0012', sha: 'a' } }, { type: 'busy' }, { type: 'packing' },
    { type: 'reloaded', adr: { id: '0012', sha: 'b' } })
  expect(s).toMatchObject({ busy: false, packing: false, adr: { sha: 'b' }, notice: { key: 'adr.reloaded' } })
  expect(screen(s, { type: 'nope' })).toBe(s)
})

test('an ADR opens by its phase; with no working state it is legacy', () => {
  expect(viewOf({ state: null })).toBe('legacy')
  expect(viewOf({})).toBe('legacy')
  expect(viewOf({ state: { phase: 'problem' } })).toBe('evidence')
  expect(viewOf({ state: { phase: 'evidence' } })).toBe('evidence')
  for (const phase of ['review', 'accepted', 'rejected', undefined]) expect(viewOf({ state: { phase } })).toBe('review')
})

test('a save that succeeds clears what the screen last said', () => {
  const s = run({ type: 'read', adr: { id: '0012', sha: 'a' } }, { type: 'reloaded', adr: { id: '0012', sha: 'b' } }, { type: 'busy' },
    { type: 'done', adr: { id: '0012', sha: 'c' } })
  expect(s.notice).toBeNull()
})

// ---------- the review (sections/adr/Review.jsx) ----------
const PARTS = [{ id: 'context', status: 'approved' }, { id: 'drivers', status: 'pending' }, { id: 'point:p1', status: 'deferred' },
  { id: 'options', status: 'pending' }, { id: 'affected', status: 'pending' }]
const inReview = (o = {}) => ({ id: '0012', sha: 's1', state: { phase: 'review', parts: {} }, parts: PARTS,
  points: [{ id: 'p1', question: 'Q', options: [{ id: 'A', name: 'Redis' }, { id: 'B', name: 'Postgres' }] }], sections: {}, ...o })

test('a part is a text section, a decision point or the affected docs', () => {
  expect(partKind('context')).toBe('text')
  expect(partKind('decision')).toBe('text')
  expect(partKind('point:p1')).toBe('point')
  expect(partKind('affected')).toBe('affected')
})

test('the review walks the server\'s parts, and the Decision section too when there is no point to decide', () => {
  expect(reviewParts(inReview())).toEqual(PARTS)
  const none = inReview({ points: [], parts: PARTS.filter((p) => p.id !== 'point:p1'), state: { phase: 'review', parts: { decision: 'edited' } } })
  expect(reviewParts(none).map((p) => p.id)).toEqual(['context', 'drivers', 'decision', 'options', 'affected'])
  expect(reviewParts(none)[2]).toEqual({ id: 'decision', status: 'edited' })
  expect(reviewParts(inReview({ points: [], parts: [{ id: 'context' }] }))).toEqual([{ id: 'context' }, { id: 'decision', status: 'pending' }])
  expect(reviewParts({})).toEqual([{ id: 'decision', status: 'pending' }])
  expect(reviewParts(null)).toEqual([{ id: 'decision', status: 'pending' }])
})

test('a review opens on the first part still to see, else on the first', () => {
  expect(firstOpen(PARTS)).toBe('drivers')
  expect(firstOpen([{ id: 'context', status: 'approved' }, { id: 'point:p1', status: 'deferred' }])).toBe('point:p1')
  expect(firstOpen([{ id: 'context', status: 'approved' }, { id: 'affected', status: 'edited' }])).toBe('context')
  expect(firstOpen([])).toBeNull()
})

test('a blocked accept points at the part that is in the way', () => {
  expect(blockedPart({ key: 'adr.why.unchosen', point: 'P1' }, PARTS)).toBe('point:p1')
  expect(blockedPart({ key: 'adr.why.noDecision' }, [...PARTS, { id: 'decision' }])).toBe('decision')
  expect(blockedPart({ key: 'adr.why.noDecision' }, PARTS)).toBeNull()
  expect(blockedPart({ key: 'adr.why.deferred', point: 'P9' }, PARTS)).toBeNull()
  expect(blockedPart(null, PARTS)).toBeNull()
})

const key = (k, o = {}) => ({ key: k, metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, ...o })

test('a review key is the presentation\'s, never with a modifier, while typing or as the end of a g chord', () => {
  const ctx = { typing: false, options: 2 }
  expect(reviewKey(key('ArrowRight'), ctx)).toEqual({ do: 'next' })
  expect(reviewKey(key('2'), ctx)).toEqual({ do: 'choose', n: 2 })
  expect(reviewKey(key('E', { shiftKey: true }), ctx)).toEqual({ do: 'edit' })          // Shift or Caps Lock
  expect(reviewKey(key('P'), ctx)).toEqual({ do: 'toggle' })
  for (const mod of ['metaKey', 'ctrlKey', 'altKey']) expect(reviewKey(key('a', { [mod]: true }), ctx), mod).toBeNull()
  expect(reviewKey(key('d'), { ...ctx, typing: true })).toBeNull()
  expect(reviewKey(key('d'), { ...ctx, chord: true })).toBeNull()                       // g d goes to Docs, it never defers
  expect(reviewKey(key('3'), ctx)).toBeNull()
  expect(reviewKey(key('Enter'), ctx)).toBeNull()
  expect(reviewKey({}, ctx)).toBeNull()
})

test('a key moves, presents, picks, edits, defers or accepts the part in view', () => {
  const a = inReview()
  const fx = (current, act, ctx = {}) => keyEffect(a, current, act, { present: false, ...ctx })
  expect(fx('drivers', { do: 'next' })).toEqual({ go: 'point:p1' })
  expect(fx('context', { do: 'prev' })).toEqual({ go: 'context' })
  expect(fx('context', { do: 'toggle' })).toEqual({ present: true })
  expect(fx('context', { do: 'toggle' }, { present: true })).toEqual({ present: false })
  expect(fx('context', { do: 'exit' }, { present: true })).toEqual({ present: false })
  expect(fx('context', { do: 'exit' })).toBeNull()
  expect(fx('point:p1', { do: 'choose', n: 2 })).toEqual({ pick: 'B' })
  expect(fx('context', { do: 'choose', n: 1 })).toBeNull()
  expect(fx('context', { do: 'edit' })).toEqual({ edit: 'text' })
  expect(fx('point:p1', { do: 'edit' })).toEqual({ edit: 'rationale' })
  expect(fx('affected', { do: 'edit' })).toBeNull()                                    // computed: nothing to write
  expect(fx('context', { do: 'defer' })).toEqual({ defer: 'part' })
  expect(fx('point:p1', { do: 'defer' })).toEqual({ defer: 'point' })
  expect(fx('affected', { do: 'defer' })).toBeNull()
  expect(fx('context', { do: 'accept' })).toEqual({ go: 'point:p1', blocked: { key: 'adr.why.unchosen', point: 'P1' } })
  expect(fx('context', null)).toBeNull()
})

test('a decided ADR only moves and presents; an ADR ready to accept asks to confirm', () => {
  const done = inReview({ state: { phase: 'accepted' } })
  const fx = (act) => keyEffect(done, 'point:p1', act, { present: false })
  expect(fx({ do: 'next' })).toEqual({ go: 'options' })
  expect(fx({ do: 'toggle' })).toEqual({ present: true })
  for (const act of [{ do: 'choose', n: 1 }, { do: 'edit' }, { do: 'defer' }, { do: 'accept' }]) expect(fx(act), act.do).toBeNull()
  const ready = inReview({ points: [{ id: 'p1', chosen: 'A', options: [] }] })
  expect(keyEffect(ready, 'context', { do: 'accept' }, { present: true })).toEqual({ accept: true })
})

test('only a save the file outran reloads; a busy lock or a refusal keeps its message', () => {
  expect(stale({ status: 409, data: { sha: 'b' } })).toBe(true)
  expect(stale({ status: 409, data: { error: 'another change to this ADR is being saved: try again' } })).toBe(false)
  expect(stale({ status: 400, data: { sha: 'b' } })).toBe(false)
  expect(stale(new Error('offline'))).toBe(false)
  expect(stale(undefined)).toBe(false)
})

test('a choice is the option picked or the one typed, with its one-line why', () => {
  const p = { id: 'p1', options: [{ id: 'A' }, { id: 'B' }] }
  expect(choiceBody(p, { picked: 'B', rationale: '  ya   en uso  ' })).toEqual({ op: 'choose', point: 'p1', chosen: 'B', rationale: 'ya en uso' })
  expect(choiceBody(p, { picked: 'other', other: ' Hazelcast ' })).toEqual({ op: 'choose', point: 'p1', other: 'Hazelcast', rationale: '' })
  expect(choiceBody(p, { picked: 'other', other: '  ' })).toBeNull()
  expect(choiceBody(p, { picked: 'C' })).toBeNull()
  expect(choiceBody(p, {})).toBeNull()
  expect(choiceBody(p, undefined)).toBeNull()
  expect(choiceBody({ ...p, chosen: 'A', rationale: 'kept' }, {})).toEqual({ op: 'choose', point: 'p1', chosen: 'A', rationale: 'kept' })
  expect(choiceBody({ ...p, other: 'Memcached' }, {})).toEqual({ op: 'choose', point: 'p1', other: 'Memcached', rationale: '' })
})

test('a new point needs its question and two named options; pros and cons go one per line', () => {
  expect(newPointBody({ question: ' ¿Dónde? ', options: [{ name: 'Redis', pros: 'ya en uso\n\n rápido ', cons: '' }, { name: ' Postgres ' }, { name: ' ' }] }))
    .toEqual({ op: 'add', question: '¿Dónde?', options: [{ name: 'Redis', pros: ['ya en uso', 'rápido'], cons: [] },
      { name: 'Postgres', pros: [], cons: [] }] })
  expect(newPointBody({ question: '', options: [{ name: 'a' }, { name: 'b' }] })).toBeNull()
  expect(newPointBody({ question: 'q', options: [{ name: 'a' }, { name: '' }] })).toBeNull()
  expect(newPointBody(null)).toBeNull()
})

test('attendees come typed one or several at once, each once whatever its case', () => {
  expect(addAttendees(['LA'], ' MP, Juan Ruiz ,, la ')).toEqual(['LA', 'MP', 'Juan Ruiz'])
  expect(addAttendees(['LA'], 'LA')).toEqual(['LA'])
  expect(addAttendees(undefined, ' ')).toEqual([])
})
