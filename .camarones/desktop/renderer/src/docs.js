import { errorLine } from './onboarding.js'

// The portal (the reader) from the app: it is served by the same project server, one folder up from /desktop/, and
// a project window opens it in the system browser. Pure.

// An address of the portal: origin is this window's (location.origin), hash the portal's route ('#/', '#/review'…).
export const portalUrl = (origin, hash = '#/') => `${String(origin).replace(/\/+$/, '')}/${hash || '#/'}`

// The repos that have an OpenWiki, as the portal reads them from the tree (GET tree): their pages are in the wiki
// space, under repos/<repo>/wiki/…. Only those have a graph to build (env.wiki_graph needs pages). Once each, in order.
export function wikiRepos(tree) {
  const out = []
  for (const d of tree?.docs || []) {
    if (d.space !== 'wiki') continue
    const repo = String(d.path).split('/')[1]
    if (repo && !out.includes(repo)) out.push(repo)
  }
  return out
}

// The C4 explorer's card: `body` is what POST build takes (token-gated; the portal has no token), `hash` where the
// portal shows the result.
export const c4Card = { id: 'c4', repo: '', body: { what: 'c4' }, hash: '#/c4' }

// One block per repo of the project (the tree's `repos`: every one, whether or not it has a wiki yet). `body` is what
// POST wiki takes (lib/serve.py wiki(b)): `choose` adds the repo to the ones with a wiki when it is not, `starter`
// writes a starter brief without AI when there is none (it never writes over one), so the same body serves a repo at
// any stage. `graph` is the wiki-graph build, which needs pages (`hasWiki`).
export const wikiBlocks = (tree) => {
  const withWiki = wikiRepos(tree)
  return (tree?.repos || []).map((repo) => ({ repo, hasWiki: withWiki.includes(repo), hash: `#/wiki/${repo}`,
    body: { repo, choose: true, starter: true },
    graph: { id: `wiki:${repo}`, repo, body: { what: 'wiki-graph', repo }, hash: `#/wiki/${repo}` } }))
}

export const startBuild = (srv, card) => srv.post('build', card.body)
export const startWiki = (srv, block) => srv.post('wiki', block.body)

// The portal in the system browser (the window never navigates to it); a window without the bridge does nothing.
export const openPortal = (app, origin, hash = '#/') => app.openExternal?.(portalUrl(origin, hash))

// A useJob state that ended badly: the POST was rejected, or the job failed (a stopped one is the person's doing).
export const buildFailed = (b) => !!b.error || (b.job?.status === 'failed' && !b.job.stopped)

// Ask's AI answer (POST ask/answer, lib/answers.py): the question as the server takes it; null for an empty one.
export const askBody = (q) => {
  const text = String(q ?? '').trim()
  return text ? { q: text } : null
}

// A source ("<path>" or "<path>#<section>") as the portal's address of that page: a repo's wiki page (repos/<repo>/wiki/…)
// under #/wiki/<repo>/<page>, any other under #/docs/<path>, a section after "::" (portal core.hrefFor).
export function citeHash(cite) {
  const [path, anchor] = String(cite).split('#')
  const tail = anchor ? `::${anchor}` : ''
  const wiki = path.match(/^repos\/([^/]+)\/wiki\/(.+)$/)
  return wiki ? `#/wiki/${wiki[1]}/${wiki[2]}${tail}` : `#/docs/${path}${tail}`
}

// What the answer card shows: the text with who wrote it and its sources, or "none" when the docs had nothing to
// answer from or the model said nothing (answer is null then).
export function answerView(r) {
  if (!r?.answer) return { kind: 'none' }
  const sources = (Array.isArray(r.cited) ? r.cited : []).map((cite) => ({ cite, hash: citeHash(cite) }))
  return { kind: 'answer', text: r.answer, by: r.runner ? (r.model ? `${r.runner} (${r.model})` : r.runner) : '', sources }
}

// The server refuses in English (lib/answers.py raises RuntimeError): the two refusals a person can act on get their
// own sentence; anything else goes through the wizard's errorLine.
export function askError(e, t) {
  const msg = String(e?.message ?? e ?? '')
  if (/^no AI answer here/.test(msg)) return t('docs.askNoAi')
  if (/^no answer within/.test(msg)) return t('docs.askSlow')
  return errorLine(e, t)
}
