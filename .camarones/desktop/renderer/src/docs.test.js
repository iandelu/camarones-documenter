import { expect, test } from 'vitest'
import { buildFailed, docsCards, openPortal, portalUrl, startBuild, wikiRepos } from './docs.js'

// The portal is the reader, on the project's own server one folder up from /desktop/; the window opens it in the
// system browser (main.cjs's guard sends same-origin addresses outside /desktop/ there).
test('the portal lives at the root of the project server', () => {
  expect(portalUrl('http://127.0.0.1:5123', '#/')).toBe('http://127.0.0.1:5123/#/')
  expect(portalUrl('http://127.0.0.1:5123', '#/review')).toBe('http://127.0.0.1:5123/#/review')
  expect(portalUrl('http://127.0.0.1:5123')).toBe('http://127.0.0.1:5123/#/')
  expect(portalUrl('http://127.0.0.1:5123/', '#/')).toBe('http://127.0.0.1:5123/#/')    // a trailing slash is not doubled
})

// The portal reads a page's space ('wiki' for a repo's OpenWiki, under repos/<repo>/wiki/…): the repos with at least one
// wiki page are the ones whose graph can be built (env.wiki_graph is False without pages).
test('the repos with a wiki are the ones with wiki pages, once each, in order', () => {
  const tree = { docs: [
    { path: 'index.md', space: 'docs' },
    { path: 'repos/api/wiki/index.md', space: 'wiki' },
    { path: 'repos/api/wiki/auth.md', space: 'wiki' },
    { path: 'repos/web/index.md', space: 'docs' },           // a repo's own page in the docs space: not a wiki
    { path: 'repos/ui/wiki/a.md', space: 'wiki' },
    { path: 'interview/x.md', space: 'notes' }] }
  expect(wikiRepos(tree)).toEqual(['api', 'ui'])
  expect(wikiRepos({ docs: [] })).toEqual([])
  expect(wikiRepos(null)).toEqual([])
  expect(wikiRepos({})).toEqual([])
})

// What the Docs section does, without a DOM: the cards it shows, what Build posts and where Ver / Leer… send the window.
const wikiTree = { docs: [{ path: 'repos/api/wiki/a.md', space: 'wiki' }, { path: 'repos/ui/wiki/a.md', space: 'wiki' }] }

test('a C4 card, then one wiki graph card per repo with a wiki, each with its body and portal route', () => {
  expect(docsCards(wikiTree)).toEqual([
    { id: 'c4', repo: '', body: { what: 'c4' }, hash: '#/c4' },
    { id: 'wiki:api', repo: 'api', body: { what: 'wiki-graph', repo: 'api' }, hash: '#/wiki/api' },
    { id: 'wiki:ui', repo: 'ui', body: { what: 'wiki-graph', repo: 'ui' }, hash: '#/wiki/ui' }])
  expect(docsCards({ docs: [] }).map((c) => c.id)).toEqual(['c4'])
})

test('Build posts the card body to build; the portal opens in the browser with its address', async () => {
  const posts = []
  const srv = { post: async (path, body) => { posts.push([path, body]); return { id: '7' } } }
  for (const c of docsCards(wikiTree)) await startBuild(srv, c)
  expect(posts).toEqual([['build', { what: 'c4' }], ['build', { what: 'wiki-graph', repo: 'api' }],
    ['build', { what: 'wiki-graph', repo: 'ui' }]])
  const opened = []
  const app = { openExternal: (u) => { opened.push(u) } }
  openPortal(app, 'http://127.0.0.1:5000', '#/')
  openPortal(app, 'http://127.0.0.1:5000', '#/review')
  openPortal(app, 'http://127.0.0.1:5000', '#/search')
  for (const c of docsCards(wikiTree)) openPortal(app, 'http://127.0.0.1:5000', c.hash)
  expect(opened).toEqual(['http://127.0.0.1:5000/#/', 'http://127.0.0.1:5000/#/review', 'http://127.0.0.1:5000/#/search',
    'http://127.0.0.1:5000/#/c4', 'http://127.0.0.1:5000/#/wiki/api', 'http://127.0.0.1:5000/#/wiki/ui'])
  expect(() => openPortal({}, 'http://x', '#/')).not.toThrow()           // a window without the bridge: nothing happens
})

test('a build failed when the POST was rejected or the job ended failed (not when it was stopped)', () => {
  expect(buildFailed({ error: 'Failed to fetch', job: null })).toBe(true)
  expect(buildFailed({ error: '', job: { status: 'failed', lines: [] } })).toBe(true)
  expect(buildFailed({ error: '', job: { status: 'failed', stopped: true, lines: [] } })).toBe(false)
  expect(buildFailed({ error: '', job: { status: 'done', lines: [] } })).toBe(false)
  expect(buildFailed({ error: '', job: null })).toBe(false)
})
