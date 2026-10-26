// Pure helpers of the Libraries table (the portal and the desktop app), from GET /api/inventory (lib/inventory.py rows).
const RANK = { critical: 4, high: 3, medium: 2, low: 1, unknown: 1 }

export function worst(vulns) {
  if (!vulns || !vulns.length) return null
  return vulns.reduce((a, b) => ((RANK[b.severity] || 0) > (RANK[a] || 0) ? b.severity : a), vulns[0].severity)
}

export function applyFilter(rows, f) {
  const q = (f.q || '').trim().toLowerCase()
  return rows.filter((r) => (!f.category || r.category === f.category) && (!f.language || r.language === f.language)
    && (!f.repo || r.repo === f.repo) && (!f.scope || r.scope === f.scope) && (!f.vulnerable || (r.vulns || []).length)
    && (!q || r.name.toLowerCase().includes(q)))
}

export function matrix(rows) {
  const repos = [...new Set(rows.map((r) => r.repo))].sort()
  const byKey = new Map()
  for (const r of rows) {
    const key = `${r.ecosystem}|${r.name}`
    const item = byKey.get(key) || { key, name: r.name, ecosystem: r.ecosystem, category: r.category, language: r.language,
      cells: {}, vulns: [], drift: false }
    item.cells[r.repo] = { version: r.version || r.declared || (r.managedBy ? 'managed' : ''), scope: r.scope, vulns: r.vulns || [] }
    item.vulns.push(...(r.vulns || []))
    item.drift = item.drift || r.drift
    byKey.set(key, item)
  }
  const items = [...byKey.values()].map((x) => ({ ...x, worst: worst(x.vulns) }))
  items.sort((a, b) => (RANK[b.worst] || 0) - (RANK[a.worst] || 0) || a.category.localeCompare(b.category) || a.name.localeCompare(b.name))
  return { repos, items }
}

export function facets(rows) {
  const count = (key) => Object.entries(rows.reduce((acc, r) => ({ ...acc, [r[key]]: (acc[r[key]] || 0) + 1 }), {}))
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  return { category: count('category'), language: count('language'), repo: count('repo'), scope: count('scope') }
}
