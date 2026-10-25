// `camaron up` opens the portal with the machine token in the fragment (env.portal_url): `#/<route>&cam-token=<t>`
// or `#cam-token=<t>`. The page keeps it for this tab (sessionStorage, sent as a header by api.js) and takes it out of
// the address at once, so it never lands in the history, a bookmark or a shared link.
export function captureToken(loc = location, storage = sessionStorage, hist = history) {
  const hash = loc.hash || ''
  const m = hash.match(/[#&]cam-token=([A-Za-z0-9_-]+)/)
  if (!m) return null
  try { storage.setItem('cam-token', m[1]) } catch { /* private mode: writes stay off, the board says why */ }
  const route = hash.slice(1).split('&').filter((p) => p && !p.startsWith('cam-token=')).join('&')
  hist.replaceState(null, '', `${loc.pathname || '/'}${loc.search || ''}#${route.startsWith('/') ? route : '/'}`)
  return m[1]
}
