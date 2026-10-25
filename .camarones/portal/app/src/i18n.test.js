import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'
import { STRINGS } from './i18n.js'

// The React views' strings (src/i18n.js), both languages: every key in each.
test('every string exists in en and es', () => {
  expect(Object.keys(STRINGS.es).sort()).toEqual(Object.keys(STRINGS.en).sort())
})

// The Pipeline was the last view with English written into it: its words come from the dictionary now.
test('the Pipeline says everything through the dictionary', () => {
  const src = readFileSync(new URL('./Pipeline.jsx', import.meta.url), 'utf-8')
  const used = [...src.matchAll(/\bt\('([\w.-]+)'/g)].map((m) => m[1])
  expect(used.length).toBeGreaterThan(20)
  expect(used.filter((k) => !(k in STRINGS.en) || !(k in STRINGS.es))).toEqual([])
  for (const literal of ['To do', 'Loading…', 'Live log', 'Nothing yet in this run.', 'awaiting approval', 'own copy',
    'Retry this unit', "'Graph'", "'Board'", 'units done', 'not answering', 'aria-label="Close"', 'phase {u.phase}'])
    expect(src, literal).not.toContain(literal)
})

test('the run line and the counts keep their placeholders in both languages', () => {
  for (const l of ['en', 'es']) {
    expect(STRINGS[l]['pipe.count']).toMatch(/\{done\}.*\{total\}/)
    for (const k of ['pipe.runDone', 'pipe.runNow']) expect(STRINGS[l][k], `${l}.${k}`).toContain('{run}')
    expect(STRINGS[l]['pipe.phase']).toContain('{n}')
  }
})
