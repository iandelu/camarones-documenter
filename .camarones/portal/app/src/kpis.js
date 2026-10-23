// Pure helpers of the KPIs tab: the headline tiles and the per-repo trust bar, from GET /api/kpis.
export const pct = (n, total) => (total ? `${Math.round((100 * n) / total)} %` : '—')

export function money(usd) {
  if (usd === null || usd === undefined) return '—'
  return usd >= 0.01 || usd === 0 ? `$${usd.toFixed(2)}` : `$${usd.toPrecision(2)}`
}

export function tiles(d) {
  const tr = d.trust || {}, c4 = d.c4 || {}, fr = d.freshness || {}, use = d.usefulness || {}
  const month = (d.runs || [])[0] || {}
  const out = (fr.outOfDate || []).length
  return [
    { key: 'confirmed', value: pct(tr.confirmed || 0, tr.pages || 0), sub: `${tr.confirmed || 0} / ${tr.pages || 0}` },
    { key: 'c4', value: pct(c4.confirmed || 0, c4.elements || 0), sub: `${c4.confirmed || 0} / ${c4.elements || 0}` },
    { key: 'outOfDate', value: String(out), sub: `${fr.unverified || 0}`, state: out ? 'warn' : 'ok' },
    { key: 'noAnswer', value: use.searches ? `${use.no_results_pct || 0} %` : '—', sub: `${use.searches || 0}`,
      state: (use.no_results_pct || 0) > 20 ? 'warn' : undefined },
    { key: 'plan', value: `${tr.plan_done || 0} / ${tr.plan_total || 0}`, sub: pct(tr.plan_done || 0, tr.plan_total || 0) },
    { key: 'cost', value: money(month.cost_usd ?? null), sub: `${month.done || 0}` },
    { key: 'eval', value: use.eval_score === null || use.eval_score === undefined ? '—' : `${Math.round(use.eval_score * 100)} %`,
      sub: '' },
  ]
}

export function segments(repo) {
  const total = repo.pages || 0
  if (!total) return []
  return [['confirmed', repo.confirmed], ['draft', repo.draft], ['needsReconfirm', repo.needsReconfirm]]
    .filter(([, n]) => n > 0).map(([key, n]) => ({ key, n, share: Math.round((100 * n) / total) }))
}
