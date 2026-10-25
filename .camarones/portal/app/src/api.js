// The portal server's API (lib/serve.py), relative so the app also works under a sub-path. Mutations need the
// X-Camarones header, which a cross-site page cannot send. In the desktop app's window (its preload sets
// window.camaronApp) every request also carries the app's token: only then does the server start processes.
import { parseSSE } from './sse.js'

// (Read once at import; without a page — the tests — it is the live server, outside the app.)
export const STATIC = typeof document !== 'undefined' && document.querySelector('meta[name="cam-mode"]')?.content === 'static'
export const APP = typeof window !== 'undefined' && window.camaronApp?.token ? window.camaronApp : null
export const RUNS = !STATIC && !!APP

// Outside the app, the token `camaron up` put in the address (token.js keeps it for this tab): board writes need it.
const portalToken = () => { try { return sessionStorage.getItem('cam-token') || '' } catch { return '' } }
const token = () => {
  const tok = APP ? APP.token : portalToken()
  return tok ? { 'X-Camaron-Token': tok } : {}
}

export async function getJSON(path) {
  const res = await fetch(`api/${path}`, { headers: { Accept: 'application/json', ...token() } })
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `${path}: ${res.status}`)
  return res.json()
}

export async function postJSON(path, body) {
  const res = await fetch(`api/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Camarones': '1', ...token() },
    body: JSON.stringify(body || {}),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || `${path}: ${res.status}`)
  return data
}

// Server-sent events through fetch: EventSource cannot send the app's token.
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
