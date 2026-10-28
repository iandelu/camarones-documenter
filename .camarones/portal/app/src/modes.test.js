import { readdirSync, readFileSync } from 'node:fs'
import { expect, test } from 'vitest'
import { STRINGS } from './i18n.js'
import { I18N } from './i18n/portal.js'

// The desktop app never shows the portal in its window (desktop/main.cjs guard() opens it in the system browser), so
// the portal is live or static: no view keeps a branch, a button or a string for the app's window.
const sources = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory()
  ? sources(new URL(`${e.name}/`, dir))
  : /\.(jsx?|css)$/.test(e.name) && !e.name.includes('.test.') ? [new URL(e.name, dir)] : []))
const files = sources(new URL('./', import.meta.url))

test('no source keeps a branch for the desktop app\'s window', () => {
  expect(files.length).toBeGreaterThan(40)
  for (const f of files) {
    const src = readFileSync(f, 'utf-8')
    expect(src, f.pathname).not.toMatch(/AppOnly|camaronApp|\bRUNS\b|\bAPP\b|[!=]== 'app'|\bruns\(\)|in-app|-webkit-app-region|\.\/desktop\//)
  }
})

test('the portal calls no endpoint only the desktop app may (lib/serve.py APP_ONLY)', () => {
  for (const f of files) {
    const src = readFileSync(f, 'utf-8')
    expect(src, f.pathname).not.toMatch(/postJSON\(['`](runs|wiki|build|inventory|schemas|ci|ask\/answer|plan\/cost)['`/]/)
  }
})

test('the strings only the app\'s window showed are gone, in both languages', () => {
  const gone = ['appMenu', 'shell.app', 'pInApp', 'firstLook', 'home.firstLook', 'home.firstLookFailed', 'build', 'rebuild',
    'noGraphify', 'c4Saved', 'c4Redrawing', 'generate', 'update', 'via', 'graphBuilding', 'graphFailed', 'notChosen',
    'needBrief', 'noEngine', 'noEngine.off', 'noEngine.missing', 'running', 'done', 'failed', 'jobStarted',
    'aiAnswer', 'aiBusy', 'aiBy', 'aiCheck', 'aiNone', 'dataWrite', 'ciGenerate', 'ciRegenerate', 'ciOther', 'ciNoPush',
    'libsScan', 'libsRefresh', 'libsScanning', 'libsRefreshing']
  for (const dict of [STRINGS, I18N]) for (const l of ['en', 'es']) for (const k of gone) expect(dict[l][k], `${l}.${k}`).toBeUndefined()
  for (const l of ['en', 'es']) expect(I18N[l].c4SavedNoBuild, l).toBeTruthy()             // an edit still says how it is redrawn
})
