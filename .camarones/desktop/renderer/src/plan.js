// The Plan section's units (GET /api/pipeline) by what each asks of you, and the one action that moves it.
import { INTERVIEW_TYPES, linkFor } from './summary.js'

export function groups(units) {
  const pick = (test) => (units || []).filter(test).sort((a, b) => a.phase - b.phase)
  return {
    awaiting: pick((u) => u.awaiting),
    blocked: pick((u) => u.status === 'blocked' && !u.awaiting),
    doing: pick((u) => u.status === 'doing'),
    ready: pick((u) => u.status === 'todo' && u.ready),
    waiting: pick((u) => u.status === 'todo' && !u.ready),
    done: pick((u) => u.status === 'done'),
  }
}

// A unit's colour on the board (app.css .tone-*): running yellow, done green, ready white, blocked red, awaiting
// your approval in the accent, waiting for others dim.
export function tone(u) {
  if (u.awaiting) return 'awaiting'
  if (u.status === 'doing') return 'running'
  if (u.status === 'todo') return u.ready ? 'ready' : 'waiting'
  return ['done', 'blocked', 'dropped'].includes(u.status) ? u.status : 'waiting'
}

// The board, like the portal's: what you can start, what runs, what needs you (approve or retry), what waits, what
// is done. Dropped units are left out.
export const COLUMNS = ['ready', 'running', 'attention', 'waiting', 'done']
const COLUMN = { ready: 'ready', running: 'running', awaiting: 'attention', blocked: 'attention', waiting: 'waiting', done: 'done' }
const byPlan = (a, b) => a.phase - b.phase || (a.awaiting === b.awaiting ? 0 : a.awaiting ? -1 : 1) || a.id.localeCompare(b.id)
export function board(units) {
  return COLUMNS.map((key) => ({ key, units: (units || []).filter((u) => COLUMN[tone(u)] === key).sort(byPlan) }))
}

// The phases, left to right like the portal's graph: each lane with its units and how many are done.
export function phases(units) {
  const lanes = new Map()
  for (const u of units || []) {
    if (u.status === 'dropped') continue
    if (!lanes.has(u.phase)) lanes.set(u.phase, [])
    lanes.get(u.phase).push(u)
  }
  return [...lanes.entries()].sort((a, b) => a[0] - b[0])
    .map(([phase, list]) => ({ phase, units: list.sort(byPlan), done: list.filter((u) => u.status === 'done').length }))
}

export const waitsFor = (unit, units) => {
  const status = Object.fromEntries((units || []).map((u) => [u.id, u.status]))
  return (unit.deps || []).filter((d) => !['done', 'dropped'].includes(status[d]))
}

// plan: what the pipeline says of the whole plan ({interviews}: the mode, null while nobody chose it: the agent
// refuses an interview unit until then, so the row asks for it).
export function unitAction(u, plan = {}) {
  if (u.awaiting) return { kind: 'approve', label: 'unit.approve' }
  if (u.status === 'blocked') return { kind: 'retry', label: 'unit.retry' }
  const open = u.status === 'doing' || (u.status === 'todo' && u.ready)
  if (!open) return null
  if (u.runner !== 'agent') return linkFor(u)
  if (plan.interviews === null && INTERVIEW_TYPES.includes(u.type)) return { kind: 'mode', label: 'iv.choose' }
  return u.status === 'doing' ? { kind: 'agent', mode: 'continue', label: 'unit.continue' }      // the agent: the section's picker
    : { kind: 'agent', mode: 'new', label: 'unit.start' }
}
