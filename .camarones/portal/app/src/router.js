// The portal's address table: a hash → what the shell shows. Pure: the shell passes what it knows (mode, the page
// on screen, each page's space, how a page is linked). Old addresses keep working: #/doc, #/status, #/wikis/<repo>,
// #/docs/<a wiki page>, #/boards (removed in 4.49).

// The React views that need the live server, and the Taller (machine work), which needs the desktop app.
export const NATIVE = ['pipeline', 'ask', 'kpis', 'ci', 'libs', 'data', 'interview', 'sync']
export const TALLER = ['generate', 'analyze', 'check', 'interviews', 'team', 'machine', 'kitdev']
const COVERS = ['arch', 'plan', 'quality', 'taller']

export function parse(hash) {
  const raw = (hash || '').replace(/^#/, '')
  let h = raw
  try { h = decodeURIComponent(raw) } catch { /* a bare % in a file name: route the address as it is */ }
  const [, view = '', rest = ''] = h.match(/^\/([\w-]*)\/?(.*)$/) || []
  return { view, rest }
}

const HOME = { kind: 'native', view: 'home', arg: '' }

// ctx: { mode: 'static' | 'live' | 'app', current: page path on screen, space(path), hrefFor(path, anchor),
//        firstView(zone): the address of the zone's first view in this mode, if it has one }
export function resolve(hash, ctx) {
  const { view, rest } = parse(hash)
  if (NATIVE.includes(view) && ctx.mode !== 'static' || TALLER.includes(view) && ctx.mode === 'app')
    return { kind: 'native', view, arg: rest }
  if (view === 'boards') return { kind: 'redirect', to: '#/arch' }
  if (view === 'docs' || view === 'doc') {
    if (!rest) return { kind: 'native', view: 'docs', arg: '' }
    const [path, anchor] = rest.split('::')
    if (ctx.space(path) === 'wiki') return { kind: 'redirect', to: ctx.hrefFor(path, anchor) }
    if (path === ctx.current && anchor !== undefined) return { kind: 'scroll', anchor }
    return { kind: 'native', view: 'doc', arg: rest }
  }
  if (view === 'wiki') {
    const [repo = '', ...more] = rest.split('/')
    const [rel = '', anchor] = more.join('/').split('::')
    if (rel && `repos/${repo}/${rel}` === ctx.current && anchor !== undefined) return { kind: 'scroll', anchor }
    if (!repo) return { kind: 'native', view: 'wikis', arg: '' }
    return rel ? { kind: 'native', view: 'wikipage', arg: rest } : { kind: 'native', view: 'wikigraph', arg: repo }
  }
  if (view === 'wikis') return rest ? { kind: 'redirect', to: `#/wiki/${rest}` } : { kind: 'native', view: 'wikis', arg: '' }
  if (view === 'c4' && /^code(\/|$)/.test(rest))         // the old address of graphify's page
    return { kind: 'redirect', to: `#/code/${rest.split('/').slice(1).filter(Boolean).join('/') || 'all'}/graph` }
  if (view === 'c4') return { kind: 'native', view: 'c4', arg: rest }
  if (view === 'code') return { kind: 'native', view: 'code', arg: rest }
  if (view === 'review' || view === 'status') return { kind: 'native', view: 'review', arg: '' }
  if (view === 'search') return { kind: 'native', view: 'search', arg: rest }
  if (view === 'new' && ctx.mode !== 'static') return { kind: 'native', view: 'new', arg: '' }
  const first = COVERS.includes(view) && (view !== 'taller' || ctx.mode === 'app') && ctx.firstView(view)
  if (first) return { kind: 'redirect', to: first }
  return HOME
}
