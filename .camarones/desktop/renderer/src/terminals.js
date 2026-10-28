// The canvas's terminals: programs the server runs on a PTY (lib/terminals.py) and streams to the app as raw bytes.
// Pure helpers, the stream aside: which terminals show, how a chunk becomes bytes, where a dropped stream resumes.
import { FOLD_MS } from './canvas.js'

export const STREAM = 'app/terminals/stream'

// "t-a-1:120,t-b-2:0": every terminal and the offset the app has reached in it; nothing yet, nothing to ask.
export const streamFrom = (offsets) => Object.entries(offsets || {}).map(([t, o]) => `${t}:${o}`).join(',') || undefined

// A chunk is cut anywhere, inside a UTF-8 character included: xterm gets the bytes and joins them itself.
export const bytes = (b64) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))

export const nap = (ms, signal) => new Promise((resolve) => {
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

// How many terminals a switch of project would end (the server that holds them stops); 0 when the list cannot be read.
export const liveSessions = (srv) => srv.get('app/terminals')
  .then((r) => (r?.terminals || []).filter(live).length, () => 0)

// Seconds count from the server's clock (epoch seconds); `now` is Date.now() in ms.
const sinceEnd = (term, now) => now - term.ended * 1000

// A clean end folds away after FOLD_MS; a failed one stays for its error until it is removed (closed).
const stays = (term, now) => live(term) || term.code !== 0 || sinceEnd(term, now) < FOLD_MS

// What the canvas shows: per unit its newest terminal, unless it was closed or folded away (an older one never comes
// back), and the ones that belong to no unit (the docs update).
export function shown(terms, now) {
  const all = [...(terms || [])].sort((a, b) => a.started - b.started)
  const units = new Map()
  for (const term of all) if (term.kind === 'unit') units.set(term.unit, term)
  for (const [uid, term] of units) if (term.closed || !stays(term, now)) units.delete(uid)
  return { units, loose: all.filter((term) => term.kind !== 'unit' && !term.closed && stays(term, now)) }
}

// A streamed chunk gets an xterm for a terminal the canvas shows, or for one the list does not have yet (it just
// opened); the rest (folded, a unit's older one) only move their offset: nothing would ever show their screen.
export function needsScreen(id, terms, now) {
  if (!(terms || []).some((term) => term.id === id)) return true
  const { units, loose } = shown(terms, now)
  return [...units.values(), ...loose].some((term) => term.id === id)
}

export const elapsed = (term, now) => Math.max(0, Math.floor((live(term) ? now / 1000 : term.ended) - term.started))

// What lib/terminals.py takes: 10–500 columns, 5–200 rows. The fit addon proposes nothing while the screen is hidden.
const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n))
export const fitSize = (dims) => (dims && Number.isFinite(dims.cols) && Number.isFinite(dims.rows)
  ? { cols: clamp(dims.cols, 10, 500), rows: clamp(dims.rows, 5, 200) } : null)

// The server takes 256 KB of input a request (UTF-8). A paste goes in pieces, cut between characters, never inside one.
export const INPUT_MAX = 256 * 1024
const utf8 = (cp) => (cp < 0x80 ? 1 : cp < 0x800 ? 2 : cp < 0x10000 ? 3 : 4)
export function inputPieces(text, max = INPUT_MAX) {
  if (text.length * 3 <= max) return text ? [text] : []
  const pieces = []
  let start = 0
  let size = 0
  for (let i = 0; i < text.length;) {
    const cp = text.codePointAt(i)
    const n = utf8(cp)
    if (size + n > max) { pieces.push(text.slice(start, i)); start = i; size = 0 }
    size += n
    i += cp > 0xffff ? 2 : 1
  }
  if (start < text.length) pieces.push(text.slice(start))
  return pieces
}

// GET app/terminals gives each terminal's `offset`, how far its output had gone 2 s before: the stream's bytes up to
// there are history, replayed; fresher ones are live, so a query an agent sent just before the canvas mounted is
// answered. A chunk of `n` bytes ending at `o` may straddle it (the program printed between the list and the
// stream's first read): how many of its first bytes are history. None for a terminal not in that first list: it
// joined later, live from its first byte.
export const historyBytes = (o, n, upTo) => (Number.isFinite(upTo) && Number.isFinite(o) ? clamp(upTo - (o - n), 0, n) : 0)

// xterm answers the queries it parses (DA, the cursor's position, the colours) through onData, as if typed. History is
// written with those answers muted, so an old query is never answered to the program again (a stray Esc interrupts an
// agent). xterm parses in order: a live write queued after history is answered as usual.
export function screenFeed(term, send) {
  let muted = 0
  term.onData((data) => { if (muted === 0) send(data) })
  return (data, history) => {
    if (!history) { term.write(data); return }
    muted += 1
    term.write(data, () => { muted -= 1 })
  }
}
