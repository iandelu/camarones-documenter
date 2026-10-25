// A doc page's decisions, pure: which banners it carries, its neighbours in the reading order, a new page's path.

// d: the page as api/doc returns it; row: its entry in the docs index; lang: the reader's ('' = English).
// Each banner: { tone, key } (+ code: the cited files a stale page lost; draft: the one that carries Confirm).
export function pageBanners(d, row, lang) {
  const out = []
  const i18n = lang ? (row.i18n || {})[lang] : ''
  if (lang && !d.exists) out.push({ tone: 'info', key: 'noTranslation' })
  if (lang && d.exists && i18n === 'outdated') out.push({ tone: 'warn', key: 'outdatedTranslation' })
  if (d.trust === 'needs-reconfirm') out.push({ tone: 'info', key: 'banner.needs-reconfirm' })
  if (d.fresh === 'suspect' || d.fresh === 'stale')
    out.push({ tone: 'warn', key: 'banner.' + d.fresh, code: [...(d.freshness?.missing || []), ...(d.freshness?.changed || [])].join(', ') })
  if (d.trust === 'draft' && row.space !== 'notes') out.push({ tone: 'warn', key: 'banner.draft', draft: true })
  return out
}

export function pager(order, path) {
  const i = order.indexOf(path)
  return i < 0 ? null : { prev: order[i - 1] || null, next: order[i + 1] || null }
}

export const newPagePath = (title) => 'guides/' + title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + '.md'
