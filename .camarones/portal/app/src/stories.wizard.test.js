import { expect, test } from 'vitest'
import { addDep, addTask, analyzeBody, chipGroups, dropDep, editTask, footprintOf, initialDraft, mergeTasks, pickHit,
  removeTask, saveBlock, saveBody, taskNames, titleFrom, withChecks } from './stories.js'

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

test('withChecks: a proposal whose files the story\'s subtasks on the board already cover comes unticked', () => {
  const fresh = [task('a'), task('b', { touches: ['api:b.py', 'api:c.py'] }), task('n', { touches: [] })]
  const onBoard = [{ id: 'WI-5', touches: ['api:a.py', 'api:b.py'] }, { id: 'WI-6', touches: null }]
  expect(withChecks(fresh, null, onBoard).map((t) => t.checked)).toEqual([false, true, true])
  expect(withChecks(fresh, [{ key: 'a', checked: true }], onBoard)[0].checked).toBe(true)      // the person's tick wins
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

test('analyzeBody: the story, the tasks without the screen-only fields, removed and the language', () => {
  const body = analyzeBody(story({ id: 'WI-7', epic: 'WI-1', tasks: [{ ...task('a'), checked: false, outside: ['x'] }], removed: ['b'] }), 'es')
  expect(body).toEqual({ lang: 'es', removed: ['b'],
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
