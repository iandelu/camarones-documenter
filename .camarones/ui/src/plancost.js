// The pure part of PlanCost: the bill of lib/harness/ledger.py (`camaron plan cost --json`, GET /api/plan/cost) as
// short words and rows. No React, no DOM, so it is tested in node. A value that is missing is "—", never 0.

const DASH = '—'

export function money(usd) {
  if (usd === null || usd === undefined) return DASH
  return usd >= 0.01 || usd === 0 ? `$${usd.toFixed(2)}` : `$${usd.toPrecision(2)}`
}

export function fmtDuration(s) {
  if (s === null || s === undefined) return DASH
  if (s < 60) return `${Math.round(s)} s`
  if (s < 3600) return `${Math.floor(s / 60)} min`
  if (s < 172800) return `${Math.floor(s / 3600)} h ${Math.floor((s % 3600) / 60)} min`
  return `${Math.round(s / 86400)} d`
}

export function fmtTokens(n) {
  if (n === null || n === undefined) return DASH
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)} M`
  if (n >= 1e3) return `${Math.round(n / 1e3)} k`
  return String(n)
}

export function summary(b) {
  const s = b.seconds || {}, t = b.tokens || {}
  const gaps = { unpriced: (b.unpriced || []).length, unmeasured: (b.unmeasured || []).length, unrecorded: b.unrecorded || 0 }
  return {
    cost: money(b.cost_usd), unattended: fmtDuration(s.unattended), withPerson: fmtDuration(s.with_person),
    calendar: fmtDuration(s.calendar), since: String(b.since || '').slice(0, 10), people: b.people || 0,
    revised: (b.pricing || {}).revised || '',
    tokens: { in: fmtTokens(t.in), cache: fmtTokens((t.cache_read || 0) + (t.cache_write || 0)), out: fmtTokens(t.out) },
    incomplete: !b.complete || gaps.unrecorded > 0, gaps,
  }
}

export const phaseRows = (b) => (b.phases || []).map((p) => ({ phase: p.phase ?? 'other', cost: money(p.cost_usd), time: fmtDuration(p.seconds) }))

export const topUnits = (b, n = 3) => (b.units || []).slice(0, n).map((u) => ({ unit: u.unit ?? DASH, cost: money(u.cost_usd) }))
