import { expect, test } from 'vitest'
import { bytes, elapsed, followTerminals, shown, streamFrom } from './terminals.js'

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
