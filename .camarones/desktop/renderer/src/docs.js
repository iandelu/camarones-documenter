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

// The Docs section's build cards: the C4 explorer, then a graph per repo with a wiki. `body` is what POST build takes
// (token-gated; the portal has no token), `hash` where the portal shows the result.
export const docsCards = (tree) => [{ id: 'c4', repo: '', body: { what: 'c4' }, hash: '#/c4' },
  ...wikiRepos(tree).map((repo) => ({ id: `wiki:${repo}`, repo, body: { what: 'wiki-graph', repo }, hash: `#/wiki/${repo}` }))]

export const startBuild = (srv, card) => srv.post('build', card.body)

// The portal in the system browser (the window never navigates to it); a window without the bridge does nothing.
export const openPortal = (app, origin, hash = '#/') => app.openExternal?.(portalUrl(origin, hash))

// A useJob state that ended badly: the POST was rejected, or the job failed (a stopped one is the person's doing).
export const buildFailed = (b) => !!b.error || (b.job?.status === 'failed' && !b.job.stopped)
