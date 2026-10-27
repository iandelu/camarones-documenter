import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test, vi } from 'vitest'
import Home from './Home.jsx'

// Home reads the docs index from the portal's state (core.js); a fake one stands in for it here.
const state = vi.hoisted(() => ({ core: {} }))
vi.mock('../core.js', () => ({ core: new Proxy({}, { get: (_, k) => state.core[k] }) }))
const fake = (index, mode = 'live') => {
  state.core = { tree: () => index, mode: () => mode, t: (k) => k, hrefFor: (p) => `#/docs/${p}`, lang: () => '',
    byPath: (p) => index.docs.find((d) => d.path === p) }
}

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

// The first look runs in the desktop app (Docs); the portal shows no button it cannot run.
test('an empty project leads to the Pipeline and the tutorial, with no first-look button', () => {
  const empty = { ...documented, docs: [], kitGuides: ['guides/tutorial.md'] }
  fake(empty, 'live')
  const live = renderToStaticMarkup(<Home />)
  expect(live).not.toContain('cu-btn--primary')
  expect(live).not.toContain('joblog')
  expect(live).toContain('href="#/pipeline"')
  expect(live).toContain('href="#/docs/guides/tutorial.md"')
  fake(empty, 'static')
  expect(renderToStaticMarkup(<Home />)).not.toContain('#/pipeline')
})

// main (553a609): the project home, when there is one, is the Home's "The system" section, before the figures.
test('the project home is the system section, only when it exists', () => {
  fake({ ...documented, docs: [...documented.docs, { path: 'index.md' }] })
  const out = renderToStaticMarkup(<Home />)
  expect(out).toMatch(/<section class="start-sec start-home" aria-labelledby="home-system"><h2 class="t-impact" id="home-system">home\.system<\/h2><div class="start-home-body"><\/div><\/section>/)
  expect(out.indexOf('start-home')).toBeLessThan(out.indexOf('home-kpis'))
  fake(documented)
  expect(renderToStaticMarkup(<Home />)).not.toContain('start-home')
})
