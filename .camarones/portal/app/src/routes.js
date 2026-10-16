// Hash routes, so the static export works on any host: #/ · #/pipeline
export const VIEWS = ['home', 'pipeline']

export function parse(hash) {
  const path = (hash || '').replace(/^#\/?/, '')
  const [view, ...rest] = path.split('/')
  return VIEWS.includes(view) ? { view, arg: rest.join('/') || null } : { view: 'home', arg: null }
}

export function href(view, arg) {
  return `#/${view === 'home' ? '' : view}${arg ? `/${arg}` : ''}`
}
