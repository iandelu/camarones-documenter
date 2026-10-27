import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { CostView, Reset } from './sections/Plan.jsx'
import { setLang } from './i18n.js'

const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }
const render = () => renderToStaticMarkup(<Reset srv={srv} jobs={null} onChanged={() => {}} />)

afterEach(() => setLang('es'))

// `docs reset`, previewed first: redo is the default (it deletes nothing), and the button that acts only shows once a
// preview of the chosen options has listed what it does.
test('the reset card offers redo or wipe, redo first, and only a preview before anything runs', () => {
  const out = render()
  expect(out).toContain('Empezar la documentación otra vez')
  expect(out).toMatch(/role="radio" aria-checked="true"[^>]*>Rehacer</)
  expect(out).toMatch(/role="radio" aria-checked="false"[^>]*>Borrar y empezar de cero</)
  expect(out).toContain('No borra nada')
  expect(out).toMatch(/>Ver qué haría<\/button>/)
  expect(out.split('<dialog')[0]).not.toContain('cu-btn--danger')            // the dialog's own stays closed
  expect(out).not.toMatch(/<dialog[^>]* open/)
})

test('the reset card exists in English', () => {
  setLang('en')
  const out = render()
  expect(out).toContain('Start the docs again')
  expect(out).toMatch(/>See what it would do<\/button>/)
})


// What the plan took from zero: the shared card once POST /api/plan/cost answered, the server's message if it failed.
const bill = { since: '2026-10-20', people: 1, seconds: { unattended: 600, with_person: 0, calendar: 600 },
  tokens: { in: 1000, out: 10, cache_read: 0, cache_write: 0 }, cost_usd: 1.5, complete: true,
  phases: [{ phase: 1, cost_usd: 1.5, seconds: 600 }], units: [{ unit: 'discovery:api', cost_usd: 1.5 }],
  unpriced: [], unmeasured: [], unrecorded: 0, before: null, pricing: { revised: '2026-10-27' }, notes: [] }

test('the plan cost card shows the bill and can be updated', () => {
  const out = renderToStaticMarkup(<CostView bill={bill} onRefresh={() => {}} />)
  expect(out).toContain('$1.50')
  expect(out).toContain('discovery:api')
  expect(out).toMatch(/<button[^>]*>(Update|Actualizar)<\/button>/)
})

test('a plan cost that could not be read says why and offers to retry', () => {
  const out = renderToStaticMarkup(<CostView error="plan.yaml is damaged" onRetry={() => {}} />)
  expect(out).toContain('plan.yaml is damaged')
  expect(out).toContain('<button')
})

test('nothing is drawn while the plan cost loads', () => {
  expect(renderToStaticMarkup(<CostView />)).toBe('')
})
