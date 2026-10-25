import { expect, test } from 'vitest'
import { crumbs, homeKpis, locate, paletteEntries, zonesFor } from './zones.js'

const idx = {
  project: 'demo', repos: ['api', 'web'],
  docs: [
    { path: 'index.md', title: 'Home', space: 'docs', trust: 'confirmed' },
    { path: 'flows/alta-mascota.md', title: 'Alta de mascota', space: 'docs', trust: 'draft' },
    { path: 'repos/api/http-api.md', title: 'HTTP API', space: 'wiki', trust: 'needs-reconfirm' },
  ],
  views: [{ id: 'flow_checkout', kind: 'dynamic' }], codeGraphs: [], codeMaps: [],
  summary: { confirmed: 1, draft: 1, 'needs-reconfirm': 1, total: 3 }, feedback: 2,
}

test('static export: live-only zones and views are gone', () => {
  const z = zonesFor('static', idx)
  expect(z.map((x) => x.id)).toEqual(['docs', 'arch', 'review'])
  expect(z.find((x) => x.id === 'arch').views.map((v) => v.id)).toEqual(['c4'])
  expect(paletteEntries('static', idx).map((e) => e.href)).not.toContain('#/pipeline')
})

test('live: every zone, code only with a graph', () => {
  expect(zonesFor('live', idx).map((x) => x.id)).toEqual(['docs', 'arch', 'plan', 'quality', 'review'])
  expect(zonesFor('live', idx).find((x) => x.id === 'arch').views.map((v) => v.id)).toEqual(['c4', 'data', 'libs'])
  expect(zonesFor('live', { ...idx, codeMaps: ['api'] }).find((x) => x.id === 'arch').views[1].id).toBe('code')
  expect(paletteEntries('live', idx).map((e) => e.href)).not.toContain('#/boards')
})

test('wikis show in the static export only when there are wiki pages', () => {
  const noWikis = { ...idx, docs: idx.docs.filter((d) => d.space !== 'wiki') }
  expect(zonesFor('static', idx).find((x) => x.id === 'docs').views.map((v) => v.id)).toEqual(['pages', 'wikis'])
  expect(zonesFor('static', noWikis).find((x) => x.id === 'docs').views.map((v) => v.id)).toEqual(['pages'])
  expect(zonesFor('live', noWikis).find((x) => x.id === 'docs').views.map((v) => v.id)).toEqual(['pages', 'wikis'])
})

test('crumbs of a docs page decode, drop the anchor and use the title', () => {
  expect(crumbs('#/docs/flows/alta-mascota.md::paso-2', 'live', idx)).toEqual([
    { key: 'zone.docs', href: '#/docs' }, { key: 'sec.flows', href: null },
    { text: 'Alta de mascota', href: '#/docs/flows/alta-mascota.md' }])
  expect(crumbs('#/docs/flows/alta%20nueva.md', 'live', idx).at(-1))
    .toEqual({ text: 'alta nueva.md', href: '#/docs/flows/alta%20nueva.md' })
})

test('a folder with an index page links to it, as the old in-page crumbs did', () => {
  const withIndex = { ...idx, docs: [...idx.docs, { path: 'flows/index.md', title: 'Flujos', space: 'docs' }] }
  expect(crumbs('#/docs/flows/alta-mascota.md', 'live', withIndex)[1]).toEqual({ key: 'sec.flows', href: '#/docs/flows/index.md' })
  expect(crumbs('#/docs/flows/index.md', 'live', withIndex).map((c) => c.href))
    .toEqual(['#/docs', null, '#/docs/flows/index.md'])                      // the page itself is not linked twice
})

test('a malformed escape does not throw', () => {
  expect(crumbs('#/docs/flows/100%.md', 'live', idx).at(-1).text).toBe('100%.md')
})

test('zone covers and views', () => {
  expect(crumbs('#/docs', 'live', idx)).toEqual([{ key: 'zone.docs', href: '#/docs' }])
  expect(crumbs('#/arch', 'live', idx)).toEqual([{ key: 'zone.arch', href: '#/arch' }])
  expect(crumbs('#/review', 'live', idx)).toEqual([{ key: 'zone.review', href: '#/review' }])
  expect(crumbs('#/wikis', 'live', idx)).toEqual([{ key: 'zone.docs', href: '#/docs' }, { key: 'view.wikis', href: '#/wikis' }])
  expect(crumbs('#/boards/team-map', 'live', idx)).toEqual([])                  // boards were removed in 4.49
})

test('old routes keep their crumbs', () => {
  expect(crumbs('#/status', 'live', idx)).toEqual([{ key: 'zone.review', href: '#/review' }])
  expect(crumbs('#/doc/index.md', 'live', idx)[0]).toEqual({ key: 'zone.docs', href: '#/docs' })
  expect(crumbs('#/wiki/api/http-api.md', 'live', idx).map((c) => c.key || c.text))
    .toEqual(['zone.docs', 'view.wikis', 'api', 'HTTP API'])
  expect(crumbs('#/c4/flow_checkout', 'live', idx)).toEqual([
    { key: 'zone.arch', href: '#/arch' }, { key: 'view.c4', href: '#/c4' }, { text: 'flow_checkout', href: null }])
})

test('home, unknown and unavailable routes have no crumbs', () => {
  for (const h of ['', '#/', '#/nope', '#/nope/x']) expect(crumbs(h, 'live', idx)).toEqual([])
  expect(crumbs('#/pipeline', 'static', idx)).toEqual([])
  expect(crumbs('#/plan', 'static', idx)).toEqual([])
})

test('search keeps its query as a crumb', () => {
  expect(crumbs('#/search/fecha%20cita', 'live', idx)).toEqual([{ key: 'search', href: null }, { text: 'fecha cita', href: null }])
})

test('palette: one entry per available zone cover and view, a cover that is its view only once', () => {
  const live = paletteEntries('live', idx)
  expect(live.filter((e) => e.href === '#/review')).toEqual([{ key: 'zone.review', href: '#/review', zone: 'review' }])
  expect(live).toContainEqual({ key: 'view.libs', href: '#/libs', zone: 'arch' })
  expect(live).toContainEqual({ key: 'zone.quality', href: '#/quality', zone: 'quality' })
  expect(live.filter((e) => e.href === '#/docs')).toHaveLength(1)
})

test('home KPIs come from the index only, none for an empty project', () => {
  expect(homeKpis(idx)).toEqual([
    { id: 'confirmed', value: '1/3', tone: 'ok' }, { id: 'reconfirm', value: '1', tone: 'warn' },
    { id: 'drafts', value: '1', tone: null }, { id: 'feedback', value: '2', tone: 'warn' }])
  expect(homeKpis({ ...idx, docs: [], summary: { confirmed: 0, draft: 0, 'needs-reconfirm': 0, total: 0 } })).toEqual([])
  expect(homeKpis({ ...idx, feedback: undefined }).map((k) => k.id)).not.toContain('feedback')
  expect(homeKpis({ ...idx, summary: { ...idx.summary, 'needs-reconfirm': 0 }, feedback: 0 }).map((k) => k.tone))
    .toEqual(['ok', null, null, null])
  expect(homeKpis({ ...idx, summary: { ...idx.summary, confirmed: 0 } })[0]).toEqual({ id: 'confirmed', value: '0/3', tone: null })
})

test('desktop app: every live view plus the Taller, which the browser portal never shows', () => {
  expect(zonesFor('app', idx).map((x) => x.id)).toEqual(['docs', 'arch', 'plan', 'quality', 'review', 'taller'])
  expect(zonesFor('app', idx).find((x) => x.id === 'taller').views.map((v) => v.id))
    .toEqual(['generate', 'analyze', 'check', 'interviews', 'team', 'machine'])
  expect(zonesFor('app', { ...idx, kitdev: true }).find((x) => x.id === 'taller').views.map((v) => v.id)).toContain('kitdev')
  expect(zonesFor('live', idx).map((x) => x.id)).not.toContain('taller')
  expect(zonesFor('app', idx).find((x) => x.id === 'docs').views.map((v) => v.id)).toEqual(['pages', 'wikis'])
  expect(paletteEntries('app', idx).map((e) => e.href)).toContain('#/generate')
  expect(paletteEntries('live', idx).map((e) => e.href)).not.toContain('#/generate')
})

test('crumbs of a Taller view', () => {
  expect(crumbs('#/generate', 'app', idx)).toEqual([{ key: 'zone.taller', href: '#/taller' }, { key: 'view.generate', href: '#/generate' }])
  expect(crumbs('#/generate', 'live', idx)).toEqual([])
})

// The shell's sidebar marks where the reader is: the zone and, inside it, the view.
test('locate: the zone and view of an address, old addresses included', () => {
  expect(locate('#/docs/guides/a.md')).toEqual({ zone: 'docs', view: 'pages' })
  expect(locate('#/wiki/api/x.md')).toEqual({ zone: 'docs', view: 'wikis' })
  expect(locate('#/status')).toEqual({ zone: 'review', view: 'review' })
  expect(locate('#/machine')).toEqual({ zone: 'taller', view: 'machine' })
  expect(locate('#/arch')).toEqual({ zone: 'arch', view: null })
  expect(locate('#/search/x')).toEqual({ zone: null, view: null })
  expect(locate('')).toEqual({ zone: null, view: null })
})
