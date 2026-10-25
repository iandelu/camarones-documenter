// Search, pure: the order of hits, the matched parts of a text, and what the ⌘K palette lists for a query.

const SPACES = { docs: 0, wiki: 1, notes: 2 }
const rank = (path, byPath) => SPACES[byPath[path]?.space] ?? 3

// Docs first, then the repo wikis, then the working notes (a stable sort keeps the score order inside each).
export const rankBySpace = (hits, byPath) => hits.slice().sort((a, b) => rank(a.path, byPath) - rank(b.path, byPath))

const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// [{text, hit}] for each run of a text: a hit is one of the query's terms (two or more word characters).
export function marked(text, q) {
  const terms = (q || '').match(/\w{2,}/g) || []
  if (!terms.length) return [{ text, hit: false }]
  const low = new Set(terms.map((w) => w.toLowerCase()))
  return text.split(new RegExp(`(${terms.map(escapeRe).join('|')})`, 'i')).filter(Boolean)
    .map((part) => ({ text: part, hit: low.has(part.toLowerCase()) }))
}

// What the palette lists. index: the docs tree; order: the docs in reading order; places: zones.paletteEntries();
// content: the full-text hits once they arrive. Each item: { href, label, sub?, path?, space?, where? }.
export function paletteGroups({ q, mode, index, order, byPath, places, content, t, hrefFor = (p) => `#/docs/${p}` }) {
  const low = (q || '').trim().toLowerCase()
  const page = (d, sub) => ({ href: hrefFor(d.path), label: d.title, path: d.path, space: d.space || 'docs', sub: sub ?? d.path })
  const titles = (low ? (index.docs || []).filter((d) => `${d.title} ${d.path}`.toLowerCase().includes(low))
    : order.map((p) => byPath[p]).filter(Boolean))
  const shown = (low ? rankBySpace(titles, byPath) : titles).slice(0, 8)
  const groups = []
  if (low && mode !== 'static') groups.push({ id: 'ask', label: t('homeAsk'), items: [{ href: `#/ask/${encodeURIComponent(q.trim())}`, label: q.trim() }] })
  groups.push({ id: 'places', label: t('zonesGroup'), items: places
    .map((e) => ({ href: e.href, label: t(e.key), where: e.key.startsWith('view.') ? t('zone.' + e.zone) : '' }))
    .filter((e) => !low || `${e.label} ${e.where}`.toLowerCase().includes(low)).slice(0, 8) })
  groups.push({ id: 'titles', label: t('titles'), items: shown.map((d) => page(d)) })
  if (content) {
    const seen = new Set(shown.map((d) => d.path))
    const hits = rankBySpace(content.filter((h) => !seen.has(h.path) && byPath[h.path]), byPath).slice(0, 8)
    groups.push({ id: 'content', label: t('content'), items: [
      ...hits.map((h) => page(byPath[h.path], (h.lines[0] || '').slice(0, 140))),
      { href: `#/search/${encodeURIComponent(q.trim())}`, label: t('searchAll', { q: q.trim() }) }] })
  }
  return groups
}
