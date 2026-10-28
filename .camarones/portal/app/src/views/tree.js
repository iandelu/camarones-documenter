// The docs tree, pure: folders in the canonical section order, the reading order the pager and ⌘K follow, the working
// notes apart, and the Business view (what the system does and why, not how it is built).

export const BUSINESS_SECTIONS = ['overview', 'domain', 'flows', 'decisions']
export const BUSINESS_TYPES = ['overview', 'domain', 'glossary', 'business-flow', 'decision']
export const forBusiness = (d) => d.path === 'index.md' || BUSINESS_TYPES.includes(d.type)
  || BUSINESS_SECTIONS.includes(d.path.split('/')[0])

// { name, path, dirs: {name: node}, pages: [row], index: row | null }; the docs home (index.md) is left out.
export function buildTree(rows) {
  const root = { name: '', path: '', dirs: {}, pages: [], index: null }
  for (const d of rows) {
    if (d.path === 'index.md') continue
    const parts = d.path.split('/')
    let node = root
    parts.slice(0, -1).forEach((p, i) => {
      node = node.dirs[p] ||= { name: p, path: parts.slice(0, i + 1).join('/'), dirs: {}, pages: [], index: null }
    })
    if (node !== root && parts.at(-1) === 'index.md') node.index = d; else node.pages.push(d)
  }
  return root
}

export function sortedDirs(node, sections) {
  const rank = (n) => { const i = sections.indexOf(n); return i < 0 ? sections.length : i }
  return Object.values(node.dirs).sort((a, b) => (node.path ? 0 : rank(a.name) - rank(b.name)) || a.name.localeCompare(b.name))
}

// An ADR's status (the tree row's `adr_status`) as the key of its label and the tone of its pill; a page that is not an
// ADR has neither. A status nobody can read is shown as such, not hidden.
const ADR_STATUS = { proposed: 'info', accepted: 'ok', rejected: 'bad', superseded: 'warn', deprecated: 'warn', unknown: undefined }
export const adrStatusLabel = (status) => (status ? 'adr.' + (Object.hasOwn(ADR_STATUS, status) ? status : 'unknown') : '')
export const adrTone = (status) => (Object.hasOwn(ADR_STATUS, status) ? ADR_STATUS[status] : undefined)

export const byTitle = (lang) => (a, b) => a.title.localeCompare(b.title, lang || 'en')

export function flatten(node, sections, lang, out = []) {
  if (node.index) out.push(node.index.path)
  node.pages.slice().sort(byTitle(lang)).forEach((d) => out.push(d.path))
  sortedDirs(node, sections).forEach((n) => flatten(n, sections, lang, out))
  return out
}

// rows: the docs index; business: the Business view is on (the page being read stays in it).
export function docsTrees(rows, { sections = [], lang = '', business = false, active = '' } = {}) {
  const space = (d) => d.space || 'docs'
  const docs = buildTree(rows.filter((d) => space(d) === 'docs' && (!business || forBusiness(d) || d.path === active)))
  let notes = buildTree(rows.filter((d) => space(d) === 'notes'))
  if (!notes.pages.length && Object.keys(notes.dirs).length === 1 && notes.dirs.interview) notes = { ...notes.dirs.interview, path: '' }
  const home = rows.some((d) => d.path === 'index.md')
  const order = [...(home ? ['index.md'] : []), ...flatten({ ...docs, dirs: {} }, sections, lang),
    ...sortedDirs(docs, sections).flatMap((n) => flatten(n, sections, lang))]
  return { docs, notes, order, notesOrder: flatten(notes, sections, lang) }
}
