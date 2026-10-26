import { expect, test } from 'vitest'
import { parse, resolve } from './router.js'

// Characterization of the address table legacy/app.js routeNow() had: every address keeps landing where it did.
const space = { 'repos/api/wiki/intro.md': 'wiki', 'guides/a.md': 'docs' }
const ctx = (over = {}) => ({
  mode: 'live', current: '',
  space: (p) => space[p],
  hrefFor: (p, a) => `#/wiki/${p.split('/')[1]}/${p.split('/').slice(2).join('/')}${a ? '::' + a : ''}`,
  firstView: (zone) => ({ arch: '#/c4', plan: '#/pipeline', quality: '#/kpis' }[zone]),
  ...over,
})
const go = (hash, over) => resolve(hash, ctx(over))
const HOME = { kind: 'native', view: 'home', arg: '' }
const DOC = (arg) => ({ kind: 'native', view: 'doc', arg })

test('parse splits the view from the rest and decodes it', () => {
  expect(parse('#/docs/guides/a b.md::x')).toEqual({ view: 'docs', rest: 'guides/a b.md::x' })
  expect(parse('#/docs/guides/a%20b.md')).toEqual({ view: 'docs', rest: 'guides/a b.md' })
  expect(parse('#/docs/100%.md')).toEqual({ view: 'docs', rest: '100%.md' })          // a bare % routes as it is
  expect(parse('')).toEqual({ view: '', rest: '' })
  expect(parse('#/')).toEqual({ view: '', rest: '' })
})

test('home: the root, an unknown address', () => {
  expect(go('')).toEqual(HOME)
  expect(go('#/')).toEqual(HOME)
  expect(go('#/nope')).toEqual(HOME)
})

test('the React views need the server; in the export they fall back to home', () => {
  for (const v of ['pipeline', 'ask', 'kpis', 'ci', 'libs', 'data', 'interview', 'sync', 'health']) {
    expect(go(`#/${v}/x`)).toEqual({ kind: 'native', view: v, arg: 'x' })
    expect(go(`#/${v}`, { mode: 'static' })).toEqual(HOME)
  }
  expect(go('#/ask/how%20does%20it%20work')).toEqual({ kind: 'native', view: 'ask', arg: 'how does it work' })
  // the Board's add form, opened from a page with its link filled in
  expect(go('#/kanban/new?path=domain%2Fvisits.md&section=the-flow'))
    .toEqual({ kind: 'native', view: 'kanban', arg: 'new?path=domain/visits.md&section=the-flow' })
})

test('Salud: live-only, the per-repo page rides on the argument', () => {
  expect(go('#/health')).toEqual({ kind: 'native', view: 'health', arg: '' })
  expect(go('#/health/api')).toEqual({ kind: 'native', view: 'health', arg: 'api' })
  expect(go('#/health', { mode: 'static' })).toEqual(HOME)
})

// The Taller left the portal in 4.53: in the app its old addresses open the app's own section, in a browser home.
test('the Taller\'s old addresses open the desktop app\'s sections', () => {
  const app = { generate: 'plan', analyze: 'quality', check: 'quality', interviews: 'interviews', team: 'team',
    machine: 'machine', kitdev: 'kitdev', taller: 'summary' }
  for (const [old, section] of Object.entries(app)) {
    expect(go(`#/${old}`, { mode: 'app' })).toEqual({ kind: 'redirect', to: `./desktop/#/${section}` })
    expect(go(`#/${old}`)).toEqual(HOME)
    expect(go(`#/${old}`, { mode: 'static' })).toEqual(HOME)
  }
})

test('docs: home, a page, an anchor, the old #/doc alias', () => {
  expect(go('#/docs')).toEqual({ kind: 'native', view: 'docs', arg: '' })
  expect(go('#/docs/guides/a.md')).toEqual(DOC('guides/a.md'))
  expect(go('#/docs/guides/a.md::setup')).toEqual(DOC('guides/a.md::setup'))
  expect(go('#/doc/guides/a.md')).toEqual(DOC('guides/a.md'))
})

test('docs: an anchor on the page already shown only scrolls', () => {
  expect(go('#/docs/guides/a.md::setup', { current: 'guides/a.md' })).toEqual({ kind: 'scroll', anchor: 'setup' })
  expect(go('#/docs/guides/a.md', { current: 'guides/a.md' })).toEqual(DOC('guides/a.md'))
})

test('docs: a wiki page under #/docs moves to its wiki address', () => {
  expect(go('#/docs/repos/api/wiki/intro.md::a')).toEqual({ kind: 'redirect', to: '#/wiki/api/wiki/intro.md::a' })
})

test('wikis: the list, a repo graph, a page, an anchor on the page shown', () => {
  expect(go('#/wiki')).toEqual({ kind: 'native', view: 'wikis', arg: '' })
  expect(go('#/wikis')).toEqual({ kind: 'native', view: 'wikis', arg: '' })
  expect(go('#/wikis/api')).toEqual({ kind: 'redirect', to: '#/wiki/api' })
  expect(go('#/wiki/api')).toEqual({ kind: 'native', view: 'wikigraph', arg: 'api' })
  expect(go('#/wiki/api/wiki/intro.md')).toEqual({ kind: 'native', view: 'wikipage', arg: 'api/wiki/intro.md' })
  expect(go('#/wiki/api/wiki/intro.md::b')).toEqual({ kind: 'native', view: 'wikipage', arg: 'api/wiki/intro.md::b' })
  expect(go('#/wikis', { mode: 'static' })).toEqual({ kind: 'native', view: 'wikis', arg: '' })
  expect(go('#/wiki/api/wiki/intro.md::b', { current: 'repos/api/wiki/intro.md' })).toEqual({ kind: 'scroll', anchor: 'b' })
})

test('architecture, code, review, search, new page, zone covers', () => {
  expect(go('#/c4')).toEqual({ kind: 'native', view: 'c4', arg: '' })
  expect(go('#/c4/index')).toEqual({ kind: 'native', view: 'c4', arg: 'index' })
  expect(go('#/c4', { mode: 'static' })).toEqual({ kind: 'native', view: 'c4', arg: '' })
  expect(go('#/code/api')).toEqual({ kind: 'native', view: 'code', arg: 'api' })
  expect(go('#/code', { mode: 'static' })).toEqual({ kind: 'native', view: 'code', arg: '' })
  expect(go('#/c4/code/api')).toEqual({ kind: 'redirect', to: '#/code/api/graph' })        // the old address of graphify's page
  expect(go('#/c4/code')).toEqual({ kind: 'redirect', to: '#/code/all/graph' })
  expect(go('#/review')).toEqual({ kind: 'native', view: 'review', arg: '' })
  expect(go('#/status')).toEqual({ kind: 'native', view: 'review', arg: '' })
  expect(go('#/review', { mode: 'static' })).toEqual({ kind: 'native', view: 'review', arg: '' })   // read-only there
  expect(go('#/search/visit%20form')).toEqual({ kind: 'native', view: 'search', arg: 'visit form' })
  expect(go('#/search/x', { mode: 'static' })).toEqual({ kind: 'native', view: 'search', arg: 'x' })   // the export searches too
  expect(go('#/new')).toEqual({ kind: 'native', view: 'new', arg: '' })
  expect(go('#/new', { mode: 'static' })).toEqual(HOME)
})

// The sidebar lists every zone's views, so a zone's address opens its first view (no cover page since phase 1).
test('a zone address opens its first view; a zone this mode lacks goes home', () => {
  expect(go('#/arch')).toEqual({ kind: 'redirect', to: '#/c4' })
  expect(go('#/plan')).toEqual({ kind: 'redirect', to: '#/pipeline' })
  expect(go('#/quality')).toEqual({ kind: 'redirect', to: '#/kpis' })
  expect(go('#/quality', { mode: 'static', firstView: () => undefined })).toEqual(HOME)
})

test('boards were removed in 4.49: their addresses land on Architecture', () => {
  expect(go('#/boards')).toEqual({ kind: 'redirect', to: '#/arch' })
  expect(go('#/boards/flows')).toEqual({ kind: 'redirect', to: '#/arch' })
})
