// The Plan's canvas: what each unit of a running plan is doing, from the run's events (runs/<run>/events.jsonl).
// Pure helpers: an event becomes display rows, and a run's events fold into one feed per unit.

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
