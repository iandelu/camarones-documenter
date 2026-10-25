// A repo wiki's page, pure: which page an address asks for, the wiki's reading order, the pages that link to it.
// rows: api/wikis; rel: the page under repos/<repo>/ ('' = the wiki's home).
export function wikiTarget(rows, repo, rel) {
  const wiki = (rows || []).find((r) => r.repo === repo) || null
  const nav = wiki?.nav || { home: null, pages: [], backlinks: {} }
  const path = rel ? `repos/${repo}/${rel}` : nav.home || null
  const title = (p) => nav.pages.find((x) => x.path === p)?.title || p.split('/').pop()
  return { wiki, nav, path, order: nav.pages.map((p) => p.path),
    backlinks: (path && nav.backlinks[path] || []).map((p) => ({ path: p, title: title(p) })) }
}
