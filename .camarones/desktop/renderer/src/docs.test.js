import { expect, test } from 'vitest'
import { answerView, askBody, askError, buildFailed, c4Card, citeHash, openPortal, portalUrl, startBuild, startWiki, wikiBlocks,
  wikiRepos } from './docs.js'
import { setLang, t } from './i18n.js'

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

// What the Docs section does, without a DOM: the blocks it shows, what each button posts and where Ver / Leer… send the window.
// `repos` is every repo of the project (the tree's `repos`, docs.repo_names()); `docs` says which already have a wiki.
const index = { repos: ['api', 'web', 'ui'], docs: [{ path: 'repos/api/wiki/a.md', space: 'wiki' }, { path: 'repos/ui/wiki/a.md', space: 'wiki' },
  { path: 'repos/web/index.md', space: 'docs' }] }

test('the C4 card builds the explorer and the portal shows it at #/c4', () => {
  expect(c4Card).toEqual({ id: 'c4', repo: '', body: { what: 'c4' }, hash: '#/c4' })
})

// POST wiki (lib/serve.py wiki(b)) refuses a repo that is not chosen unless `choose` is true, adds it to the wiki repos
// when it is, and writes the starter brief when `starter` is true and no brief exists (it never writes over one).
test("one wiki block per repo of the project, with or without a wiki yet, in the project's order", () => {
  const blocks = wikiBlocks(index)
  expect(blocks.map((b) => b.repo)).toEqual(['api', 'web', 'ui'])
  expect(blocks.map((b) => b.hasWiki)).toEqual([true, false, true])
  expect(blocks[1]).toEqual({ repo: 'web', hasWiki: false, hash: '#/wiki/web',
    body: { repo: 'web', choose: true, starter: true },
    graph: { id: 'wiki:web', repo: 'web', body: { what: 'wiki-graph', repo: 'web' }, hash: '#/wiki/web' } })
  expect(wikiBlocks({ repos: [], docs: [] })).toEqual([])
  expect(wikiBlocks(null)).toEqual([])
  expect(wikiBlocks({ docs: [] })).toEqual([])
})

test('Generate posts the shape wiki(b) expects; Build posts the C4 or graph body to build', async () => {
  const posts = []
  const srv = { post: async (path, body) => { posts.push([path, body]); return { id: '7' } } }
  const [api, web] = wikiBlocks(index)
  await startWiki(srv, api)
  await startWiki(srv, web)
  await startBuild(srv, c4Card)
  await startBuild(srv, web.graph)
  expect(posts).toEqual([['wiki', { repo: 'api', choose: true, starter: true }], ['wiki', { repo: 'web', choose: true, starter: true }],
    ['build', { what: 'c4' }], ['build', { what: 'wiki-graph', repo: 'web' }]])
})

test('the portal opens in the browser with its address', () => {
  const opened = []
  const app = { openExternal: (u) => { opened.push(u) } }
  openPortal(app, 'http://127.0.0.1:5000', '#/')
  openPortal(app, 'http://127.0.0.1:5000', '#/review')
  openPortal(app, 'http://127.0.0.1:5000', '#/search')
  for (const h of [c4Card.hash, ...wikiBlocks(index).map((b) => b.hash)]) openPortal(app, 'http://127.0.0.1:5000', h)
  expect(opened).toEqual(['http://127.0.0.1:5000/#/', 'http://127.0.0.1:5000/#/review', 'http://127.0.0.1:5000/#/search',
    'http://127.0.0.1:5000/#/c4', 'http://127.0.0.1:5000/#/wiki/api', 'http://127.0.0.1:5000/#/wiki/web', 'http://127.0.0.1:5000/#/wiki/ui'])
  expect(() => openPortal({}, 'http://x', '#/')).not.toThrow()           // a window without the bridge: nothing happens
})

test('a build failed when the POST was rejected or the job ended failed (not when it was stopped)', () => {
  expect(buildFailed({ error: 'Failed to fetch', job: null })).toBe(true)
  expect(buildFailed({ error: '', job: { status: 'failed', lines: [] } })).toBe(true)
  expect(buildFailed({ error: '', job: { status: 'failed', stopped: true, lines: [] } })).toBe(false)
  expect(buildFailed({ error: '', job: { status: 'done', lines: [] } })).toBe(false)
  expect(buildFailed({ error: '', job: null })).toBe(false)
})

// POST ask/answer takes {q}; an empty question is never sent (answers.answer would spend a model call on nothing).
test('the question is trimmed, and an empty one is not sent', () => {
  expect(askBody('  how does auth work?  ')).toEqual({ q: 'how does auth work?' })
  expect(askBody('')).toBeNull()
  expect(askBody('   \n ')).toBeNull()
  expect(askBody(undefined)).toBeNull()
})

// A cite is "<path>" or "<path>#<section>"; the portal reads a wiki page under #/wiki/<repo>/<page>, any other under
// #/docs/<path>, and a section after "::" (portal core.hrefFor).
test('a source becomes the portal address of its page', () => {
  expect(citeHash('architecture/overview.md#Context')).toBe('#/docs/architecture/overview.md::Context')
  expect(citeHash('repos/web/index.md')).toBe('#/docs/repos/web/index.md')
  expect(citeHash('repos/api/wiki/auth.md#Login')).toBe('#/wiki/api/auth.md::Login')
  expect(citeHash('repos/api/wiki/deep/x.md')).toBe('#/wiki/api/deep/x.md')
})

// answers.answer: {answer, cited, runner, model, seconds…}; answer is null when the docs had nothing or the model said
// nothing (cited is then empty). The sources are only those the retrieval knew.
test('an answer with sources, one without, and the "nothing to answer" state', () => {
  const full = answerView({ answer: 'It uses JWT.', cited: ['architecture/overview.md#Context', 'repos/api/wiki/auth.md'],
    runner: 'claude', model: 'haiku', seconds: 4.2 })
  expect(full).toEqual({ kind: 'answer', text: 'It uses JWT.', by: 'claude (haiku)',
    sources: [{ cite: 'architecture/overview.md#Context', hash: '#/docs/architecture/overview.md::Context' },
      { cite: 'repos/api/wiki/auth.md', hash: '#/wiki/api/auth.md' }] })
  const bare = answerView({ answer: 'No idea.', cited: [], runner: 'codex', model: null })
  expect(bare).toEqual({ kind: 'answer', text: 'No idea.', by: 'codex', sources: [] })
  expect(answerView({ answer: 'x' }).sources).toEqual([])          // no cited key at all
  expect(answerView({ answer: null, cited: [], runner: 'claude' })).toEqual({ kind: 'none' })
  expect(answerView({ answer: '', cited: [] })).toEqual({ kind: 'none' })
  expect(answerView(null)).toEqual({ kind: 'none' })
})

// answers.answer raises RuntimeError (HTTP 400 {error: text}) in English: the person gets es/en sentences, not that text.
test("the server's \"no AI\" and \"too slow\" refusals are said in the app's language", () => {
  const noAi = { message: 'no AI answer here: no runner for bounded work (or ask.ai is false in workspace.yaml)' }
  const slow = { message: 'no answer within 90 s: claude is slow or waiting for a login; try again or set a faster model with `ask: {model: …}` in workspace.yaml' }
  setLang('es')
  expect(askError(noAi, t)).toBe(t('docs.askNoAi'))
  expect(askError(slow, t)).toBe(t('docs.askSlow'))
  expect(askError({ message: 'Failed to fetch' }, t)).toBe('No llego al servidor del proyecto.')
  expect(askError({ message: 'boom' }, t)).toBe('El servidor lo ha rechazado: boom')
  setLang('en')
  expect(askError(noAi, t)).toBe('There is no AI to answer here: no agent is available, or ask.ai is off in workspace.yaml.')
  expect(askError(slow, t)).toBe(t('docs.askSlow'))
  setLang('es')
})
