// What a command's --json gives back, shaped for one generic view (the portal's Taller, the app's panels): a list of rows becomes a table, an
// object label / value pairs (nested values summarised), anything else text. Pure, so vitest checks it.
const summary = (v) => {
  if (Array.isArray(v)) return `${v.length} items`
  if (v && typeof v === 'object') return Object.entries(v).slice(0, 4).map(([k, x]) => `${k}: ${typeof x === 'object' && x ? '…' : x}`).join(' · ')
  return v === undefined ? null : v
}

export function shape(result) {
  if (result == null || (Array.isArray(result) && !result.length)) return { kind: 'empty' }
  if (Array.isArray(result) && result.every((r) => r && typeof r === 'object' && !Array.isArray(r))) {
    const cols = [...new Set(result.flatMap((r) => Object.keys(r)))].slice(0, 8)
    return { kind: 'table', cols, rows: result.map((r) => cols.map((c) => summary(r[c]))) }
  }
  if (typeof result === 'object' && !Array.isArray(result)) {
    return { kind: 'pairs', rows: Object.entries(result).map(([k, v]) => [k, summary(v)]) }
  }
  return { kind: 'text', text: String(result) }
}

const ORDER = ['critical', 'high', 'medium', 'moderate', 'low', 'unknown']

// lib/inventory.py libraries → [[severity, count]] from the worst down.
export function severities(libraries) {
  const n = {}
  for (const l of libraries || []) for (const v of l.vulns || []) n[v.severity] = (n[v.severity] || 0) + 1
  return Object.entries(n).sort(([a], [b]) => (ORDER.indexOf(a) + 99 * (ORDER.indexOf(a) < 0)) - (ORDER.indexOf(b) + 99 * (ORDER.indexOf(b) < 0)))
}
