import { expect, test } from 'vitest'
import { parse, resolve } from './router.js'

// Characterization of the address table legacy/app.js routeNow() had: every address keeps landing where it did.
const space = { 'repos/api/wiki/intro.md': 'wiki', 'guides/a.md': 'docs' }
const ctx = (over = {}) => ({
  mode: 'live', current: '',
  space: (p) => space[p],
  hrefFor: (p, a) => `#/wiki/${p.split('/')[1]}/${p.split('/').slice(2).join('/')}${a ? '::' + a : ''}`,
  ...over,
})
const go = (hash, over) => resolve(hash, ctx(over))
const legacy = (fn, ...args) => ({ kind: 'legacy', fn, args })

test('parse splits the view from the rest and decodes it', () => {
  expect(parse('#/docs/guides/a b.md::x')).toEqual({ view: 'docs', rest: 'guides/a b.md::x' })
  expect(parse('#/docs/guides/a%20b.md')).toEqual({ view: 'docs', rest: 'guides/a b.md' })
  expect(parse('#/docs/100%.md')).toEqual({ view: 'docs', rest: '100%.md' })          // a bare % routes as it is
  expect(parse('')).toEqual({ view: '', rest: '' })
  expect(parse('#/')).toEqual({ view: '', rest: '' })
})

test('home: the root, an unknown address', () => {
  expect(go('')).toEqual(legacy('showStart'))
  expect(go('#/')).toEqual(legacy('showStart'))
  expect(go('#/nope')).toEqual(legacy('showStart'))
})

test('the React views need the server; in the export they fall back to home', () => {
  for (const v of ['pipeline', 'ask', 'kpis', 'ci', 'libs', 'data', 'interview', 'sync']) {
    expect(go(`#/${v}/x`)).toEqual({ kind: 'native', view: v, arg: 'x' })
    expect(go(`#/${v}`, { mode: 'static' })).toEqual(legacy('showStart'))
  }
  expect(go('#/ask/how%20does%20it%20work')).toEqual({ kind: 'native', view: 'ask', arg: 'how does it work' })
})

test('the Taller only in the desktop app', () => {
  for (const v of ['generate', 'analyze', 'check', 'interviews', 'team', 'machine', 'kitdev']) {
    expect(go(`#/${v}`, { mode: 'app' })).toEqual({ kind: 'native', view: v, arg: '' })
    expect(go(`#/${v}`)).toEqual(legacy('showStart'))
  }
  expect(go('#/taller', { mode: 'app' })).toEqual(legacy('showZone', 'taller'))
})

test('docs: home, a page, an anchor, the old #/doc alias', () => {
  expect(go('#/docs')).toEqual(legacy('showDocsHome'))
  expect(go('#/docs/guides/a.md')).toEqual(legacy('showDoc', 'guides/a.md', undefined))
  expect(go('#/docs/guides/a.md::setup')).toEqual(legacy('showDoc', 'guides/a.md', 'setup'))
  expect(go('#/doc/guides/a.md')).toEqual(legacy('showDoc', 'guides/a.md', undefined))
})

test('docs: an anchor on the page already shown only scrolls', () => {
  expect(go('#/docs/guides/a.md::setup', { current: 'guides/a.md' })).toEqual({ kind: 'scroll', anchor: 'setup' })
  expect(go('#/docs/guides/a.md', { current: 'guides/a.md' })).toEqual(legacy('showDoc', 'guides/a.md', undefined))
})

test('docs: a wiki page under #/docs moves to its wiki address', () => {
  expect(go('#/docs/repos/api/wiki/intro.md::a')).toEqual({ kind: 'redirect', to: '#/wiki/api/wiki/intro.md::a' })
})

test('wikis: the list, a repo graph, a page, an anchor on the page shown', () => {
  expect(go('#/wiki')).toEqual(legacy('showWikis'))
  expect(go('#/wikis')).toEqual(legacy('showWikis'))
  expect(go('#/wikis/api')).toEqual({ kind: 'redirect', to: '#/wiki/api' })
  expect(go('#/wiki/api')).toEqual(legacy('showWikiGraph', 'api'))
  expect(go('#/wiki/api/wiki/intro.md')).toEqual(legacy('showWiki', 'api', 'wiki/intro.md', undefined))
  expect(go('#/wiki/api/wiki/intro.md::b')).toEqual(legacy('showWiki', 'api', 'wiki/intro.md', 'b'))
  expect(go('#/wiki/api/wiki/intro.md::b', { current: 'repos/api/wiki/intro.md' })).toEqual({ kind: 'scroll', anchor: 'b' })
})

test('architecture, code, review, search, new page, zone covers', () => {
  expect(go('#/c4')).toEqual(legacy('showArch', ''))
  expect(go('#/c4/index')).toEqual(legacy('showArch', 'index'))
  expect(go('#/code/api')).toEqual(legacy('showCodeTab', 'api'))
  expect(go('#/review')).toEqual(legacy('showReview'))
  expect(go('#/status')).toEqual(legacy('showReview'))
  expect(go('#/search/visit%20form')).toEqual(legacy('showSearch', 'visit form'))
  expect(go('#/new')).toEqual(legacy('newPage'))
  expect(go('#/new', { mode: 'static' })).toEqual(legacy('showStart'))
  for (const z of ['arch', 'plan', 'quality']) expect(go(`#/${z}`)).toEqual(legacy('showZone', z))
})

test('boards were removed in 4.49: their addresses land on Architecture', () => {
  expect(go('#/boards')).toEqual({ kind: 'redirect', to: '#/arch' })
  expect(go('#/boards/flows')).toEqual({ kind: 'redirect', to: '#/arch' })
})
