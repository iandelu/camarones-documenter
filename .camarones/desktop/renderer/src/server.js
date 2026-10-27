import { parseSSE } from '@camaron/ui'

// The project's server, one folder up from /desktop/. Every call carries the app's token (lib/serve.py checks it);
// a write also carries X-Camarones, which a page on another site cannot send. A read's `query` goes in the address
// ({ lang } for the units' titles in the app's language). A refusal throws an Error with the server's message, its
// `status` and the response `data`.
// `stream` follows a server-sent stream (a run's events) and resolves with the last id it read, to resume from there;
// when it rejects (a refusal, a dropped connection, an abort) the error carries that same `id`.
export function server(token, fetcher = (...a) => fetch(...a)) {
  const refused = async (name, r) => {
    const data = await r.json().catch(() => ({}))
    return Object.assign(new Error(data.error || `${name}: ${r.status}`), { status: r.status, data })   // data: why (the board's 409 lists who blocks)
  }
  const call = async (name, init = {}) => {
    const r = await fetcher(`../api/${name}`, { ...init, headers: { 'X-Camaron-Token': token, ...init.headers } })
    if (!r.ok) throw await refused(name, r)
    return r.json().catch(() => ({}))
  }
  return {
    get: (name, query) => call(query ? `${name}?${new URLSearchParams(query)}` : name),
    post: (name, body) => call(name, { method: 'POST', body: JSON.stringify(body || {}),
      headers: { 'Content-Type': 'application/json', 'X-Camarones': '1' } }),
    stream: async (name, onEvent, { from, signal } = {}) => {
      let id = from == null ? null : String(from)
      try {
        const url = `../api/${name}${from == null ? '' : `?${new URLSearchParams({ from })}`}`
        const r = await fetcher(url, { headers: { 'X-Camaron-Token': token }, signal })
        if (!r.ok) throw await refused(name, r)
        if (r.status === 204) return { id }               // a run stopped from outside, read to its end: nothing more
        const reader = r.body.pipeThrough(new TextDecoderStream()).getReader()
        let rest = ''
        try {
          for (;;) {
            const { done, value } = await reader.read()
            if (done) return { id }
            const piece = parseSSE(rest + value)
            rest = piece.rest
            if (piece.id !== null) id = piece.id
            piece.events.forEach((ev) => onEvent(ev))
          }
        } finally { reader.cancel().catch(() => {}) }
      } catch (e) { throw e instanceof Object ? Object.assign(e, { id }) : e }   // where it got to, to resume from there
    },
  }
}
