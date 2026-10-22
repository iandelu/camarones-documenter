// Pure state for the Pipeline tab: the plan's units plus what the latest run's events say about them.
export const COLUMNS = ['todo', 'running', 'blocked', 'done', 'dropped']

const blankLive = () => ({ runner: null, outcome: null, seconds: null, merge: null, tokens_in: 0, tokens_cache: 0,
  tokens_out: 0, cost_usd: 0, log: [] })

export function initial(pipeline, detail) {
  const units = {}
  for (const u of pipeline?.units || []) units[u.id] = { ...u, live: blankLive() }
  let state = { units, run: pipeline?.run || null, finished: Boolean(pipeline?.run?.finished) }
  for (const row of detail?.units || []) {
    const u = state.units[row.unit]
    if (!u) continue
    state.units[row.unit] = { ...u, live: { ...u.live, ...row, log: u.live.log } }
  }
  return state
}

const LOGGED = new Set(['tool.call', 'file.changed', 'log', 'error'])

export function apply(state, ev) {
  if (ev.type === 'run.finished') {                          // a unit the run never finished goes back where it was
    const units = Object.fromEntries(Object.entries(state.units).map(([id, u]) =>
      [id, u.status === 'doing' && u.live.runner && !u.live.outcome
        ? { ...u, status: u.live.before || 'todo', live: { ...u.live, outcome: 'interrupted' } } : u]))
    return { ...state, units, finished: true }
  }
  const u = ev.unit && state.units[ev.unit]
  if (!u) return state
  const live = { ...u.live }
  let status = u.status
  if (ev.type === 'unit.started') {
    Object.assign(live, blankLive(), { runner: ev.runner, isolation: ev.isolation, before: u.status })
    status = 'doing'
  } else if (ev.type === 'unit.finished') {
    Object.assign(live, { outcome: ev.outcome, seconds: ev.seconds })
    status = ev.status || status
  } else if (ev.type === 'usage') {
    live.tokens_in += ev.in || 0
    live.tokens_cache += (ev.cache_read || 0) + (ev.cache_write || 0)
    live.tokens_out += ev.out || 0
    live.cost_usd = Math.round((live.cost_usd + (ev.cost_usd || 0)) * 1e6) / 1e6
  } else if (ev.type.startsWith('merge.') || ev.type === 'gate.failed') live.merge = ev.type === 'merge.ok' ? 'merged' : ev.type
  if (LOGGED.has(ev.type)) live.log = [...live.log, line(ev)].slice(-200)
  return { ...state, units: { ...state.units, [ev.unit]: { ...u, status, live } } }
}

export function line(ev) {
  if (ev.type === 'tool.call') return `· ${ev.name}${ev.arg ? ` ${ev.arg}` : ''}`
  if (ev.type === 'file.changed') return `· edit ${ev.path}`
  if (ev.type === 'error') return `= error: ${ev.text}`
  return `» ${ev.text}`
}

export function column(u) {
  if (u.status === 'doing') return 'running'
  return COLUMNS.includes(u.status) ? u.status : 'todo'
}

export function columns(units) {
  const out = Object.fromEntries(COLUMNS.map((c) => [c, []]))
  for (const u of Object.values(units)) out[column(u)].push(u)
  for (const c of COLUMNS) out[c].sort((a, b) => a.phase - b.phase || a.id.localeCompare(b.id))
  return out
}

// A layered layout without a layout engine: one column per phase, units stacked in plan order.
export function layout(units, { dx = 260, dy = 76 } = {}) {
  const rows = {}
  const nodes = Object.values(units).map((u) => {
    const row = (rows[u.phase] = (rows[u.phase] ?? -1) + 1)
    return { id: u.id, position: { x: u.phase * dx, y: row * dy }, data: { unit: u }, type: 'unit' }
  })
  const ids = new Set(Object.keys(units))
  const edges = Object.values(units).flatMap((u) => (u.deps || []).filter((d) => ids.has(d))
    .map((d) => ({ id: `${d}->${u.id}`, source: d, target: u.id, animated: u.status === 'doing' })))
  return { nodes, edges }
}

// Whether the page must reload the pipeline: another run appeared, or the one shown is still going.
export function changedRun(shown, latest) {
  if (!latest) return false
  return !shown || latest.run !== shown.run || latest.finished !== shown.finished
}
