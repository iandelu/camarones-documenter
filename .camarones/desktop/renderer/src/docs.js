import { errorLine } from './onboarding.js'

// The portal (the reader) from the app: it is served by the same project server, one folder up from /desktop/, and
// a project window opens it in the system browser. Pure.

// An address of the portal: origin is this window's (location.origin), hash the portal's route ('#/', '#/review'…).
export const portalUrl = (origin, hash = '#/') => `${String(origin).replace(/\/+$/, '')}/${hash || '#/'}`

// The repos that have an OpenWiki, as the portal reads them from the tree (GET tree): their pages are in the wiki
// space, at repos/<repo>/<page> (docs.iter_docs). Only those have a graph to build (env.wiki_graph needs pages). Once each, in order.
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

// One block per repo of the project, from GET wikis (env.wikis(): every repo, in the project's order, with whether it is
// cloned and chosen, its brief ('ai' | 'starter' | null), its pages and canGenerate = cloned and a wiki engine
// installed). `blocked` says why Generate is closed: 'notCloned', 'noEngine', or 'unread' when wikis could not be read
// (then the tree's `repos` still list every repo, with what the tree knows of their pages).
// `body` is what POST wiki takes (lib/serve.py wiki(b)): `choose` only for a repo not yet chosen (the server adds it to
// the ones with a wiki), `starter` only when there is no brief and no pages (a starter brief is written without AI),
// as the portal sent them. `graph` is the wiki-graph build, which needs pages (`hasWiki`).
export const wikiBlocks = (tree, wikis) => {
  const block = (repo, hasWiki, blocked, { chosen = false, brief = null, pages = 0 } = {}) => ({ repo, hasWiki, blocked, hash: `#/wiki/${repo}`,
    body: { repo, ...(chosen ? {} : { choose: true }), ...(brief || pages ? {} : { starter: true }) },
    graph: { id: `wiki:${repo}`, repo, body: { what: 'wiki-graph', repo }, hash: `#/wiki/${repo}` } })
  if (Array.isArray(wikis)) {
    return wikis.map((w) => block(w.repo, w.pages > 0, w.canGenerate ? null : w.cloned ? 'noEngine' : 'notCloned', w))
  }
  const withWiki = wikiRepos(tree)
  return (tree?.repos || []).map((repo) => block(repo, withWiki.includes(repo), 'unread'))
}

export const startBuild = (srv, card) => srv.post('build', card.body)
export const startWiki = (srv, block) => srv.post('wiki', block.body)

// One wiki runs at a time (lib/serve.py wiki(): another repo's start is refused with 409 busy). From the jobs store's
// running list: the repo whose wiki runs, when it is not `repo` ('' otherwise), so Generate closes on the others.
export const wikiBusyWith = (running, repo) =>
  (running || []).find((j) => j.kind === 'wiki' && j.status === 'running' && j.repo && j.repo !== repo)?.repo || ''

// POST wiki refused with busy (another repo's wiki started meanwhile) has its own sentence; anything else as errorLine.
export const wikiError = (e, t) => (String(e?.message ?? e ?? '') === 'busy' ? t('docs.wikiBusyAny') : errorLine(e, t))

// The portal in the system browser (the window never navigates to it); a window without the bridge does nothing.
export const openPortal = (app, origin, hash = '#/') => app.openExternal?.(portalUrl(origin, hash))

// A useJob state that ended badly: the POST was rejected, or the job failed (a stopped one is the person's doing).
export const buildFailed = (b) => !!b.error || (b.job?.status === 'failed' && !b.job.stopped)

// Ask's AI answer (POST ask/answer, lib/answers.py): the question as the server takes it; null for an empty one.
export const askBody = (q) => {
  const text = String(q ?? '').trim()
  return text ? { q: text } : null
}

// A source ("<path>" or "<path>#<section>") as the portal's address of that page: #/docs/<path>, a section after "::"
// (portal core.hrefFor). A wiki page's path (repos/<repo>/<page>) looks like a repo's own page; the portal's router
// sends #/docs/<a wiki page> on to #/wiki/<repo>/<page>, so it is not told apart here.
export function citeHash(cite) {
  const [path, ...rest] = String(cite).split('#')            // only the first # splits: a section may contain one
  const anchor = rest.join('#')
  return `#/docs/${path}${anchor ? `::${anchor}` : ''}`
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
