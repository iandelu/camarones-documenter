import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { PlanCost } from './index.js'
import { fmtDuration, fmtTokens, money, phaseRows, summary, topUnits } from './plancost.js'

const bill = (over = {}) => ({
  epoch: '2026-10-20T00:00:00Z', since: '2026-10-20T00:00:00Z', people: 2,
  seconds: { unattended: 24000, with_person: 6900, calendar: 259200 },
  tokens: { in: 4100000, out: 610000, cache_read: 30000000, cache_write: 8000000 },
  cost_usd: 48.2, complete: true,
  phases: [{ phase: 1, cost_usd: 9.1, seconds: 100 }, { phase: null, cost_usd: 2, seconds: 30 }],
  units: [{ unit: 'repo-wiki:api', cost_usd: 7.9 }, { unit: 'arch-system', cost_usd: 5.2 }, { unit: 'domain', cost_usd: null },
    { unit: 'data', cost_usd: 1 }],
  unpriced: [], unmeasured: [], unrecorded: 0, before: null,
  pricing: { revised: '2026-10-27', problems: [], overridden: [] }, notes: [],
  ...over,
})

test('durations, tokens and money read short, and a missing value is a dash', () => {
  expect([45, 600, 24000, 259200, null].map(fmtDuration)).toEqual(['45 s', '10 min', '6 h 40 min', '3 d', '—'])
  expect([4100000, 610000, 999, null].map(fmtTokens)).toEqual(['4.1 M', '610 k', '999', '—'])
  expect([48.2, 0, 0.004, null].map(money)).toEqual(['$48.20', '$0.00', '$0.0040', '—'])
})

test('the summary has the cost, the three times and the tokens', () => {
  expect(summary(bill())).toEqual({
    cost: '$48.20', unattended: '6 h 40 min', withPerson: '1 h 55 min', calendar: '3 d', since: '2026-10-20',
    people: 2, revised: '2026-10-27', tokens: { in: '4.1 M', cache: '38.0 M', out: '610 k' }, incomplete: false,
    gaps: { unpriced: 0, unmeasured: 0, unrecorded: 0 },
  })
})

test('phases keep their order and the ones with no phase are "other"; the top units are the first three', () => {
  expect(phaseRows(bill())).toEqual([{ phase: 1, cost: '$9.10', time: '1 min' }, { phase: 'other', cost: '$2.00', time: '30 s' }])
  expect(topUnits(bill())).toEqual([{ unit: 'repo-wiki:api', cost: '$7.90' }, { unit: 'arch-system', cost: '$5.20' },
    { unit: 'domain', cost: '—' }])
})

test('the card shows the cost as API-equivalent with its figures, top units and phases', () => {
  const out = renderToStaticMarkup(h(PlanCost, { bill: bill(), lang: 'en' }))
  for (const s of ['Plan from zero', '$48.20', 'API-equivalent', '6 h 40 min', 'repo-wiki:api', 'By phase', '2 people'])
    expect(out).toContain(s)
  expect(out).not.toContain('Incomplete')
  const es = renderToStaticMarkup(h(PlanCost, { bill: bill(), lang: 'es' }))
  expect(es).toContain('Plan desde 0')
  expect(es).toContain('equivalentes de la API')
})

test('an incomplete bill says what is missing in words, never as zero', () => {
  const out = renderToStaticMarkup(h(PlanCost, {
    bill: bill({ complete: false, unpriced: [{}], unmeasured: [{}, {}], unrecorded: 3,
      before: { cost_usd: 12.3, seconds: 7800 } }), lang: 'en' }))
  expect(out).toContain('Incomplete')
  expect(out).toContain('without a price: 1')
  expect(out).toContain('not measured: 2')
  expect(out).toContain('done with no record: 3')
  expect(out).toContain('Before the last reset: $12.30 · 2 h 10 min')
})

test('with nothing recorded the card says what will fill it', () => {
  const out = renderToStaticMarkup(h(PlanCost, { bill: bill({ units: [], phases: [], cost_usd: 0 }), lang: 'en' }))
  expect(out).toContain('Nothing recorded yet')
  expect(out).not.toContain('$0.00')
  const nobody = renderToStaticMarkup(h(PlanCost, { bill: bill({ units: [], phases: [], people: 0 }), lang: 'en' }))
  expect(nobody).not.toContain('0 people')
})

test('a refresh button only where the card can act', () => {
  expect(renderToStaticMarkup(h(PlanCost, { bill: bill(), lang: 'en' }))).not.toContain('<button')
  expect(renderToStaticMarkup(h(PlanCost, { bill: bill(), lang: 'en', onRefresh: () => {} }))).toContain('>Update</button>')
})
