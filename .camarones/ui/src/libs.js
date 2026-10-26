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

// Versions as numbers where they are numbers: 8.3.10 after 8.3.9, v1.2 = 1.2.0, a pre-release (2.0.0-rc.1) before
// its release. Good enough to pick a fix among an advisory's own versions, not a full semver.
export function compareVersions(a, b) {
  const split = (v) => {
    const [main, pre = ''] = String(v || '').replace(/^v/, '').split(/-(.*)/s)
    return { parts: main.split(/[.+]/).map((x) => (/^\d+$/.test(x) ? Number(x) : x)), pre }
  }
  const x = split(a), y = split(b)
  for (let i = 0; i < Math.max(x.parts.length, y.parts.length); i++) {
    const p = x.parts[i] ?? 0, q = y.parts[i] ?? 0
    if (p === q) continue
    if (typeof p === 'number' && typeof q === 'number') return p - q
    return String(p).localeCompare(String(q))
  }
  if (x.pre === y.pre) return 0
  return !x.pre ? 1 : !y.pre ? -1 : x.pre.localeCompare(y.pre)
}

// The version that fixes every advisory with a fix: the highest of their `fixed`. null when none has a fix.
export function fixTarget(vulns) {
  const fixed = (vulns || []).map((v) => v.fixed).filter(Boolean)
  return fixed.length ? fixed.reduce((a, b) => (compareVersions(b, a) > 0 ? b : a)) : null
}

// One entry per advisory (the same one shows up in each repo that has the library), the worst first.
export function advisories(vulns) {
  const one = [...new Map((vulns || []).map((v) => [v.id, v])).values()]
  return one.sort((a, b) => (RANK[b.severity] || 0) - (RANK[a.severity] || 0) || String(a.id).localeCompare(String(b.id)))
}

// The inventory rows behind one line of the matrix (its key: `<ecosystem>|<name>`), by repo.
export const rowsOf = (rows, key) => rows.filter((r) => `${r.ecosystem}|${r.name}` === key)
  .sort((a, b) => a.repo.localeCompare(b.repo))
