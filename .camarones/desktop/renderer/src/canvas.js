// The Plan's canvas: what each unit of a running plan is doing, from the run's events (runs/<run>/events.jsonl).
// Pure helpers: an event becomes display rows, a run's events fold into one feed per unit, and the units become
// positioned nodes (React Flow's shapes) with the keyboard's moves between them.
import { phases } from './plan.js'

export const MAX_ROWS = 500
export const LINE = 400
export const LINES = 20

export const GLYPH = { edit: '✎', read: '⌕', run: '▶', tool: '·', log: '»', error: '✕' }

const KIND = new Map([
  ...['edit', 'write', 'multiedit', 'notebookedit', 'patch'].map((n) => [n, 'edit']),
  ...['read', 'glob', 'grep', 'ls', 'list'].map((n) => [n, 'read']),
  ...['bash', '$'].map((n) => [n, 'run']),
])

// Every row is bounded, whatever an agent sends: a heredoc or a whole error would otherwise be one huge row.
const cut = (s) => (s.length > LINE ? `${s.slice(0, LINE - 1)}…` : s)
const firstLine = (s) => String(s).split(/\r?\n/).find((l) => l.trim()) ?? ''

function textRows(kind, text) {
  const lines = String(text ?? '').split(/\r?\n/).filter((l) => l.trim())
  const rows = lines.slice(0, LINES).map((l) => ({ kind, text: cut(l) }))
  if (lines.length > LINES) rows.push({ kind, text: `… +${lines.length - LINES}` })
  return rows
}

export function row(ev) {
  switch (ev.type) {
    case 'tool.call': {
      const name = String(ev.name ?? '')
      const arg = ev.arg == null ? '' : firstLine(ev.arg)
      return [{ kind: KIND.get(name.toLowerCase()) || 'tool', text: cut(arg ? `${name} ${arg}` : name) }]
    }
    case 'file.changed': return [{ kind: 'edit', text: cut(`edit ${ev.path}`) }]
    case 'log': return textRows('log', ev.text)
    case 'error': {
      const rows = textRows('error', ev.text)
      return rows.length ? rows : [{ kind: 'error', text: '' }]
    }
    default: return []
  }
}

export const emptyFeed = (run) => ({ run, finished: false, units: {} })

const ms = (ts) => Date.parse(ts) || 0
const fresh = (ts) => ({ runner: null, started: ms(ts), ended: null, outcome: null, cost: 0, rows: [] })
const append = (u, rows) => (rows.length ? { ...u, rows: [...u.rows, ...rows].slice(-MAX_ROWS) } : u)

function step(u, ev, known) {
  switch (ev.type) {
    case 'unit.started': {
      const took = known && ev.runner ? [{ kind: 'log', text: `— ${ev.runner}` }] : []
      return { ...append(u, took), runner: ev.runner ?? null, ended: null, outcome: null }
    }
    case 'unit.finished': return { ...u, ended: ms(ev.ts), outcome: ev.outcome ?? null }
    case 'usage': return { ...u, cost: u.cost + (Number(ev.cost_usd) || 0) }
    default: return append(u, row(ev))
  }
}

// Folds one event into the feed; the feed it gets is never changed, and it comes back as is when the event adds nothing.
export function feed(f, ev) {
  if (ev.type === 'run.finished') return f.finished ? f : { ...f, finished: true }
  if (!ev.unit) return f
  const known = f.units[ev.unit]
  const next = step(known || fresh(ev.ts), ev, Boolean(known))
  return next === known ? f : { ...f, units: { ...f.units, [ev.unit]: next } }
}

// A terminal stays open this long after its unit ends, so the last lines are read before it folds into a card.
export const FOLD_MS = 4000
export const SIZE = { unit: { w: 200, h: 64 }, term: { w: 440, h: 280 } }
export const GAP = { x: 60, y: 24 }

// Failed units stay open: the error is what the person comes for.
export function openUnits(units, f, viewed, now) {
  const open = new Set()
  for (const u of units || []) {
    if (u.status === 'dropped') continue
    const e = f?.units[u.id]
    const ended = e?.ended ?? null
    const running = e && ended === null && !f.finished
    const justEnded = ended !== null && now - ended < FOLD_MS
    if (running || justEnded || e?.outcome === 'failed' || viewed.has(u.id)) open.add(u.id)
  }
  return open
}

// Phases left to right, each column as wide as its widest node; a node's size is the only thing that moves the rest.
export function layout(units, open) {
  const nodes = []
  let x = 0
  for (const { units: lane } of phases(units)) {
    let y = 0
    let width = 0
    for (const unit of lane) {
      const type = open.has(unit.id) ? 'term' : 'unit'
      const { w, h } = SIZE[type]
      nodes.push({ id: unit.id, type, position: { x, y }, width: w, height: h, data: { unit } })
      y += h + GAP.y
      width = Math.max(width, w)
    }
    x += width + GAP.x
  }
  const present = new Set(nodes.map((n) => n.id))
  const edges = nodes.flatMap(({ id, data: { unit } }) => (unit.deps || []).filter((dep) => present.has(dep))
    .map((dep) => ({ id: `${dep}->${id}`, source: dep, target: id, animated: unit.status === 'doing' })))
  return { nodes, edges }
}

export function place(nodes, saved) {
  return nodes.map((n) => {
    const at = saved?.[n.id]
    return Number.isFinite(at?.x) && Number.isFinite(at?.y) ? { ...n, position: { x: at.x, y: at.y } } : n
  })
}

const centre = (n) => ({ x: n.position.x + n.width / 2, y: n.position.y + n.height / 2 })

// The nearest node whose centre lies beyond this one's in that direction; a tie goes to the one more in line.
export function neighbour(nodes, id, dir) {
  const from = nodes.find((n) => n.id === id)
  if (!from) return null
  const c = centre(from)
  const horizontal = dir === 'left' || dir === 'right'
  const sign = dir === 'left' || dir === 'up' ? -1 : 1
  let best = null
  for (const n of nodes) {
    if (n === from) continue
    const m = centre(n)
    const along = (horizontal ? m.x - c.x : m.y - c.y) * sign
    if (along <= 0) continue
    const across = Math.abs(horizontal ? m.y - c.y : m.x - c.x)
    const dist = along * along + across * across
    if (!best || dist < best.dist || (dist === best.dist && across < best.across)) best = { id: n.id, dist, across }
  }
  return best ? best.id : null
}

const VIEWS = ['board', 'phases', 'canvas']

export const defaultView = (saved, live) => (VIEWS.includes(saved) ? saved : live ? 'canvas' : 'board')

// A log follows its end only while the person has not scrolled up to read.
export const atBottom = ({ scrollTop, scrollHeight, clientHeight }, slack = 24) => scrollHeight - scrollTop - clientHeight <= slack

// Whether the plan must reload: another run appeared, or the one shown has finished (the portal's rule, board.js).
export function changedRun(shown, latest) {
  if (!latest) return false
  return !shown || latest.run !== shown.run || latest.finished !== shown.finished
}
