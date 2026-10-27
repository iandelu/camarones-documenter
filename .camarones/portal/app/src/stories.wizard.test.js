import { expect, test } from 'vitest'
import { addDep, addTask, analyzeBody, chipGroups, dropDep, editTask, escapeAborts, footprintOf, initialDraft, mergeDocSources,
  mergeTasks, pickHit, planAnalyze, removeTask, saveBlock, saveBody, taskNames, titleFrom, withChecks } from './stories.js'

// The wizard's pure parts (Stories.jsx): picking files in Toca, the footprint line, the person's edits to the proposed
// tasks and what goes to analyze and save.

test('titleFrom: the want, first letter upper-cased, cut at 80 characters on a word boundary (stories.title_for)', () => {
  expect(titleFrom('  exportar una   página a PDF. ')).toBe('Exportar una página a PDF')
  expect(titleFrom('')).toBe('')
  const got = titleFrom('ver ' + 'informes '.repeat(12))
  expect([...got].length).toBeLessThanOrEqual(80)
  expect(got.endsWith('informes')).toBe(true)
  expect(titleFrom('x'.repeat(90))).toBe('X' + 'x'.repeat(79))         // one long word: cut where it is
  expect(titleFrom('a, b;')).toBe('A, b')
})

test('pickHit: a file or a page adds itself; a group adds its files, never the group; sorted, once each', () => {
  expect(pickHit(['api:b.py'], { touch: 'api:a.py', kind: 'file', group: 'core' })).toEqual(['api:a.py', 'api:b.py'])
  expect(pickHit(['api:a.py'], { touch: 'api:a.py', kind: 'file' })).toEqual(['api:a.py'])
  expect(pickHit([], { touch: 'cam-docs:docs/x.md', kind: 'page', group: 'docs', title: 'X' })).toEqual(['cam-docs:docs/x.md'])
  expect(pickHit(['api:a.py'], { touch: 'api:owners', kind: 'group', group: 'owners', files: ['api:o/2.py', 'api:a.py', 'api:o/1.py'] }))
    .toEqual(['api:a.py', 'api:o/1.py', 'api:o/2.py'])
  expect(pickHit(['api:a.py'], { touch: 'api:empty', kind: 'group', group: 'empty' })).toEqual(['api:a.py'])
})

test('chipGroups: the chips grouped by their code-map group, else repo and folder; pages under docs', () => {
  const groups = { 'api:o/1.py': 'owners', 'api:o/2.py': 'owners', 'api:v/1.py': 'vets' }
  expect(chipGroups(['api:v/1.py', 'api:o/2.py', 'api:o/1.py', 'web:src/app/x.ts', 'cam-docs:docs/a.md', 'api:main.py'], groups)).toEqual([
    { group: 'api', touches: ['api:main.py'] },
    { group: 'docs', touches: ['cam-docs:docs/a.md'] },
    { group: 'owners', touches: ['api:o/1.py', 'api:o/2.py'] },
    { group: 'vets', touches: ['api:v/1.py'] },
    { group: 'web/src/app', touches: ['web:src/app/x.ts'] },
  ])
  expect(chipGroups([], groups)).toEqual([])
})

test('footprintOf: groups, files and repos of the code, pages apart', () => {
  const groups = { 'api:o/1.py': 'owners', 'api:o/2.py': 'owners', 'web:v.ts': 'vets' }
  expect(footprintOf(['api:o/1.py', 'api:o/2.py', 'web:v.ts', 'cam-docs:docs/a.md', 'cam-docs:docs/b.md'], groups))
    .toEqual({ groups: 2, files: 3, repos: 2, pages: 2 })
  expect(footprintOf([], {})).toEqual({ groups: 0, files: 0, repos: 0, pages: 0 })
})

const task = (key, more = {}) => ({ key, kind: 'change', title: key, group: 'g', touches: [`api:${key}.py`], criteria: [], deps: [],
  conflicts: [], wave: 0, edited: false, added: [], dropped: [], ...more })

test('withChecks: the fresh tasks keep the ticks the person left, new ones come ticked', () => {
  const fresh = [task('a'), task('b'), task('c')]
  expect(withChecks(fresh, [{ key: 'a', checked: false }, { key: 'b', checked: true }]).map((t) => t.checked)).toEqual([false, true, true])
  expect(withChecks(fresh, null).every((t) => t.checked)).toBe(true)
})

test('withChecks: unticked tasks were not sent to analyze; they stay on the list, after the others, without a wave', () => {
  const fresh = [task('a', { wave: 1 }), task('c', { wave: 0 })]
  const before = [{ ...task('b', { deps: ['a'], wave: 0 }), checked: false }, { ...task('a'), checked: true }]
  const out = withChecks(fresh, before)
  expect(out.map((t) => [t.key, t.checked, t.wave])).toEqual([['a', true, 1], ['c', true, 0], ['b', false, -1]])
  expect(out[2].deps).toEqual([])
  expect(withChecks([{ ...task('b'), wave: 2 }], before).map((t) => [t.key, t.checked])).toEqual([['b', false]])   // came back
})

test('editTask marks the task edited; deps: ✕ drops a derived one or takes back an added one, + adds', () => {
  const tasks = [task('a', { deps: ['b', 'WI-3'] }), task('b')]
  expect(editTask(tasks, 'a', { title: 'New' })[0]).toMatchObject({ title: 'New', edited: true })
  expect(editTask(tasks, 'a', { title: 'New' })[1]).toBe(tasks[1])
  const dropped = dropDep(tasks, 'a', 'b')[0]
  expect(dropped).toMatchObject({ dropped: ['b'], added: [], edited: true })
  expect(dropped.deps).toEqual(['WI-3'])
  const added = addDep(tasks, 'b', 'a')[1]
  expect(added).toMatchObject({ added: ['a'], dropped: [], edited: true, deps: ['a'] })
  expect(dropDep([added], 'b', 'a')[0]).toMatchObject({ added: [], dropped: [] })       // takes back its own
  expect(addDep([dropped], 'a', 'b')[0]).toMatchObject({ added: [], dropped: [] })      // undoes the drop
  expect(addDep(tasks, 'a', 'a')).toBe(tasks)                                           // never on itself
  expect(addDep(tasks, 'a', 'b')).toBe(tasks)                                           // already a dependency
})

test('removeTask: out of the list, its key in removed, and no one keeps it as an added dependency', () => {
  const draft = { ...initialDraft(null), tasks: [task('a'), task('b', { added: ['a'], deps: ['a'] })], removed: ['z'] }
  const out = removeTask(draft, 'a')
  expect(out.tasks.map((t) => t.key)).toEqual(['b'])
  expect(out.tasks[0]).toMatchObject({ added: [], deps: [] })
  expect(out.removed).toEqual(['z', 'a'])
  expect(removeTask({ ...draft, removed: undefined }, 'a').removed).toEqual(['a'])
})

test('addTask: a hand-made task with its own key, edited, ticked, with or without files', () => {
  const tasks = [task('a'), { ...task('added:2'), edited: true }]
  const out = addTask(tasks, '  Revisar  textos ', ['web:b.ts', 'web:a.ts', 'web:a.ts'])
  expect(out).toHaveLength(3)
  expect(out[2]).toMatchObject({ key: 'added:3', kind: 'change', title: 'Revisar textos', group: '', touches: ['web:a.ts', 'web:b.ts'],
    edited: true, checked: true, added: [], dropped: [], deps: [] })
  expect(addTask([], 'x', [])[0]).toMatchObject({ key: 'added:1', touches: [] })
  expect(addTask(null, 'x')[0]).toMatchObject({ key: 'added:1', touches: [] })
})

test('mergeTasks: one task with both files and criteria; the second goes to removed; their deps on each other go', () => {
  const draft = { ...initialDraft(null), removed: [], tasks: [
    task('a', { criteria: ['c1'], added: ['WI-9'], deps: ['WI-9'] }),
    task('b', { criteria: ['c1', 'c2'], added: ['a', 'WI-4'], deps: ['a', 'WI-4'], touches: ['api:b.py', 'api:a.py'] }),
    task('c', { added: ['b'], deps: ['b'] })] }
  const out = mergeTasks(draft, 'a', 'b')
  expect(out.tasks.map((t) => t.key)).toEqual(['a', 'c'])
  expect(out.tasks[0]).toMatchObject({ touches: ['api:a.py', 'api:b.py'], criteria: ['c1', 'c2'], added: ['WI-9', 'WI-4'], edited: true })
  expect(out.tasks[1]).toMatchObject({ added: ['a'], edited: true })                    // waited for b: now for a
  expect(out.removed).toEqual(['b'])
  expect(mergeTasks(draft, 'a', 'a')).toBe(draft)
  expect(mergeTasks(draft, 'a', 'zz')).toBe(draft)
})

const story = (over = {}) => ({ ...initialDraft(null), as: 'dev', want: 'ver informes', so: 'decidir', title: 'Ver informes',
  criteria: ['Dado x, cuando y, entonces z', '  '], touches: ['api:a.py'], ...over })

test('analyzeBody: the story, the ticked tasks without the screen-only fields, removed (unticked keys too), the language', () => {
  const body = analyzeBody(story({ id: 'WI-7', epic: 'WI-1', removed: ['b'],
    tasks: [{ ...task('a'), checked: true, outside: ['x'] }, { ...task('u', { edited: true }), checked: false }] }), 'es')
  expect(body).toEqual({ lang: 'es', removed: ['b', 'u'],
    story: { id: 'WI-7', as: 'dev', want: 'ver informes', so: 'decidir', criteria: ['Dado x, cuando y, entonces z'], touches: ['api:a.py'], epic: 'WI-1' },
    tasks: [{ key: 'a', kind: 'change', title: 'a', group: 'g', touches: ['api:a.py'], criteria: [], edited: false, added: [], dropped: [] }] })
  expect(analyzeBody(story(), 'en')).toMatchObject({ tasks: [], removed: [], story: { id: null, epic: null } })
})

test('saveBody: only the ticked tasks; a dependency on an unticked one is left out; base_sha and title', () => {
  const tasks = [{ ...task('a'), checked: true, deps: ['b', 'WI-3'] }, { ...task('b'), checked: false }, { ...task('c'), deps: ['a'] }]
  const body = saveBody(story({ id: 'WI-7', sha: 'abcd1234', tasks }))
  expect(body.base_sha).toBe('abcd1234')
  expect(body.title).toBe('Ver informes')
  expect(body.story).toMatchObject({ id: 'WI-7', as: 'dev', touches: ['api:a.py'] })
  expect(body.tasks.map((t) => [t.key, t.deps])).toEqual([['a', ['WI-3']], ['c', ['a']]])
  expect(body.tasks[0]).not.toHaveProperty('checked')
  expect(saveBody(story({ title: '  ' })).title).toBeNull()
  expect(saveBody(story()).base_sha).toBeNull()
})

test('taskNames: titles for the keys of the tasks on screen, the rest as they are', () => {
  expect(taskNames(['change:api:o', 'WI-3', 'x'], [task('change:api:o', { title: ' Owners:  list ' }), task('x', { title: '' })]))
    .toEqual(['«Owners: list»', 'WI-3', 'x'])
  expect(taskNames(undefined, null)).toEqual([])
})

test('saveBlock: why the primary button is off, or null', () => {
  const fine = { hints: [], cycle: [], duplicates: [] }
  const sent = { as: 'dev', want: 'ver informes', so: 'decidir' }
  const d = story({ tasks: [task('a')] })
  expect(saveBlock(d, fine, sent)).toBeNull()
  expect(saveBlock(d, null, null)).toEqual({ key: 'stories.block.pending', vars: {} })
  expect(saveBlock(d, fine, { ...sent, want: 'otra' })).toEqual({ key: 'stories.block.pending', vars: {} })
  expect(saveBlock(d, { ...fine, hints: [{ code: 'empty', field: 'so' }] }, sent)).toEqual({ key: 'stories.block.empty', vars: {} })
  expect(saveBlock(d, { ...fine, cycle: ['a', 'b'] }, sent)).toEqual({ key: 'stories.block.cycle', vars: { keys: '«a» → b' } })
  expect(saveBlock(d, { ...fine, duplicates: ['a'] }, sent)).toEqual({ key: 'stories.block.duplicates', vars: { keys: 'a' } })
  expect(saveBlock(story({ tasks: [task('a', { title: ' ' })] }), fine, sent)).toEqual({ key: 'stories.block.title', vars: { key: 'a' } })
  expect(saveBlock(story({ tasks: [task('a', { title: ' ', checked: false })] }), fine, sent)).toBeNull()   // not saved
})

test('planAnalyze: run on a new body, skip the one on screen; a blank want clears and forgets it, so the same text runs again', () => {
  let last = ''
  const step = (key, want) => { const p = planAnalyze(last, key, want); last = p.last; return p.action }
  expect(step('0|A', 'ver')).toBe('run')
  last = '0|A'                                         // the answer for A came back
  expect(step('0|A', 'ver')).toBe('skip')
  expect(step('0|B', '  ')).toBe('clear')              // the want was emptied
  expect(last).toBe('')
  expect(step('0|A', 'ver')).toBe('run')               // typed back: never stuck on "Revisando…"
  last = '0|A'
  expect(step('1|A', 'ver')).toBe('run')               // the same story opened again: a new nonce
})

test('planAnalyze: a change undone before its answer (A → B → A) skips and is no longer pending', () => {
  // the effect as Stories.jsx runs it: pending follows the plan; an answer only lands when its key is still current
  let last = ''
  let pending = false
  let now = ''
  const effect = (key, want) => { now = key; const p = planAnalyze(last, key, want); last = p.last; pending = p.pending; return p.action }
  const answer = (key) => { if (now === key) { last = key; pending = false } }
  expect(effect('0|A', 'ver')).toBe('run')
  expect(pending).toBe(true)
  answer('0|A')
  expect(effect('0|B', 'verx')).toBe('run')            // a character typed: B goes out (and is aborted below)
  expect(pending).toBe(true)
  expect(effect('0|A', 'ver')).toBe('skip')            // undone before B's answer: A is the one on screen
  expect(pending).toBe(false)                          // Save is not held on "Revisando…"
  answer('0|B')                                        // a late B answer would be dropped
  expect(last).toBe('0|A')
  expect(planAnalyze('', '0|A', '').pending).toBe(false)
})

test('mergeDocSources: an empty footprint starts from the files the linked pages cite, marked as coming from the docs', () => {
  const d = story({ touches: [] })
  const out = mergeDocSources(d, ['api:b.py', 'api:a.py', 'api:b.py'])
  expect(out.touches).toEqual(['api:a.py', 'api:b.py'])
  expect(out.fromDocs).toEqual(['api:a.py', 'api:b.py'])
  expect(mergeDocSources(d, [])).toBe(d)
  expect(mergeDocSources(d, undefined)).toBe(d)
})

test('mergeDocSources: a saved footprint is left as it is (files the person removed and saved do not come back)', () => {
  const saved = story({ id: 'WI-7', touches: ['api:a.py'] })
  expect(mergeDocSources(saved, ['api:b.py', 'api:a.py'])).toBe(saved)
})

test('escapeAborts: Escape while a suggestion runs only stops it; otherwise the page keeps the key', () => {
  const ev = (key) => ({ key, stopped: 0, prevented: 0, stopPropagation() { this.stopped++ }, preventDefault() { this.prevented++ } })
  let stops = 0
  const esc = ev('Escape')
  expect(escapeAborts(esc, true, () => stops++)).toBe(true)
  expect([stops, esc.stopped, esc.prevented]).toEqual([1, 1, 1])
  const idle = ev('Escape')
  expect(escapeAborts(idle, false, () => stops++)).toBe(false)
  const other = ev('Enter')
  expect(escapeAborts(other, true, () => stops++)).toBe(false)
  expect([stops, idle.stopped, other.stopped]).toEqual([1, 0, 0])
})
