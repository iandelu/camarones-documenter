import { expect, test } from 'vitest'
import { emptyFeed, feed, MAX_ROWS, row } from './canvas.js'

const ev = (type, f = {}) => ({ v: 1, ts: '2026-10-27T10:00:00.000Z', type, unit: 'a', ...f })

test('a tool call, an edit, a command, a message and an error each become rows', () => {
  expect(row(ev('tool.call', { name: 'Edit', arg: 'cam-docs/api.md' }))).toEqual([{ kind: 'edit', text: 'Edit cam-docs/api.md' }])
  expect(row(ev('tool.call', { name: 'Grep', arg: 'RestController' }))).toEqual([{ kind: 'read', text: 'Grep RestController' }])
  expect(row(ev('tool.call', { name: 'Bash', arg: 'rg -n x' }))).toEqual([{ kind: 'run', text: 'Bash rg -n x' }])
  expect(row(ev('tool.call', { name: '$', arg: 'npm test' }))).toEqual([{ kind: 'run', text: '$ npm test' }])
  expect(row(ev('tool.call', { name: 'camarones.search_docs', arg: null }))).toEqual([{ kind: 'tool', text: 'camarones.search_docs' }])
  expect(row(ev('file.changed', { path: 'docs/a.md' }))).toEqual([{ kind: 'edit', text: 'edit docs/a.md' }])
  expect(row(ev('log', { text: 'two\n\nlines' }))).toEqual([{ kind: 'log', text: 'two' }, { kind: 'log', text: 'lines' }])
  expect(row(ev('error', { text: 'boom' }))).toEqual([{ kind: 'error', text: 'boom' }])
  expect(row(ev('usage', { in: 1, out: 2, cost_usd: 0.1 }))).toEqual([])
  expect(row(ev('result', { text: 'done' }))).toEqual([])
})

test('long output is cut: 400 characters a row, 20 rows a message', () => {
  const r = row(ev('log', { text: Array.from({ length: 30 }, () => 'x'.repeat(500)).join('\n') }))
  expect(r).toHaveLength(21)
  expect(r[0].text).toHaveLength(400)
  expect(r[0].text.endsWith('…')).toBe(true)
  expect(r[20]).toEqual({ kind: 'log', text: '… +10' })
})

test("the feed keeps each unit's rows, cost, end and outcome", () => {
  let f = emptyFeed('r-1')
  for (const e of [ev('unit.started', { runner: 'claude' }), ev('tool.call', { name: 'Read', arg: 'a.md' }),
    ev('usage', { cost_usd: 0.12 }), ev('usage', { cost_usd: 0.1 }), ev('usage', {}),
    ev('unit.finished', { outcome: 'ok', ts: '2026-10-27T10:04:00.000Z' })]) f = feed(f, e)
  expect(f.units.a).toMatchObject({ runner: 'claude', outcome: 'ok', rows: [{ kind: 'read', text: 'Read a.md' }] })
  expect(f.units.a.cost).toBeCloseTo(0.22)
  expect(f.units.a.ended - f.units.a.started).toBe(240000)
})

test('a long run keeps the last 500 rows of a unit', () => {
  let f = feed(emptyFeed('r-1'), ev('unit.started', { runner: 'claude' }))
  for (let i = 0; i < 10000; i++) f = feed(f, ev('tool.call', { name: 'Read', arg: `f${i}` }))
  expect(f.units.a.rows).toHaveLength(MAX_ROWS)
  expect(f.units.a.rows.at(-1).text).toBe('Read f9999')
})

test('a unit started again after a usage limit keeps its rows and says which agent took over', () => {
  let f = emptyFeed('r-1')
  for (const e of [ev('unit.started', { runner: 'claude' }), ev('tool.call', { name: 'Read', arg: 'a.md' }),
    ev('unit.finished', { outcome: 'limited' }), ev('unit.started', { runner: 'codex' })]) f = feed(f, e)
  expect(f.units.a).toMatchObject({ runner: 'codex', ended: null, outcome: null })
  expect(f.units.a.rows.map((r) => r.text)).toEqual(['Read a.md', '— codex'])
})

test('an event of a unit never started still lands, and run.finished closes the feed', () => {
  let f = feed(emptyFeed('r-1'), ev('log', { unit: 'b', text: 'hola' }))
  expect(f.units.b.rows).toEqual([{ kind: 'log', text: 'hola' }])
  expect(feed(f, { v: 1, ts: '2026-10-27T10:05:00.000Z', type: 'run.finished', done: 1 }).finished).toBe(true)
})

test('the feed is pure', () => {
  const f = emptyFeed('r-1')
  const g = feed(f, ev('unit.started', { runner: 'claude' }))
  expect(g).not.toBe(f)
  expect(f.units).toEqual({})
})
