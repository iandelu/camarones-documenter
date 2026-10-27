// The Plan's canvas: what each unit of a running plan is doing, from the run's events (runs/<run>/events.jsonl).
// Pure helpers: an event becomes display rows, and a run's events fold into one feed per unit.

export const MAX_ROWS = 500
export const LINE = 400
export const LINES = 20

export const GLYPH = { edit: '✎', read: '⌕', run: '▶', tool: '·', log: '»', error: '✕' }

const KIND = new Map([
  ...['Edit', 'Write', 'MultiEdit', 'NotebookEdit'].map((n) => [n, 'edit']),
  ...['Read', 'Glob', 'Grep', 'LS'].map((n) => [n, 'read']),
  ...['Bash', '$'].map((n) => [n, 'run']),
])

const cut = (s) => (s.length > LINE ? `${s.slice(0, LINE - 1)}…` : s)

function logRows(text) {
  const lines = String(text ?? '').split(/\r?\n/).filter((l) => l.trim())
  const rows = lines.slice(0, LINES).map((l) => ({ kind: 'log', text: cut(l) }))
  if (lines.length > LINES) rows.push({ kind: 'log', text: `… +${lines.length - LINES}` })
  return rows
}

export function row(ev) {
  switch (ev.type) {
    case 'tool.call': {
      const name = String(ev.name ?? '')
      const arg = ev.arg == null || ev.arg === '' ? '' : ` ${ev.arg}`
      return [{ kind: KIND.get(name) || 'tool', text: name + arg }]
    }
    case 'file.changed': return [{ kind: 'edit', text: `edit ${ev.path}` }]
    case 'log': return logRows(ev.text)
    case 'error': return [{ kind: 'error', text: String(ev.text ?? '') }]
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
