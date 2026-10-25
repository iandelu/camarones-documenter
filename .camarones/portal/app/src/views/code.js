// The code map, pure: graphify's graph folded by the server into modules → files (lib/codemap.py). Which view an
// address asks for, a module's files and folders, the search, the in-page path, and the graph to draw.

// #/code/<repo>/<mode>/<id>/<sub…>: mode f (a file), g (a module, optionally a sub-folder), graph (graphify's page).
export function codeRoute(rest, index) {
  const [repoArg = '', mode = '', idArg = '', ...subParts] = (rest || '').split('/')
  const maps = index.codeMaps || []
  const repo = repoArg || maps[0] || ((index.codeGraphs || []).includes('all') ? 'all' : '')
  return { repo, mode, id: Number(idArg === '' ? NaN : idArg), sub: subParts.filter(Boolean).join('/'),
    graph: mode === 'graph' || (!!repo && !maps.includes(repo)) }
}

export const codeView = (m, mode, id) => (mode === 'f' && m.files[id] ? 'file' : mode === 'g' && m.groups[id] ? 'group' : 'map')

const within = (f, sub) => !sub || f.sub === sub || f.sub.startsWith(sub + '/')
const busy = (f) => f.deg[0] + f.deg[1]
export const inSub = (m, g, sub) => m.files.map((f, i) => [i, f]).filter(([, f]) => f.group === g && within(f, sub))
  .sort(([, a], [, b]) => busy(b) - busy(a))
export const nextSeg = (f, sub) => (sub ? f.sub.slice(sub.length + 1) : f.sub).split('/')[0]
export const subHref = (repo, g, sub) => `#/code/${repo}/g/${g}${sub ? '/' + sub : ''}`

// A level with a single folder and no files of its own opens that folder.
export function singleFolder(m, g, sub, repo) {
  const segs = new Set(inSub(m, g, sub).map(([, f]) => nextSeg(f, sub)))
  return segs.size === 1 && !segs.has('') ? subHref(repo, g, sub ? `${sub}/${[...segs][0]}` : [...segs][0]) : null
}

export function searchFiles(m, q) {
  const s = (q || '').trim().toLowerCase()
  if (s.length < 2) return []
  const starts = (f) => (f.label.toLowerCase().startsWith(s) ? 0 : 1)
  return m.files.map((f, i) => [i, f]).filter(([, f]) => f.label.toLowerCase().includes(s) || f.path.toLowerCase().includes(s))
    .sort(([, a], [, b]) => starts(a) - starts(b) || busy(b) - busy(a)).slice(0, 10)
}

export function codeCrumbs(repo, m, view, id, sub) {
  const out = [{ label: repo, href: `#/code/${repo}` }]
  if (view === 'map') return out
  const g = view === 'file' ? m.files[id].group : id
  out.push({ label: m.groups[g].label, href: subHref(repo, g, '') })
  const segs = (view === 'file' ? m.files[id].sub : sub).split('/').filter(Boolean)
  segs.forEach((seg, i) => out.push({ label: seg, href: subHref(repo, g, segs.slice(0, i + 1).join('/')) }))
  return out
}

// The theme's colours mixed for the graph: vis-network draws on a canvas and wants plain hex.
export function mixHex(a, b, p) {
  const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16))
  const [x, y] = [rgb(a), rgb(b)]
  return '#' + x.map((v, i) => Math.round(v * p + y[i] * (1 - p)).toString(16).padStart(2, '0')).join('')
}

const SPLIT_AT = 18      // a package with more files than this is shown as its sub-folders first

// look: { colorOf(group, soft), t(key, vars), ink, muted, line, raise, accent } → { nodes, edges, layered, direction }
export function graphModel(m, view, id, sub, look) {
  const { colorOf, t, ink, muted, line, raise, accent } = look
  const nodes = []
  const weights = new Map()
  const font = { color: ink, size: 15, face: 'Inter, system-ui, -apple-system, Segoe UI, sans-serif', multi: 'md' }
  const box = (nid, label, g, extra = {}) => nodes.push({ id: nid, label, shape: 'box', margin: 10, font,
    color: { background: colorOf(g, true), border: colorOf(g), highlight: { background: colorOf(g, true), border: accent },
      hover: { background: colorOf(g, true), border: accent } }, borderWidth: 1.5, ...extra })
  const link = (a, b, w, dashed = false) => {
    if (a === undefined || b === undefined || a === b) return
    const k = `${a}|${b}|${dashed}`
    weights.set(k, (weights.get(k) || 0) + w)
  }
  const outside = (g) => {
    const nid = `g${g}`
    if (!nodes.some((n) => n.id === nid)) nodes.push({ id: nid, label: `→ ${m.groups[g].label}`, shape: 'box', margin: 8,
      font: { ...font, color: muted, size: 13 }, shapeProperties: { borderDashes: [4, 3] }, color: { background: raise, border: line } })
    return nid
  }
  if (view === 'map') {
    const max = Math.max(1, ...m.groups.map((g) => g.files))
    m.groups.forEach((g) => box(`g${g.id}`, `*${g.label}*\n${t('statFiles', { n: g.files })}`, g.id,
      { borderWidth: 2, font: { ...font, size: 14 + Math.round(10 * g.files / max) } }))
    m.links.forEach((l) => link(`g${l.s}`, `g${l.t}`, l.w))
  } else if (view === 'group') {
    const files = inSub(m, id, sub)
    const segs = new Set(files.map(([, f]) => nextSeg(f, sub)).filter(Boolean))
    const split = files.length > SPLIT_AT && segs.size >= 2
    const nodeOf = new Map()
    if (split) for (const seg of segs) {
      const n = files.filter(([, f]) => nextSeg(f, sub) === seg).length
      box(`s${seg}`, `*${seg}/*\n${t('statFiles', { n })}`, id, { borderWidth: 2 })
    }
    files.forEach(([i, f]) => { const seg = nextSeg(f, sub); if (split && seg) nodeOf.set(i, `s${seg}`) })
    files.filter(([i]) => !nodeOf.has(i)).slice(0, split ? 12 : 30).forEach(([i, f]) => { nodeOf.set(i, `f${i}`); box(`f${i}`, f.label, f.group) })
    files.forEach(([i, f]) => {
      const from = nodeOf.get(i)
      if (!from) return
      for (const [j, w] of f.out) {
        if (nodeOf.has(j)) link(from, nodeOf.get(j), w)
        else if (m.files[j].group !== id) link(from, outside(m.files[j].group), w, true)
      }
    })
  } else {
    const f = m.files[id]
    box(`f${id}`, `*${f.label}*`, f.group, { borderWidth: 3, font: { ...font, size: 18 }, color: { background: colorOf(f.group), border: accent } })
    const seen = new Set([id])
    const add = (j) => { if (!seen.has(j)) { seen.add(j); box(`f${j}`, m.files[j].label, m.files[j].group) } }
    for (const [j, w] of f.in) { add(j); link(`f${j}`, `f${id}`, w) }
    for (const [j, w] of f.out) { add(j); link(`f${id}`, `f${j}`, w) }
  }
  const edges = [...weights].map(([k, w]) => {
    const [from, to, dashed] = k.split('|')
    return { from, to, value: w, title: String(w), dashes: dashed === 'true', arrows: { to: { enabled: true, scaleFactor: 0.6 } },
      color: { color: muted, opacity: 0.5, highlight: accent, hover: accent } }
  })
  const layered = view !== 'group'          // the map top-down, a file between its users and what it uses; a module as a cloud
  return { nodes, edges, layered, direction: view === 'map' ? 'UD' : 'LR' }
}
