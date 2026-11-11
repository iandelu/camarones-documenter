// Which page a link names, pure; the Python twin is docs.link_target (what `camaron check` uses).
// A wiki page's path is where it sits in cam-docs, wikis/<repo>/<page>. It links a docs page as the file sits on disk,
// `../../docs/<page>`, which resolves to docs/<page>: that is the docs page <page>. Kits up to 4.80.1 called a wiki page
// repos/<repo>/<page>; that path still names it wherever no docs page has it. Anything else stays as written.
export function oldWikiPath(path) {
  const [top, repo, ...rest] = String(path).split('/')
  return top === 'repos' && repo && rest.length && rest.join('/') ? `wikis/${repo}/${rest.join('/')}` : null
}

export function linkTarget(path, has) {
  if (has(path)) return path
  const bare = path.startsWith('docs/') ? path.slice('docs/'.length) : path
  if (has(bare)) return bare
  const alias = oldWikiPath(bare)
  return alias && has(alias) ? alias : path
}

// An image or file next to a page, as the server's raw/ serves it: docs/<x> is the docs folder's <x>.
export const rawPath = (path) => (path.startsWith('docs/') ? path.slice('docs/'.length) : path)
