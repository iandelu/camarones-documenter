// The portal server's API (lib/serve.py), relative so the app also works under a sub-path. Mutations need the
// X-Camarones header, which a cross-site page cannot send. Work that starts a process is the desktop app's: the
// server refuses it here (lib/serve.py APP_ONLY).
import { parseSSE } from '@camaron/ui'

// (Read once at import; without a page — the tests — it is the live server.)
export const STATIC = typeof document !== 'undefined' && document.querySelector('meta[name="cam-mode"]')?.content === 'static'

// The token `camaron up` (or the desktop app) put in the address, kept for this tab by token.js: board writes need it.
const portalToken = () => { try { return sessionStorage.getItem('cam-token') || '' } catch { return '' } }
const token = () => {
  const tok = portalToken()
  return tok ? { 'X-Camaron-Token': tok } : {}
}

// A refused request is an Error with the server's message, its HTTP `status` and the body it sent (`data`: a 409's
// `blocked_by`, a 403's `token`…), so a view can tell a conflict from a bad input.
function failed(path, res, data) {
  return Object.assign(new Error(data.error || `${path}: ${res.status}`), { status: res.status, data })
}

export async function getJSON(path, { signal } = {}) {
  const res = await fetch(`api/${path}`, { headers: { Accept: 'application/json', ...token() }, signal })
  if (!res.ok) throw failed(path, res, await res.json().catch(() => ({})))
  return res.json()
}

export async function postJSON(path, body, { signal } = {}) {
  const res = await fetch(`api/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Camarones': '1', ...token() },
    body: JSON.stringify(body || {}),
    signal,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw failed(path, res, data)
  return data
}

// Server-sent events through fetch: EventSource cannot send the token.
export async function streamEvents(path, onEvent, signal) {
  const res = await fetch(`api/${path}`, { headers: token(), signal })
  if (!res.ok || !res.body) throw new Error((await res.json().catch(() => ({}))).error || `${path}: ${res.status}`)
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let rest = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    const r = parseSSE(rest + value)
    rest = r.rest
    r.events.forEach(onEvent)
  }
}
