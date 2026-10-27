import { readFileSync } from 'node:fs'
import { afterEach, expect, test, vi } from 'vitest'
import CASES from '../../../../tests/fixtures/story_lint_cases.json'
import { I18N } from './i18n/portal.js'
import { draftKey, initialDraft, lint, loadDraft, nextStep, outdated, primaryLabel, saveDraft } from './stories.js'

// The word lists the server sends in GET /api/stories → lint_words: the kit's YAML files, written in JSON syntax.
const words = (lang) => JSON.parse(readFileSync(new URL(`../../../templates/board/${lang}/story-lint.yaml`, import.meta.url), 'utf-8'))
const WORDS = { es: words('es'), en: words('en') }

test('lint gives the same codes, in the same order, as the Python lint for every row of the shared table', () => {
  expect(CASES.length).toBeGreaterThan(30)
  for (const row of CASES) {
    const got = lint(row.as, row.want, row.so, row.lang, WORDS[row.lang], row.touches).map((h) => h.code)
    expect(got, `${row.lang}: ${row.as} / ${row.want} / ${row.so}`).toEqual(row.codes)
  }
})

test('each hint says which field it is about', () => {
  const hints = lint('', 'x', 'y', 'en', WORDS.en, [])
  expect(hints).toEqual([{ code: 'empty', field: 'as' }, { code: 'no-footprint', field: 'touches' }])
  const all = lint('user', 'add a button and export reports', 'export reports quickly', 'en', WORDS.en, [])
  expect(Object.fromEntries(all.map((h) => [h.code, h.field])))
    .toEqual({ 'generic-role': 'as', 'two-goals': 'want', 'so-repeats-want': 'so', 'solution-in-want': 'want', 'no-footprint': 'touches' })
})

test('lint tolerates missing word lists and blank touches', () => {
  expect(lint('dev', 'exportar y ver informes', 'compartir', 'es', {}, ['', null]).map((h) => h.code)).toEqual(['no-footprint'])
  expect(lint('dev', 'export', 'share', 'en', undefined, ['portal:a.py'])).toEqual([])
})

test('the short function words and the Spanish nouns are not second goals', () => {
  const ok = (lang, want) => lint('dev', want, 'compartir con el equipo', lang, WORDS[lang], ['a:b']).map((h) => h.code)
  expect(ok('en', 'see a list of invoices and a summary of payments')).toEqual([])
  expect(ok('en', 'export the report and send it')).toEqual(['two-goals'])
  expect(ok('es', 'exportar y ver informes')).toEqual(['two-goals'])
  expect(ok('es', 'revisar el arte y la parte final')).toEqual([])
})

const draft = (over = {}) => ({ ...initialDraft(null), as: 'dev', want: 'ver informes', so: 'decidir mejor', ...over })

test('initialDraft: empty for a new story, filled from an item', () => {
  expect(initialDraft(null)).toEqual({ id: null, sha: null, as: '', want: '', so: '', title: '', epic: '', criteria: [], touches: [],
    tasks: null, step: 1 })
  const item = { id: 'WI-7', title: 'Ver informes', as_: 'dev', want: 'ver informes', so: 'decidir', criteria: ['Dado x'],
    touches: ['api:a.py'], epic: 'WI-1', sha: 'abcd1234', rest: 'notes', priority: 'P1' }
  expect(initialDraft(item)).toEqual({ id: 'WI-7', sha: 'abcd1234', as: 'dev', want: 'ver informes', so: 'decidir',
    title: 'Ver informes', epic: 'WI-1', criteria: ['Dado x'], touches: ['api:a.py'], tasks: null, step: 1 })
  expect(initialDraft({ id: 'WI-8' })).toMatchObject({ id: 'WI-8', as: '', criteria: [], touches: [], epic: '' })
})

test('initialDraft copies the lists so editing the draft never edits the item', () => {
  const item = { id: 'WI-7', criteria: ['a'], touches: ['b:c'] }
  const d = initialDraft(item)
  d.criteria.push('z'); d.touches.push('z:z')
  expect(item).toEqual({ id: 'WI-7', criteria: ['a'], touches: ['b:c'] })
})

test('nextStep: 1 until the story has its three parts, then one step on, held back by a cycle or duplicates', () => {
  const fine = { hints: [{ code: 'no-footprint', field: 'touches' }], cycle: [], duplicates: [] }
  expect(nextStep(draft(), null)).toBe(1)
  expect(nextStep(draft(), { hints: [{ code: 'empty', field: 'so' }] })).toBe(1)
  expect(nextStep(draft({ step: 2 }), { hints: [{ code: 'empty', field: 'so' }] })).toBe(1)
  expect(nextStep(draft(), fine)).toBe(2)
  expect(nextStep(draft({ step: 2 }), fine)).toBe(3)
  expect(nextStep(draft({ step: 3 }), fine)).toBe(3)
  expect(nextStep(draft({ step: 2 }), { ...fine, cycle: ['a', 'b'] })).toBe(2)
  expect(nextStep(draft({ step: 2 }), { ...fine, duplicates: ['a'] })).toBe(2)
})

test('outdated: the analysis is stale only when the text changed, not for spacing or case', () => {
  const analysed = { as: 'dev', want: 'ver informes', so: 'decidir mejor' }
  expect(outdated(draft(), analysed)).toBe(false)
  expect(outdated(draft({ as: '  Dev ', want: 'ver   INFORMES' }), analysed)).toBe(false)
  expect(outdated(draft({ want: 'ver facturas' }), analysed)).toBe(true)
  expect(outdated(draft(), null)).toBe(true)
  expect(outdated(draft(), undefined)).toBe(true)
  // a boundary between clauses is not a space: moving a word across it is a change
  expect(outdated(draft({ as: 'dev ver', want: 'informes' }), { as: 'dev', want: 'ver informes', so: 'decidir mejor' })).toBe(true)
})

const T = (key, vars) => I18N.en[key].replace(/\{(\w+)\}/g, (_, v) => vars[v])

test('primaryLabel: new story or an existing one, and how many tasks are checked', () => {
  const tasks = [{ key: 'a', checked: true }, { key: 'b', checked: false }, { key: 'c' }]
  expect(primaryLabel(draft({ tasks }), T)).toBe(T('stories.save.new', { n: 2 }))
  expect(primaryLabel(draft({ id: 'WI-7', tasks }), T)).toBe(T('stories.save.existing', { id: 'WI-7', n: 2 }))
  expect(primaryLabel(draft({ tasks: null }), T)).toBe(T('stories.save.new', { n: 0 }))
  const calls = []
  primaryLabel(draft({ id: 'WI-7', tasks }), (key, vars) => { calls.push([key, vars]); return '' })
  expect(calls).toEqual([['stories.save.existing', { id: 'WI-7', n: 2 }]])
})

afterEach(() => vi.unstubAllGlobals())

test('drafts are kept per story in localStorage and read back', () => {
  const store = new Map()
  vi.stubGlobal('localStorage', { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) })
  expect(draftKey(null)).toBe('cam-story-draft:new')
  expect(draftKey('WI-7')).toBe('cam-story-draft:WI-7')
  expect(loadDraft(draftKey('WI-7'))).toBeNull()
  expect(saveDraft(draftKey('WI-7'), draft({ id: 'WI-7' }))).toBe(true)
  expect(loadDraft('cam-story-draft:WI-7')).toEqual(draft({ id: 'WI-7' }))
  store.set('cam-story-draft:bad', '{nope')
  expect(loadDraft('cam-story-draft:bad')).toBeNull()
  store.set('cam-story-draft:num', '42')
  expect(loadDraft('cam-story-draft:num')).toBeNull()
})

test('a localStorage that throws (private mode, quota, blocked) never breaks the wizard', () => {
  const boom = () => { throw new Error('denied') }
  vi.stubGlobal('localStorage', { getItem: boom, setItem: boom })
  expect(saveDraft('cam-story-draft:new', draft())).toBe(false)
  expect(loadDraft('cam-story-draft:new')).toBeNull()
  vi.unstubAllGlobals()
  vi.stubGlobal('localStorage', undefined)
  expect(saveDraft('cam-story-draft:new', draft())).toBe(false)
  expect(loadDraft('cam-story-draft:new')).toBeNull()
})

const KEYS = ['zone.stories', 'zoned.stories', 'view.stories', 'viewd.stories', 'stories.step.1', 'stories.step.2', 'stories.step.3',
  ...['empty', 'generic-role', 'two-goals', 'so-repeats-want', 'too-long', 'solution-in-want', 'no-footprint'].map((c) => `stories.hint.${c}`),
  'stories.verdict.good', 'stories.verdict.improve', 'stories.verdict.poor',
  ...[...'INVEST'].map((l) => `stories.invest.${l}`),
  'stories.save.new', 'stories.save.existing', 'stories.saved', 'stories.readonly', 'stories.graphless', 'stories.conflict',
  'stories.ai.suggest']

test('every Historias string exists in es and en, with the same placeholders', () => {
  const ph = (s) => (s.match(/\{\w+\}/g) || []).sort()
  for (const k of KEYS) {
    expect(I18N.en[k], `en.${k}`).toBeTruthy()
    expect(I18N.es[k], `es.${k}`).toBeTruthy()
    expect(ph(I18N.es[k]), k).toEqual(ph(I18N.en[k]))
  }
  for (const l of ['en', 'es']) {
    expect(I18N[l]['stories.save.new']).toContain('{n}')
    expect(I18N[l]['stories.save.existing']).toContain('{id}')
    expect(I18N[l]['stories.save.existing']).toContain('{n}')
  }
})

test('the Spanish hints say what the Python lint says', () => {
  const py = readFileSync(new URL('../../../lib/stories.py', import.meta.url), 'utf-8')
  for (const code of ['empty', 'generic-role', 'two-goals', 'so-repeats-want', 'solution-in-want', 'no-footprint']) {
    const m = py.match(new RegExp(String.raw`\("es", "${code}"\): "((?:[^"\\]|\\.)*)"`))
    expect(m, code).not.toBeNull()
    expect(I18N.es[`stories.hint.${code}`], code).toBe(JSON.parse(`"${m[1]}"`))
  }
})
