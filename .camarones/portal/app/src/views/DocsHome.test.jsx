import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test, vi } from 'vitest'
import DocsHome from './DocsHome.jsx'

// The docs home reads the docs index from the portal's state (core.js); a fake one stands in for it here.
const state = vi.hoisted(() => ({ core: {} }))
vi.mock('../core.js', () => ({ core: new Proxy({}, { get: (_, k) => state.core[k] }) }))

const page = (path, title, trust = 'draft', extra = {}) => ({ path, title, trust, space: 'docs', ...extra })
const index = {
  project: 'petclinic', sections: ['overview', 'domain'], kitGuides: [], summary: {},
  views: [{ id: 'index', kind: 'static' }, { id: 'flow_visit', kind: 'dynamic' }],
  docs: [page('index.md', 'PetClinic', 'confirmed', { description: 'The vet clinic' }), page('domain/index.md', 'Domain', 'confirmed'),
    page('domain/visits.md', 'Visits'), page('architecture/c4.md', 'C4 notes'), page('repos/api/wiki/a.md', 'A', 'draft', { space: 'wiki' })],
}
const fake = (idx) => {
  const byPath = Object.fromEntries(idx.docs.map((d) => [d.path, d]))
  state.core = { tree: () => idx, lang: () => '', t: (k, v = {}) => (v.n !== undefined ? `${k}:${v.n}` : k),
    hrefFor: (p) => `#/docs/${p}`, byPath: (p) => byPath[p], sectionLabel: (n) => n.toUpperCase() }
}
afterEach(() => { delete globalThis.localStorage })

test('figures, a card per section (C4 second, wikis last) and the system context', () => {
  fake(index)
  const out = renderToStaticMarkup(<DocsHome />)
  expect(out).toContain('<h1>PetClinic</h1>')
  expect(out).toContain('The vet clinic')
  expect(out).toContain('statPages:4')
  expect(out).toContain('statConfirmed:50')                     // 2 of 4 docs pages
  expect(out).toContain('statFlows:1')
  const cards = [...out.matchAll(/class="cu-card card link" href="([^"]+)"/g)].map((m) => m[1])
  // canonical sections first (domain), C4 second, folders outside the canon after, wikis last
  expect(cards).toEqual(['#/docs/domain/index.md', '#/c4', '#/docs/architecture/c4.md', '#/wikis'])
  expect(out).toContain('data-view="index"')
  expect(out).not.toMatch(/\p{Extended_Pictographic}/u)          // the section icons were emoji
})

test('the Business view keeps the business sections and says it is on', () => {
  fake(index)
  globalThis.localStorage = { getItem: () => 'business' }
  const out = renderToStaticMarkup(<DocsHome />)
  expect(out).not.toContain('architecture/c4.md')
  expect(out).not.toContain('#/wikis')
  expect(out).toContain('businessOn')
})
