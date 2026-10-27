import { readdirSync, readFileSync } from 'node:fs'
import { expect, test } from 'vitest'
import { STRINGS } from './i18n.js'
import { I18N } from './i18n/portal.js'

// Historias reads its strings through core.t (i18n/portal.js); the Board through i18n.js's t. Every key either view
// names, literally or built from a known set, must exist in es and en of the dictionary that view reads.
const src = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf-8')
const storyFiles = ['./Stories.jsx', ...readdirSync(new URL('./stories/', import.meta.url)).filter((f) => f.endsWith('.jsx'))
  .map((f) => `./stories/${f}`)]
const literal = (text, fn) => [...text.matchAll(new RegExp(`\\b${fn}\\('([\\w.-]+)'`, 'g'))].map((m) => m[1])
const ph = (s) => (String(s).match(/\{\w+\}/g) || []).sort()

const built = [
  ...['good', 'improve', 'poor'].flatMap((v) => [`stories.verdict.${v}`, `stories.verdict.short.${v}`]), 'stories.verdict.short.none',
  ...[...'INVEST'].map((l) => `stories.invest.${l}`),
  ...['groups', 'files', 'repos', 'pages'].flatMap((k) => [`stories.fp.${k}.one`, `stories.fp.${k}.many`]),
  'stories.task.files.one', 'stories.task.files.many',
  ...['empty', 'generic-role', 'two-goals', 'so-repeats-want', 'too-long', 'solution-in-want', 'no-footprint'].map((c) => `stories.hint.${c}`),
  ...['pending', 'empty', 'cycle', 'duplicates', 'title'].map((b) => `stories.block.${b}`),
  ...['file', 'group', 'page', 'conflict', 'near'].map((k) => `stories.kind.${k}`),
  ...['as', 'want', 'so'].map((k) => `stories.${k}.ph`),
]

test('every string the Historias screen uses exists in es and en (i18n/portal.js), with the same placeholders', () => {
  const used = [...new Set([...storyFiles.flatMap((f) => literal(src(f), 't')), ...built])]
  expect(used.length).toBeGreaterThan(60)
  for (const k of used) {
    expect(I18N.en[k], `en.${k}`).toBeTruthy()
    expect(I18N.es[k], `es.${k}`).toBeTruthy()
    expect(ph(I18N.es[k]), k).toEqual(ph(I18N.en[k]))
  }
})

test('every string the Board uses exists in es and en (i18n.js), the wave, gate and parent marks too', () => {
  const kinds = ['conflict', 'dependency', 'missing'].map((k) => `kanban.kind.${k}`)
  const used = [...new Set([...literal(src('./Kanban.jsx'), 't'), ...literal(src('./Kanban.jsx'), 'fmt'), ...kinds])]
  for (const k of ['kanban.wave', 'kanban.blocked', 'kanban.force', 'kanban.forceAsk', 'kanban.sub', 'kanban.parent']) expect(used).toContain(k)
  for (const k of used) {
    expect(STRINGS.en[k], `en.${k}`).toBeTruthy()
    expect(STRINGS.es[k], `es.${k}`).toBeTruthy()
    expect(ph(STRINGS.es[k]), k).toEqual(ph(STRINGS.en[k]))
  }
  for (const k of ['kanban.wave', 'kanban.blocked', 'kanban.force']) expect(I18N.en[k], `moved: ${k}`).toBeUndefined()
  expect(STRINGS.es['kanban.force']).toBe('Mover igualmente')
})

test('the copy the design agreed on, word for word', () => {
  expect(I18N.es['stories.saved']).toBe('{id} y {n} subtareas añadidas')
  expect(I18N.es['stories.conflict']).toBe('{id} ha cambiado mientras la editabas: recárgala')
  expect(I18N.es['stories.ai.nothing']).toBe('La IA no ha propuesto nada nuevo')
  expect(I18N.es['stories.task.nofiles']).toBe('sin archivos: cuenta como todo el repo para los agentes')
  expect(I18N.en['stories.task.nofiles']).toBe('no files: counts as the whole repo for agents')
  expect(I18N.es['stories.criteria.ph']).toMatch(/^Dado … cuando … entonces/)
  expect(['Bien', 'Mejorable', 'Mal', 'Sin revisar']).toEqual(['good', 'improve', 'poor', 'none'].map((v) => I18N.es[`stories.verdict.short.${v}`]))
})
