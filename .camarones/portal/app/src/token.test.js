import { expect, test } from 'vitest'
import { captureToken } from './token.js'

const fake = (hash) => {
  const loc = { hash, pathname: '/', search: '' }
  const saved = {}
  const storage = { setItem: (k, v) => { saved[k] = v } }
  const calls = []
  const hist = { replaceState: (...a) => { calls.push(a); loc.hash = a[2].slice(a[2].indexOf('#')) } }
  return { loc, saved, storage, calls, hist }
}

test('a token alone: kept in the session, the address goes home', () => {
  const f = fake('#cam-token=Ab_9-z')
  expect(captureToken(f.loc, f.storage, f.hist)).toBe('Ab_9-z')
  expect(f.saved['cam-token']).toBe('Ab_9-z')
  expect(f.calls).toEqual([[null, '', '/#/']])
})

test('a route and a token: the route stays', () => {
  const f = fake('#/kanban&cam-token=tok123')
  expect(captureToken(f.loc, f.storage, f.hist)).toBe('tok123')
  expect(f.saved['cam-token']).toBe('tok123')
  expect(f.calls).toEqual([[null, '', '/#/kanban']])
  const g = fake('#/docs/flows/a.md&cam-token=t')
  captureToken(g.loc, g.storage, g.hist)
  expect(g.calls[0][2]).toBe('/#/docs/flows/a.md')
})

test('storage that throws (private mode): the token still comes back', () => {
  const f = fake('#cam-token=tok')
  const bad = { setItem: () => { throw new Error('denied') } }
  expect(() => captureToken(f.loc, bad, f.hist)).not.toThrow()
  expect(captureToken(fake('#cam-token=tok').loc, bad, fake('').hist)).toBe('tok')
})

test('blocked site data: reading sessionStorage itself throws, the token still comes back', () => {
  const had = Object.getOwnPropertyDescriptor(globalThis, 'sessionStorage')
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, get() { throw new Error('SecurityError') } })
  try {
    const f = fake('#/kanban&cam-token=tok')
    expect(captureToken(f.loc, undefined, f.hist)).toBe('tok')       // the default storage, resolved inside the guard
    expect(f.calls).toEqual([[null, '', '/#/kanban']])
  } finally {
    if (had) Object.defineProperty(globalThis, 'sessionStorage', had)
    else delete globalThis.sessionStorage
  }
})

test('no token: null and the address untouched', () => {
  const f = fake('#/kanban')
  expect(captureToken(f.loc, f.storage, f.hist)).toBeNull()
  expect(f.calls).toEqual([])
  expect(f.saved).toEqual({})
  expect(captureToken(fake('').loc, f.storage, f.hist)).toBeNull()
})
