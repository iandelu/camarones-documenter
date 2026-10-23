import { describe, expect, it } from 'vitest'
import { money, pct, segments, tiles } from './kpis.js'

const d = {
  trust: { pages: 10, confirmed: 4, draft: 5, needs_reconfirm: 1, confirmed_pct: 40, plan_done: 6, plan_total: 20 },
  c4: { elements: 8, confirmed: 2, draft: 6 },
  freshness: { fresh: 3, suspect: 1, stale: 1, unverified: 5, outOfDate: ['a.md', 'b.md'] },
  usefulness: { searches: 20, no_results_pct: 15, eval_score: 0.82 },
  runs: [{ month: '2026-10', cost_usd: 1.23456, done: 3 }, { month: '2026-09', cost_usd: 0, done: 0 }],
  misses: [{ q: 'x', n: 2 }],
}

describe('KPI tiles', () => {
  it('formats shares and money', () => {
    expect(pct(1, 3)).toBe('33 %')
    expect(pct(0, 0)).toBe('—')
    expect(money(1.23456)).toBe('$1.23')
    expect(money(0.0016)).toBe('$0.0016')
    expect(money(null)).toBe('—')
  })

  it('gives one tile per question the team asks', () => {
    const byKey = Object.fromEntries(tiles(d).map((x) => [x.key, x]))
    expect(byKey.confirmed.value).toBe('40 %')
    expect(byKey.confirmed.sub).toBe('4 / 10')
    expect(byKey.c4.value).toBe('25 %')
    expect(byKey.outOfDate.value).toBe('2')
    expect(byKey.outOfDate.state).toBe('warn')
    expect(byKey.noAnswer.value).toBe('15 %')
    expect(byKey.cost.value).toBe('$1.23')
    expect(byKey.plan.value).toBe('6 / 20')
    expect(byKey.eval.value).toBe('82 %')
  })

  it('splits a repo into confirmed, draft and needs-reconfirm with no empty segment', () => {
    expect(segments({ pages: 4, confirmed: 1, draft: 3, needsReconfirm: 0 })).toEqual([
      { key: 'confirmed', n: 1, share: 25 }, { key: 'draft', n: 3, share: 75 }])
    expect(segments({ pages: 0, confirmed: 0, draft: 0, needsReconfirm: 0 })).toEqual([])
  })
})
