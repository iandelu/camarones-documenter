import { expect, test } from 'vitest'
import { bytes, elapsed, fitSize, followTerminals, historyBytes, inputPieces, liveSessions, needsScreen, screenFeed, shown, streamFrom } from './terminals.js'

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

// Every canvas mount replays the stream: a terminal the canvas does not show (closed, folded, a unit's older one) moves
// its offset and gets no xterm; one the list does not have yet just opened, and gets its screen.
test('a chunk gets a screen only for a terminal the canvas shows, or a new one', () => {
  const T = (id, f = {}) => ({ id, kind: 'unit', unit: 'a', started: 100, ended: null, code: null, closed: false, ...f })
  const now = 200_000
  const list = [T('t-a-1', { started: 50, ended: 60, code: 1 }), T('t-a-2'), T('t-b-1', { unit: 'b', ended: 10, code: 0 }),
    T('t-c-1', { unit: 'c', ended: 150, code: 1, closed: true }), T('t-update-1', { kind: 'update', unit: null })]
  expect(needsScreen('t-a-2', list, now)).toBe(true)
  expect(needsScreen('t-update-1', list, now)).toBe(true)
  expect(needsScreen('t-a-9', list, now)).toBe(true)
  expect(needsScreen('t-a-1', list, now)).toBe(false)
  expect(needsScreen('t-b-1', list, now)).toBe(false)
  expect(needsScreen('t-c-1', list, now)).toBe(false)
  expect(needsScreen('t-a-1', [], now)).toBe(true)
})

// Per unit its newest terminal decides: the person closed it, or it folded away, and an older failed one stays gone.
test('a unit whose newest terminal was closed or folded shows none of its older ones', () => {
  const T = (id, f = {}) => ({ id, kind: 'unit', unit: 'a', started: 100, ended: null, code: null, closed: false, ...f })
  const now = 200_000
  const failed = T('t-a-1', { started: 50, ended: 60, code: 1 })
  expect(shown([failed, T('t-a-2', { ended: 199, code: -1, closed: true })], now).units.size).toBe(0)
  expect(shown([failed, T('t-a-2', { closed: true })], now).units.size).toBe(0)
  expect(shown([T('t-a-2', { ended: 150, code: 0 }), failed], now).units.size).toBe(0)
  expect(shown([failed], now).units.get('a')).toBe(failed)
})

test('loose terminals fold, leave once closed and keep their start order', () => {
  const L = (id, f = {}) => ({ id, kind: 'update', unit: null, started: 100, ended: null, code: null, closed: false, ...f })
  const now = 200_000
  const late = L('t-update-2', { started: 120 })
  const early = L('t-update-1', { started: 90 })
  const failed = L('t-update-3', { started: 80, ended: 85, code: 2 })
  const list = [late, early, failed, L('t-update-4', { ended: 150, code: 0 }), L('t-update-5', { closed: true }),
    L('t-update-6', { ended: 199, code: 0 })]
  expect(shown(list, now).loose.map((x) => x.id)).toEqual(['t-update-3', 't-update-1', 't-update-6', 't-update-2'])
  expect(list[0]).toBe(late)
})

// Switching project from the rail stops this project's server and every terminal it holds: the rail asks first when
// one is live, and switches as before when the list cannot be read.
test('a switch of project counts the live sessions it would end', async () => {
  const T = (id, f = {}) => ({ id, kind: 'unit', unit: 'a', started: 100, ended: null, code: null, closed: false, ...f })
  const srv = (terminals) => ({ get: async (name) => { expect(name).toBe('app/terminals'); return { terminals } } })
  expect(await liveSessions(srv([T('t-a-1'), T('t-b-1', { ended: 150, code: 0 }), T('t-update-1', { kind: 'update' })]))).toBe(2)
  expect(await liveSessions(srv([T('t-a-1', { ended: 150, code: 1 })]))).toBe(0)
  expect(await liveSessions(srv(undefined))).toBe(0)
  expect(await liveSessions({ get: async () => { throw new Error('gone') } })).toBe(0)
})
