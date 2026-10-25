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
