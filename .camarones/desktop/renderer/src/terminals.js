// The canvas's terminals: programs the server runs on a PTY (lib/terminals.py) and streams to the app as raw bytes.
// Pure helpers, the stream aside: which terminals show, how a chunk becomes bytes, where a dropped stream resumes.
import { FOLD_MS } from './canvas.js'

export const STREAM = 'app/terminals/stream'

// "t-a-1:120,t-b-2:0": every terminal and the offset the app has reached in it; nothing yet, nothing to ask.
export const streamFrom = (offsets) => Object.entries(offsets || {}).map(([t, o]) => `${t}:${o}`).join(',') || undefined

// A chunk is cut anywhere, inside a UTF-8 character included: xterm gets the bytes and joins them itself.
export const bytes = (b64) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))

const nap = (ms, signal) => new Promise((resolve) => {
  if (signal?.aborted) return resolve()
  const done = () => { clearTimeout(timer); signal?.removeEventListener('abort', done); resolve() }
  const timer = setTimeout(done, ms)
  signal?.addEventListener('abort', done, { once: true })
})

// The server ignores Last-Event-ID: a stream that ends or breaks opens again with the offsets reached. A refusal
// (the token, a server without the route) or an abort is final.
export async function followTerminals(srv, onEvent, { signal, offsets, retry = 2000, sleep = nap }) {
  while (!signal?.aborted) {
    try {
      await srv.stream(STREAM, onEvent, { from: streamFrom(offsets()), signal })
    } catch (e) {
      if (signal?.aborted || e?.status === 403 || e?.status === 404) return
    }
    if (signal?.aborted) return
    await sleep(retry, signal)
  }
}

const live = (term) => term.ended == null

// Seconds count from the server's clock (epoch seconds); `now` is Date.now() in ms.
const sinceEnd = (term, now) => now - term.ended * 1000

// A clean end folds away after FOLD_MS; a failed one stays for its error until it is removed (closed).
const stays = (term, now) => live(term) || term.code !== 0 || sinceEnd(term, now) < FOLD_MS

// What the canvas shows: per unit its newest terminal, and the ones that belong to no unit (the docs update).
export function shown(terms, now) {
  const open = (terms || []).filter((term) => !term.closed).sort((a, b) => a.started - b.started)
  const units = new Map()
  for (const term of open) if (term.kind === 'unit') units.set(term.unit, term)
  for (const [uid, term] of units) if (!stays(term, now)) units.delete(uid)
  return { units, loose: open.filter((term) => term.kind !== 'unit' && stays(term, now)) }
}

export const elapsed = (term, now) => Math.max(0, Math.floor((live(term) ? now / 1000 : term.ended) - term.started))
