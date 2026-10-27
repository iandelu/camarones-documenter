import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from 'vitest'
import { machineLang, S, setLang, t } from './i18n.js'

test('every key a component names exists', () => {
  const src = fileURLToPath(new URL('.', import.meta.url))
  const files = readdirSync(src, { recursive: true }).filter((f) => /\.(jsx|js)$/.test(f) && !/\.test\./.test(f))
  const used = new Set(files.flatMap((f) => [...readFileSync(join(src, f), 'utf-8').matchAll(/\bt\('([\w.-]+)'\s*[,)]/g)].map((m) => m[1])))
  expect([...used].filter((k) => !(k in S.es))).toEqual([])
  const families = { grp: ['awaiting', 'blocked', 'doing', 'ready', 'waiting', 'done'], job: ['running', 'done', 'failed', 'stopped'],
    nav: ['summary', 'board', 'decisions', 'plan', 'interviews', 'team', 'quality', 'libs', 'docs', 'machine', 'kitdev'], fr: ['suspect', 'stale'],
    'lb.scope': ['runtime', 'dev', 'test', 'build'],
    bl: ['created', 'updated', 'edited', 'human'], sev: ['critical', 'high', 'medium', 'moderate', 'low', 'unknown'],
    tk: ['mcp', 'hook', 'setting', 'codex', 'skill', 'file', 'plugin'], ts: ['new', 'changed'],      // lib/trust.py
    pk: ['checks', 'exporters', 'hooks', 'mcp', 'pipelines', 'prompts', 'runners', 'skills', 'types'],     // harness/plugins.py KINDS
    'adr.chip': ['running', 'review', 'proposed', 'accepted', 'superseded', 'rejected', 'deprecated', 'unknown'],   // lib/adr.py CHIPS
    'adr.step': ['problem', 'evidence', 'research', 'synthesis', 'review', 'accepted', 'rejected'], 'adr.filter': ['all', 'running', 'review', 'accepted', 'superseded'],
    'adr.why': ['deferred', 'unchosen', 'noDecision'], 'adr.kind': ['new', 'retro'],
    'adr.sec': ['context', 'drivers', 'options', 'decision', 'consequences', 'confirmation', 'diagram', 'evidence', 'decided_by'],
    'adr.cat': ['data', 'cache', 'messaging', 'security', 'framework', 'deploy', 'c4'],   // lib/adr_pack.py CATEGORIES + deploy, c4
    'adr.pack': ['files', 'neighbours', 'pages', 'adrs', 'commits', 'c4', 'libraries', 'questions'].flatMap((p) => [`${p}.one`, `${p}.many`]) }
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

// The hub and every project window speak the language picked on this machine (main.cjs reads ~/.camarones.json).
test('the language comes from the hub or from a project window, else Spanish', async () => {
  expect(await machineLang({ camaronHub: { lang: async () => 'en' } })).toBe('en')
  expect(await machineLang({ camaronApp: { token: 't', lang: async () => 'en' } })).toBe('en')
  expect(await machineLang({ camaronApp: { token: 't' } })).toBe('es')              // a main process without it
  expect(await machineLang({ camaronApp: { lang: async () => { throw new Error('gone') } } })).toBe('es')
  expect(await machineLang(undefined)).toBe('es')
})

// AGENTS §3: no jargon the user has not met (the Taller is gone; runner, worktree and drift stay in the code).
test('no string says runner, worktree, drift or Taller', () => {
  for (const l of ['es', 'en']) for (const [k, v] of Object.entries(S[l]))
    expect(v, `${l}.${k}`).not.toMatch(/runner|worktree|\bdrift|Taller|Workshop/i)
})
