import { expect, test } from 'vitest'
import { atBottom, changedRun, defaultView, emptyFeed, feed, FOLD_MS, GAP, layout, MAX_ROWS, neighbour, openUnits, place, row, SIZE } from './canvas.js'

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

test('no row outgrows 400 characters: a command, a path or an error as long as a document is cut', () => {
  const heredoc = `cat > doc.md <<'EOF'\n${'x'.repeat(10000)}\nEOF`
  expect(row(ev('tool.call', { name: 'Bash', arg: heredoc }))).toEqual([{ kind: 'run', text: "Bash cat > doc.md <<'EOF'" }])
  expect(row(ev('tool.call', { name: 'Bash', arg: `\n\n${heredoc}` }))[0].text).toBe("Bash cat > doc.md <<'EOF'")
  for (const r of [row(ev('tool.call', { name: 'Bash', arg: 'y'.repeat(10000) })), row(ev('file.changed', { path: 'p/'.repeat(1000) })),
    row(ev('error', { text: 'z'.repeat(10000) }))]) {
    expect(r).toHaveLength(1)
    expect(r[0].text).toHaveLength(400)
    expect(r[0].text.endsWith('…')).toBe(true)
  }
  const e = row(ev('error', { text: Array.from({ length: 30 }, () => 'e'.repeat(500)).join('\n') }))
  expect(e).toHaveLength(21)
  expect(e.every((r) => r.kind === 'error' && r.text.length <= 400)).toBe(true)
  expect(e[20]).toEqual({ kind: 'error', text: '… +10' })
  expect(row(ev('error', { text: '' }))).toEqual([{ kind: 'error', text: '' }])
})

test('tool kinds ignore case, and the name is shown as the agent sent it', () => {
  expect(row(ev('tool.call', { name: 'bash', arg: 'ls' }))).toEqual([{ kind: 'run', text: 'bash ls' }])
  expect(row(ev('tool.call', { name: 'edit', arg: 'a.md' }))).toEqual([{ kind: 'edit', text: 'edit a.md' }])
  expect(row(ev('tool.call', { name: 'patch', arg: 'a.md' }))[0].kind).toBe('edit')
  expect(row(ev('tool.call', { name: 'list', arg: 'src' }))[0].kind).toBe('read')
  expect(row(ev('tool.call', { name: 'GREP', arg: 'x' }))[0].kind).toBe('read')
  expect(row(ev('tool.call', { name: 'constructor', arg: null }))).toEqual([{ kind: 'tool', text: 'constructor' }])
  expect(row(ev('tool.call', { name: null, arg: null }))).toEqual([{ kind: 'tool', text: '' }])
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

const U = (id, phase, extra = {}) => ({ id, title: id, phase, status: 'todo', deps: [], runner: 'agent', ...extra })
const units = [U('a', 1, { status: 'done' }), U('b', 1, { status: 'done' }), U('c', 2, { status: 'doing', deps: ['a', 'b'] }),
  U('d', 2, { deps: ['a'] }), U('e', 3, { deps: ['c'] }), U('x', 3, { status: 'dropped' })]
const overlap = (p, q) => p.position.x < q.position.x + q.width && q.position.x < p.position.x + p.width &&
  p.position.y < q.position.y + q.height && q.position.y < p.position.y + p.height

test('running, failed and just-finished units open as terminals; others fold', () => {
  const f = { run: 'r', finished: false, units: {
    c: { ended: null, outcome: null }, d: { ended: 1000, outcome: 'failed' },
    a: { ended: 10_000, outcome: 'ok' }, b: { ended: 10_000 - FOLD_MS - 1, outcome: 'ok' } } }
  expect([...openUnits(units, f, new Set(), 10_000)].sort()).toEqual(['a', 'c', 'd'])
  expect(openUnits(units, f, new Set(['e']), 10_000).has('e')).toBe(true)
  expect(openUnits(units, { ...f, finished: true }, new Set(), 10_000 + FOLD_MS + 1).has('c')).toBe(false)
})

test('the layout goes by phase, sizes open nodes as terminals and never overlaps', () => {
  const { nodes, edges } = layout(units, new Set(['c']))
  const at = Object.fromEntries(nodes.map((n) => [n.id, n]))
  expect(Object.keys(at).sort()).toEqual(['a', 'b', 'c', 'd', 'e'])
  expect(at.c).toMatchObject({ type: 'term', width: SIZE.term.w, height: SIZE.term.h })
  expect(at.d).toMatchObject({ type: 'unit', width: SIZE.unit.w, height: SIZE.unit.h })
  expect(at.a.position.x).toBeLessThan(at.c.position.x)
  expect(at.e.position.x).toBeGreaterThanOrEqual(at.c.position.x + SIZE.term.w)
  for (const p of nodes) for (const q of nodes) if (p !== q) expect(overlap(p, q)).toBe(false)
  expect(edges.map((e) => e.id).sort()).toEqual(['a->c', 'a->d', 'b->c', 'c->e'])
  expect(edges.find((e) => e.id === 'a->c').animated).toBe(true)
})

test('a dragged node keeps where the person left it', () => {
  const { nodes } = layout(units, new Set())
  const placed = place(nodes, { a: { x: 900, y: 40 }, b: { x: 'no', y: 1 } })
  expect(placed.find((n) => n.id === 'a').position).toEqual({ x: 900, y: 40 })
  expect(placed.find((n) => n.id === 'b').position).toEqual(nodes.find((n) => n.id === 'b').position)
})

test('arrows move to the nearest node in that direction', () => {
  const { nodes } = layout(units, new Set())
  expect(neighbour(nodes, 'a', 'right')).toBe('c')
  expect(neighbour(nodes, 'a', 'down')).toBe('b')
  expect(neighbour(nodes, 'a', 'left')).toBe(null)
})

test('the plan opens on the canvas while something runs, unless a view was picked', () => {
  expect(defaultView(null, true)).toBe('canvas')
  expect(defaultView(null, false)).toBe('board')
  expect(defaultView('phases', true)).toBe('phases')
  expect(defaultView('nonsense', false)).toBe('board')
})

test('the log follows the end only while the person is at the bottom', () => {
  expect(atBottom({ scrollTop: 776, scrollHeight: 1000, clientHeight: 200 })).toBe(true)
  expect(atBottom({ scrollTop: 500, scrollHeight: 1000, clientHeight: 200 })).toBe(false)
})

test('a new run, or the shown one finishing, is noticed', () => {
  expect(changedRun(null, { run: 'r-2', finished: false })).toBe(true)
  expect(changedRun({ run: 'r-1', finished: false }, { run: 'r-2', finished: false })).toBe(true)
  expect(changedRun({ run: 'r-1', finished: false }, { run: 'r-1', finished: true })).toBe(true)
  expect(changedRun({ run: 'r-1', finished: false }, { run: 'r-1', finished: false })).toBe(false)
  expect(changedRun({ run: 'r-1', finished: true }, null)).toBe(false)
})

test('nothing opens without a feed, and a dropped unit never does', () => {
  expect(openUnits(units, null, new Set(), 0).size).toBe(0)
  expect(openUnits(units, emptyFeed('r'), new Set(['x']), 0).size).toBe(0)
})

test('columns are as wide as their widest node and nodes stack with the gap; edges skip absent units', () => {
  const { nodes, edges } = layout([...units, U('f', 3, { deps: ['x', 'ghost'] })], new Set(['c']))
  const at = Object.fromEntries(nodes.map((n) => [n.id, n]))
  expect(at.e.position.x).toBe(at.c.position.x + SIZE.term.w + GAP.x)
  expect(at.b.position.y).toBe(at.a.position.y + SIZE.unit.h + GAP.y)
  expect(edges.some((e) => e.target === 'f')).toBe(false)
})

test('arrows ignore an unknown node and break a tie toward the one more in line', () => {
  const box = (id, x, y, h = 2) => ({ id, position: { x: x - 1, y: y - h / 2 }, width: 2, height: h })
  const nodes = [box('o', 0, 0, 10), box('p', 5, 3), box('q', 5, -1)]
  expect(neighbour(nodes, 'o', 'right')).toBe('q')
  expect(neighbour(nodes, 'o', 'left')).toBe(null)
  expect(neighbour(nodes, 'nope', 'right')).toBe(null)
})

test('arrows prefer the node beside this one, even when a diagonal one is nearer', () => {
  const { nodes } = layout(units, new Set(['c']))
  const at = Object.fromEntries(nodes.map((n) => [n.id, n]))
  expect(at.d.position.y).toBeGreaterThan(at.c.position.y + at.c.height)
  expect(neighbour(nodes, 'b', 'right')).toBe('c')
  expect(neighbour(nodes, 'c', 'down')).toBe('d')
})

test('with nothing beside, arrows pick the diagonal that stays more in line', () => {
  const box = (id, x, y) => ({ id, position: { x: x - 1, y: y - 1 }, width: 2, height: 2 })
  const nodes = [box('o', 0, 0), box('p', 10, 6), box('q', 14, 3)]
  expect(neighbour(nodes, 'o', 'right')).toBe('q')
})
