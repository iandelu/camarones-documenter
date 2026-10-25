import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from 'vitest'
import { S, setLang, t } from './i18n.js'

test('every key a component names exists', () => {
  const src = fileURLToPath(new URL('.', import.meta.url))
  const files = readdirSync(src, { recursive: true }).filter((f) => /\.(jsx|js)$/.test(f) && !/\.test\./.test(f))
  const used = new Set(files.flatMap((f) => [...readFileSync(join(src, f), 'utf-8').matchAll(/\bt\('([\w.-]+)'\s*[,)]/g)].map((m) => m[1])))
  expect([...used].filter((k) => !(k in S.es))).toEqual([])
  const families = { grp: ['awaiting', 'blocked', 'doing', 'ready', 'waiting', 'done'], job: ['running', 'done', 'failed', 'stopped'],
    nav: ['summary', 'plan', 'interviews', 'team', 'quality', 'docs', 'machine', 'kitdev'], fr: ['suspect', 'stale'],
    bl: ['created', 'updated', 'edited', 'human'], sev: ['critical', 'high', 'medium', 'moderate', 'low', 'unknown'] }
  for (const [f, ks] of Object.entries(families)) for (const k of ks) expect(S.es[`${f}.${k}`], `${f}.${k}`).toBeTruthy()
})

test('every string exists in es and en, and draws no emoji', () => {
  expect(Object.keys(S.en).sort()).toEqual(Object.keys(S.es).sort())
  for (const l of ['es', 'en']) for (const [k, v] of Object.entries(S[l]))
    expect(v.match(/\p{Extended_Pictographic}/u), `${l}.${k}`).toBeNull()
})

test('the language falls back to Spanish and fills placeholders', () => {
  setLang('en')
  expect(t('hub.opening', { name: 'api' })).toBe('Opening api…')
  setLang('fr')
  expect(t('nav.summary')).toBe('Resumen')
  expect(t('nope')).toBe('nope')
})
