// The Plan section's units (GET /api/pipeline) by what each asks of you, and the one action that moves it.
import { linkFor } from './summary.js'

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

export const waitsFor = (unit, units) => {
  const status = Object.fromEntries((units || []).map((u) => [u.id, u.status]))
  return (unit.deps || []).filter((d) => !['done', 'dropped'].includes(status[d]))
}

export function unitAction(u) {
  if (u.awaiting) return { kind: 'approve', label: 'unit.approve' }
  if (u.status === 'blocked') return { kind: 'retry', label: 'unit.retry' }
  const open = u.status === 'doing' || (u.status === 'todo' && u.ready)
  if (!open) return null
  if (u.runner !== 'agent') return linkFor(u)
  return u.status === 'doing' ? { kind: 'agent', mode: 'continue', label: 'unit.continue' }      // the agent: the section's picker
    : { kind: 'agent', mode: 'new', label: 'unit.start' }
}
