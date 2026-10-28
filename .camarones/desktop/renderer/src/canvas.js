// The Plan's canvas: what each unit of a running plan is doing, from the run's events (runs/<run>/events.jsonl), and
// the terminals open with you (terminals.js). Pure helpers: an event becomes display rows, a run's events fold into one
// feed per unit, the units and those terminals become positioned nodes (React Flow's shapes), and a key becomes the
// canvas's move or stays the terminal's.
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
// `status` is the plan's status of the unit when it ended: `ok` only says its agent exited 0. Each row gets the unit's
// next `seq`, its key once the cap drops the oldest rows. `last`: when it was last heard from, the only end a unit cut
// off by a stopped run has.
const fresh = (ts) => ({ runner: null, started: ms(ts), ended: null, outcome: null, status: null, cost: 0, rows: [], next: 0,
  last: ms(ts) })
const append = (u, rows) => (rows.length
  ? { ...u, next: u.next + rows.length, rows: [...u.rows, ...rows.map((r, i) => ({ ...r, seq: u.next + i }))].slice(-MAX_ROWS) }
  : u)

function step(u, ev, known) {
  switch (ev.type) {
    case 'unit.started': {
      const took = known && ev.runner ? [{ kind: 'log', text: `— ${ev.runner}` }] : []
      return { ...append(u, took), runner: ev.runner ?? null, ended: null, outcome: null, status: null }
    }
    case 'unit.finished':
      return { ...append(u, textRows('error', ev.error)), ended: ms(ev.ts), outcome: ev.outcome ?? null, status: ev.status ?? null }
    case 'usage': return { ...u, cost: u.cost + (Number(ev.cost_usd) || 0) }
    default: return append(u, row(ev))
  }
}

// Folds one event into the feed; the feed it gets is never changed, and it comes back as is when the event adds nothing.
export function feed(f, ev) {
  if (ev.type === 'run.finished') return f.finished ? f : { ...f, finished: true }
  if (!ev.unit) return f
  const known = f.units[ev.unit]
  const stepped = step(known || fresh(ev.ts), ev, Boolean(known))
  const next = ms(ev.ts) > stepped.last ? { ...stepped, last: ms(ev.ts) } : stepped
  return next === known ? f : { ...f, units: { ...f.units, [ev.unit]: next } }
}

// A terminal stays open this long after its unit ends, so the last lines are read before it folds into a card.
export const FOLD_MS = 4000
export const SIZE = { unit: { w: 200, h: 64 }, term: { w: 440, h: 280 } }
export const GAP = { x: 60, y: 24 }

// The 1 s clock is for what changes with time: a unit at work and a fold window. A failed terminal left open after
// the run shows a time that no longer moves.
export function clockRuns(f, now) {
  return Object.values(f?.units || {}).some((u) => (u.ended === null ? !f.finished : now - u.ended < FOLD_MS))
}

// Failed units stay open: the error is what the person comes for. A unit with a terminal of its own (`ptys`) is open
// too: its node is that terminal.
export function openUnits(units, f, viewed, now, ptys = new Set()) {
  const open = new Set()
  for (const u of units || []) {
    if (u.status === 'dropped') continue
    const e = f?.units[u.id]
    const ended = e?.ended ?? null
    const running = e && ended === null && !f.finished
    const justEnded = ended !== null && now - ended < FOLD_MS
    if (running || justEnded || e?.outcome === 'failed' || viewed.has(u.id) || ptys.has(u.id)) open.add(u.id)
  }
  return open
}

export const LANE = { id: 'lane:loose', h: 24 }

// Phases left to right, each column as wide as its widest node; a node's size is the only thing that moves the rest.
// An open unit with a terminal of its own (`pty`) is that terminal. The terminals of no unit (`loose`: the docs update)
// go in a row under the whole graph, below their lane's title, a label that is never picked, dragged or focused.
export function layout(units, open, { pty = new Set(), loose = [] } = {}) {
  const nodes = []
  let x = 0
  for (const { units: lane } of phases(units)) {
    let y = 0
    let width = 0
    for (const unit of lane) {
      const type = !open.has(unit.id) ? 'unit' : pty.has(unit.id) ? 'pty' : 'term'
      const { w, h } = SIZE[type === 'unit' ? 'unit' : 'term']
      nodes.push({ id: unit.id, type, position: { x, y }, width: w, height: h, data: { unit } })
      y += h + GAP.y
      width = Math.max(width, w)
    }
    x += width + GAP.x
  }
  const present = new Set(nodes.map((n) => n.id))
  const edges = nodes.flatMap(({ id, data: { unit } }) => (unit.deps || []).filter((dep) => present.has(dep))
    .map((dep) => ({ id: `${dep}->${id}`, source: dep, target: id, animated: unit.status === 'doing' })))
  if (loose.length) {
    const top = nodes.length ? Math.max(...nodes.map((n) => n.position.y + n.height)) + GAP.y : 0
    nodes.push({ id: LANE.id, type: 'lane', position: { x: 0, y: top }, width: SIZE.term.w, height: LANE.h, data: {},
      selectable: false, draggable: false, focusable: false })
    const { w, h } = SIZE.term
    loose.forEach((term, i) => nodes.push({ id: term.id, type: 'pty', position: { x: i * (w + GAP.x), y: top + LANE.h + GAP.y / 2 },
      width: w, height: h, data: { term } }))
  }
  return { nodes, edges }
}

export function place(nodes, saved) {
  return nodes.map((n) => {
    const at = saved?.[n.id]
    return Number.isFinite(at?.x) && Number.isFinite(at?.y) ? { ...n, position: { x: at.x, y: at.y } } : n
  })
}

const centre = (n) => ({ x: n.position.x + n.width / 2, y: n.position.y + n.height / 2 })

// The nearest node in that direction: one beside this one (its box overlaps on the other axis) before any diagonal,
// and a diagonal counts its offset off the line double.
export function neighbour(nodes, id, dir) {
  const origin = nodes.find((n) => n.id === id)
  if (!origin) return null
  const c = centre(origin)
  const horizontal = dir === 'left' || dir === 'right'
  const sign = dir === 'left' || dir === 'up' ? -1 : 1
  const span = (n) => (horizontal ? [n.position.y, n.position.y + n.height] : [n.position.x, n.position.x + n.width])
  const [lo, hi] = span(origin)
  let best = null
  for (const n of nodes) {
    if (n === origin) continue
    const m = centre(n)
    const along = (horizontal ? m.x - c.x : m.y - c.y) * sign
    if (along <= 0) continue
    const across = Math.abs(horizontal ? m.y - c.y : m.x - c.x)
    const [from, to] = span(n)
    const beside = lo < to && from < hi
    const cost = beside ? along : along * along + 4 * across * across
    const cand = { id: n.id, diagonal: beside ? 0 : 1, cost, across }
    if (!best || (cand.diagonal - best.diagonal || cand.cost - best.cost || cand.across - best.across) < 0) best = cand
  }
  return best ? best.id : null
}

const VIEWS = ['board', 'phases', 'canvas']

export const defaultView = (saved, live) => (VIEWS.includes(saved) ? saved : live ? 'canvas' : 'board')

// A run is on: the autopilot's job, or a run the Plan's poll says is on. The Plan adds the sessions open with you
// through planLive.
export const runLive = (run, pilot) => Boolean(pilot) || Boolean(run && !run.finished)

// What turns the Plan to the canvas: a run, or a session open with you on one of its units.
export const planLive = (run, pilot, units) => runLive(run, pilot) || (units || []).some((u) => Boolean(u.session?.live))

// With no view picked, the default turns to the canvas as soon as something is live during the visit (planLive: already
// on when the plan arrives, or started from the open plan) and holds there: following the run back to the board would take the
// canvas away the moment the run ends, with the failed unit's terminal and the last one's fold window.
export const arrivedLive = (held, live) => Boolean(held) || Boolean(live)

const ARROW = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' }

// What a key does on the canvas. Every key typed in a terminal is the agent's (Escape interrupts it, the arrows move in
// its prompt). A read-only log keeps its keys, but Escape still leaves a maximised node. On a node itself, Enter or
// Space opens it; anywhere in a node, an arrow without a modifier moves to the next one.
export function canvasKey(key, { inTerminal = false, inLog = false, maxed = false, node = false, self = false, mods = false } = {}) {
  if (inTerminal) return null
  if (key === 'Escape') return maxed ? 'leave' : null
  if (inLog || !node) return null
  if (key === 'Enter' || key === ' ') return self ? 'open' : null
  return mods ? null : ARROW[key] ?? null
}

// A log follows its end only while the person has not scrolled up to read.
export const atBottom = ({ scrollTop, scrollHeight, clientHeight }, slack = 24) => scrollHeight - scrollTop - clientHeight <= slack

const wait = (ms, signal) => new Promise((resolve) => {
  const timer = setTimeout(done, ms)
  function done() { clearTimeout(timer); signal?.removeEventListener('abort', done); resolve() }
  signal?.addEventListener('abort', done)
})

// A run's events from the start, until its end. A stream that ends or breaks before run.finished is opened again from
// the id it got to, unless `over()` says the run is over all the same (stopped from outside, it never logs its end and
// the server ends its stream once read); a run whose log is gone (404) or an abort ends it quietly.
export async function followRun(srv, run, onEvent, { signal, over = () => false, retry = 2000, sleep = wait } = {}) {
  let from
  let ended = false
  const seen = (ev) => { if (ev.type === 'run.finished') ended = true; onEvent(ev) }
  while (!ended && !signal?.aborted) {
    try {
      from = (await srv.stream(`runs/${run}/events`, seen, { from, signal })).id ?? from
    } catch (err) {
      if (signal?.aborted || err.status === 404) return
      from = err.id ?? from
    }
    if (ended || signal?.aborted || over()) return
    await sleep(retry, signal)
  }
}
