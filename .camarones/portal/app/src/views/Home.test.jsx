import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import Home from './Home.jsx'

// Home reads the docs index through the plain scripts' bridge; a fake one stands in for it here.
const fake = (index, mode = 'live') => {
  globalThis.window = { CamaronLegacy: { tree: () => index, mode: () => mode, t: (k) => k, hrefFor: (p) => `#/docs/${p}` } }
}
afterEach(() => { delete globalThis.window })

const documented = { project: 'petclinic', repos: ['api', 'web'], views: [], kitGuides: [], docs: [{ path: 'domain/visits.md' }],
  summary: { total: 4, confirmed: 1, draft: 2, 'needs-reconfirm': 1 }, feedback: 0 }

test('a documented project: the question first, then each figure as a way in', () => {
  fake(documented)
  const out = renderToStaticMarkup(<Home />)
  expect(out).toContain('<form class="start-ask">')
  expect(out).toContain('aria-label="homeAsk"')
  expect(out).toContain('<a class="cu-card home-kpi ok" href="#/docs">')
  expect(out).toContain('href="#/review"')
  expect(out).not.toContain('home-tile')                                      // the zones live in the sidebar now
})

test('the export searches instead of asking', () => {
  fake(documented, 'static')
  expect(renderToStaticMarkup(<Home />)).toContain('aria-label="search"')
})

test('an empty project offers the first look in the app, and points to the app elsewhere', () => {
  const empty = { ...documented, docs: [], kitGuides: ['guides/tutorial.md'] }
  fake(empty, 'app')
  const app = renderToStaticMarkup(<Home />)
  expect(app).toContain('cu-btn--primary')
  expect(app).toContain('href="#/docs/guides/tutorial.md"')
  fake(empty, 'live')
  const live = renderToStaticMarkup(<Home />)
  expect(live).not.toContain('cu-btn--primary')
  expect(live).toContain('appOnly')
  fake(empty, 'static')
  expect(renderToStaticMarkup(<Home />)).not.toContain('#/pipeline')
})
