import { expect, test } from 'vitest'
import { bytes, elapsed, fitSize, followTerminals, historyBytes, inputPieces, screenFeed, shown, streamFrom } from './terminals.js'

const b64 = (u8) => btoa(String.fromCharCode(...u8))

test('the stream asks for every terminal from where it got to', () => {
  expect(streamFrom({})).toBe(undefined)
  expect(streamFrom({ 't-a-1': 120, 't-update-2': 0 })).toBe('t-a-1:120,t-update-2:0')
})

test('chunks decode to the very bytes the program wrote, a character split between them included', () => {
  const all = new TextEncoder().encode('año ─ fin')
  for (let cut = 1; cut < all.length; cut++) {
    const joined = new Uint8Array([...bytes(b64(all.slice(0, cut))), ...bytes(b64(all.slice(cut)))])
    expect(new TextDecoder().decode(joined)).toBe('año ─ fin')
  }
})

test('a dropped terminal stream opens again from the offsets it reached', async () => {
  const calls = []
  const offsets = {}
  const ac = new AbortController()
  const srv = { stream: async (name, onEvent, opts) => {
    calls.push([name, opts.from])
    if (calls.length === 1) { onEvent({ t: 't-a-1', d: 'aGk=', o: 2 }); return { id: 't-a-1:2' } }
    ac.abort(); return { id: null } } }
  await followTerminals(srv, (ev) => { offsets[ev.t] = ev.o }, { signal: ac.signal, offsets: () => offsets, sleep: async () => {} })
  expect(calls).toEqual([['app/terminals/stream', undefined], ['app/terminals/stream', 't-a-1:2']])
})

test('a refused terminal stream stops following', async () => {
  let n = 0
  const srv = { stream: async () => { n += 1; throw Object.assign(new Error('no'), { status: 403 }) } }
  await followTerminals(srv, () => {}, { offsets: () => ({}), sleep: async () => {} })
  expect(n).toBe(1)
})

test('which terminals show: live, a clean end for a moment, a failed end until removed, never a closed one', () => {
  const T = (id, f = {}) => ({ id, kind: 'unit', unit: 'a', started: 100, ended: null, code: null, closed: false, ...f })
  const now = 200_000
  expect(shown([T('t-a-1', { started: 50, ended: 60, code: 1 }), T('t-a-2')], now).units.get('a').id).toBe('t-a-2')
  expect(shown([T('t-a-1', { ended: 199, code: 0 })], now).units.has('a')).toBe(true)
  expect(shown([T('t-a-1', { ended: 190, code: 0 })], now).units.has('a')).toBe(false)
  expect(shown([T('t-a-1', { ended: 10, code: 127 })], now).units.has('a')).toBe(true)
  expect(shown([T('t-a-1', { ended: 199, code: -1, closed: true })], now).units.size).toBe(0)
  const up = T('t-update-1', { kind: 'update', unit: null })
  expect(shown([up], now).loose).toEqual([up])
  expect(elapsed(T('t-a-1', { started: 100 }), 160_000)).toBe(60)
  expect(elapsed(T('t-a-1', { started: 100, ended: 130 }), 999_000)).toBe(30)
})

// lib/terminals.py takes 10–500 columns and 5–200 rows: a node squeezed small or a maximised one on a wide screen asks
// for what it can have.
test('the size a screen fits to stays in what the server takes', () => {
  expect(fitSize({ cols: 61, rows: 17 })).toEqual({ cols: 61, rows: 17 })
  expect(fitSize({ cols: 2, rows: 1 })).toEqual({ cols: 10, rows: 5 })
  expect(fitSize({ cols: 900, rows: 400 })).toEqual({ cols: 500, rows: 200 })
  expect(fitSize(undefined)).toBe(null)
  expect(fitSize({ cols: NaN, rows: 20 })).toBe(null)
})

test('a paste bigger than one request goes in pieces, in order, never cutting a character', () => {
  expect(inputPieces('ls\r')).toEqual(['ls\r'])
  expect(inputPieces('')).toEqual([])
  const text = 'añ─😀'.repeat(20)
  const pieces = inputPieces(text, 9)
  expect(pieces.join('')).toBe(text)
  for (const p of pieces) {
    expect(new TextEncoder().encode(p).length).toBeLessThanOrEqual(9)
    expect(p.charCodeAt(0) >= 0xdc00 && p.charCodeAt(0) <= 0xdfff, 'a piece starts inside a character').toBe(false)
  }
  expect(inputPieces('x'.repeat(256 * 1024 + 1)).map((p) => p.length)).toEqual([256 * 1024, 1])
})

// GET app/terminals says how far each terminal's output went: up to there, the stream replays history. A chunk ends at
// `o` and holds `n` bytes; what the program printed between the list and the stream's first read makes one straddle.
test('what a terminal printed before the app looked is history, up to the byte', () => {
  expect(historyBytes(130, 50, 120)).toBe(40)                  // straddles: bytes 80..120 history, 120..130 live
  expect(historyBytes(130, 30, 120)).toBe(20)                  // 100..120 history
  expect(historyBytes(100, 50, 120)).toBe(50)
  expect(historyBytes(120, 50, 120)).toBe(50)
  expect(historyBytes(200, 50, 120)).toBe(0)
  expect(historyBytes(130, 50, undefined)).toBe(0)             // not in the first list: it joined later
  expect(historyBytes(undefined, 50, 120)).toBe(0)
})

// A stand-in for xterm: writes are parsed in order on parse(), and a query it parses is answered through onData, as
// xterm answers DA, CPR or a colour query, as if typed.
const fakeTerm = () => {
  const queue = []
  let on = () => {}
  return {
    onData: (fn) => { on = fn },
    write: (data, done) => queue.push([data, done]),
    press: (key) => on(key),
    parse: () => {
      for (const [data, done] of queue.splice(0)) {
        if (data.includes('\x1b[c')) on('\x1b[?1;2c')
        done?.()
      }
    },
  }
}

test('old queries in the history are not answered to the program; live ones and keys are', () => {
  const term = fakeTerm()
  const sent = []
  const write = screenFeed(term, (data) => sent.push(data))
  write('then \x1b[c', true)
  write('now \x1b[c', false)
  term.parse()
  expect(sent).toEqual(['\x1b[?1;2c'])
  term.press('y')
  expect(sent).toEqual(['\x1b[?1;2c', 'y'])
})

test('a chunk that straddles the end of history answers only the query after it', () => {
  const term = fakeTerm()
  const sent = []
  const write = screenFeed(term, (data) => sent.push(data))
  const chunk = new TextEncoder().encode('start \x1b[c | spin \x1b[c')
  const cut = historyBytes(chunk.length, chunk.length, 9)
  write(new TextDecoder().decode(chunk.subarray(0, cut)), true)
  write(new TextDecoder().decode(chunk.subarray(cut)), false)
  term.parse()
  expect(sent).toEqual(['\x1b[?1;2c'])
  expect(cut).toBe(9)
})
