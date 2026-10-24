// How the portal is navigated: zones (Docs, Architecture, Plan, Quality, Review) that group the views, what is
// available in the static export, on the live server or in the desktop app (mode `app`: everything live has, plus
// the Taller, where machine work runs), the breadcrumbs of any address and the ⌘K entries.
// Pure functions over the index the portal loads (`tree`); legacy/app.js reaches them as window.CamaronZones.
// Labels are i18n keys of legacy/core.js: zone.<id>, zoned.<id>, view.<id>, viewd.<id>, sec.<section>.

const hasWiki = (index) => (index.docs || []).some((d) => d.space === 'wiki')
const hasCode = (index) => (index.codeMaps || []).length > 0 || (index.codeGraphs || []).length > 0

export const ZONES = [
  { id: 'docs', href: '#/docs', views: [
    { id: 'pages', href: '#/docs' },
    { id: 'wikis', href: '#/wikis', needs: (index, mode) => mode !== 'static' || hasWiki(index) }] },
  { id: 'arch', href: '#/arch', views: [
    { id: 'c4', href: '#/c4' },
    { id: 'code', href: '#/code', needs: hasCode },
    { id: 'data', href: '#/data', live: true },
    { id: 'libs', href: '#/libs', live: true }] },
  { id: 'plan', href: '#/plan', views: [{ id: 'pipeline', href: '#/pipeline', live: true },
    { id: 'interview', href: '#/interview', live: true }, { id: 'sync', href: '#/sync', live: true }] },
  { id: 'quality', href: '#/quality', views: [{ id: 'kpis', href: '#/kpis', live: true }, { id: 'ci', href: '#/ci', live: true }] },
  { id: 'review', href: '#/review', views: [{ id: 'review', href: '#/review' }] },
  { id: 'taller', href: '#/taller', views: [
    { id: 'generate', href: '#/generate', app: true }, { id: 'analyze', href: '#/analyze', app: true },
    { id: 'check', href: '#/check', app: true }, { id: 'interviews', href: '#/interviews', app: true },
    { id: 'team', href: '#/team', app: true }, { id: 'machine', href: '#/machine', app: true },
    { id: 'kitdev', href: '#/kitdev', app: true, needs: (index) => !!index.kitdev }] },
]

// The Taller's views are the catalog's zones (lib/catalog.py), one per kind of machine work.
export const TALLER = ['generate', 'analyze', 'check', 'interviews', 'team', 'machine', 'kitdev']

// The first segment of an address → its zone and view. Old addresses (doc, status, wiki) keep working.
const ROUTES = {
  docs: ['docs', 'pages'], doc: ['docs', 'pages'], wikis: ['docs', 'wikis'], wiki: ['docs', 'wikis'],
  c4: ['arch', 'c4'], code: ['arch', 'code'], data: ['arch', 'data'], libs: ['arch', 'libs'],
  pipeline: ['plan', 'pipeline'], interview: ['plan', 'interview'], sync: ['plan', 'sync'], kpis: ['quality', 'kpis'], ci: ['quality', 'ci'],
  review: ['review', 'review'], status: ['review', 'review'],
  ...Object.fromEntries(TALLER.map((v) => [v, ['taller', v]])),
}

const available = (view, mode, index) => (!view.live || mode !== 'static') && (!view.app || mode === 'app')
  && (!view.needs || view.needs(index, mode))

export function zonesFor(mode, index) {
  return ZONES.map((z) => ({ id: z.id, href: z.href,
    views: z.views.filter((v) => available(v, mode, index)).map((v) => ({ id: v.id, href: v.href })) }))
    .filter((z) => z.views.length)
}

const decode = (s) => { try { return decodeURIComponent(s) } catch { return s } }
const titleOf = (index, path) => (index.docs || []).find((d) => d.path === path)?.title

export function crumbs(hash, mode, index) {
  const m = (hash || '').replace(/^#/, '').match(/^\/([\w-]*)\/?(.*)$/)
  if (!m || !m[1]) return []
  const [, view, tail] = m
  const raw = tail.split('::')[0]
  const rest = decode(raw)
  if (view === 'search') return [{ key: 'search', href: null }, ...(rest ? [{ text: rest, href: null }] : [])]
  const zones = zonesFor(mode, index)
  const cover = zones.find((z) => z.id === view && z.href === `#/${view}`)
  if (cover && (!rest || !ROUTES[view])) return [{ key: `zone.${cover.id}`, href: cover.href }]
  const [zoneId, viewId] = ROUTES[view] || []
  const zone = zones.find((z) => z.id === zoneId)
  const target = zone?.views.find((v) => v.id === viewId)
  if (!target) return []
  const out = [{ key: `zone.${zone.id}`, href: zone.href }]
  if (viewId === 'pages') {
    if (!rest) return out
    const parts = rest.split('/')
    parts.slice(0, -1).forEach((seg, i) => {
      const folderIndex = `${parts.slice(0, i + 1).join('/')}/index.md`
      const href = folderIndex !== rest && titleOf(index, folderIndex) !== undefined ? `#/docs/${folderIndex}` : null
      out.push(i === 0 ? { key: `sec.${seg}`, href } : { text: seg, href })
    })
    return [...out, { text: titleOf(index, rest) || parts.at(-1), href: `#/docs/${raw}` }]
  }
  if (target.href !== zone.href) out.push({ key: `view.${viewId}`, href: target.href })
  if (view === 'wiki' && rest) {
    const [repo, ...relParts] = rest.split('/')
    out.push({ text: repo, href: `#/wiki/${raw.split('/')[0]}` })
    if (relParts.length) out.push({ text: titleOf(index, `repos/${repo}/${relParts.join('/')}`) || relParts.at(-1), href: null })
    return out
  }
  if (rest && view !== 'wikis') out.push({ text: rest, href: null })
  return out
}

export function paletteEntries(mode, index) {
  return zonesFor(mode, index).flatMap((z) => [
    { key: `zone.${z.id}`, href: z.href, zone: z.id },
    ...z.views.filter((v) => v.href !== z.href).map((v) => ({ key: `view.${v.id}`, href: v.href, zone: z.id })),
  ])
}

export function homeKpis(index) {
  const s = index.summary || {}
  if (!s.total) return []
  const reconfirm = s['needs-reconfirm'] || 0
  const out = [
    { id: 'confirmed', value: `${s.confirmed || 0}/${s.total}`, tone: s.confirmed > 0 ? 'ok' : null },
    { id: 'reconfirm', value: String(reconfirm), tone: reconfirm > 0 ? 'warn' : null },
    { id: 'drafts', value: String(s.draft || 0), tone: null },
  ]
  if (typeof index.feedback === 'number')
    out.push({ id: 'feedback', value: String(index.feedback), tone: index.feedback > 0 ? 'warn' : null })
  return out
}
