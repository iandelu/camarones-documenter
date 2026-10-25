// Home's decisions, pure: is there anything documented yet, where the question goes, where each figure leads.

// Nothing of the project's own yet: the kit's guides and the interview notes do not count; a C4 model does.
export function emptyProject(index) {
  const kit = new Set(index.kitGuides || [])
  return !(index.docs || []).some((d) => (d.space || 'docs') === 'docs' && !kit.has(d.path) && d.type !== 'interview')
    && !(index.views || []).length
}

// Ask needs the server; the export searches the pages instead.
export function askHref(q, mode) {
  const s = (q || '').trim()
  if (!s) return ''
  return `${mode === 'static' ? '#/search/' : '#/ask/'}${encodeURIComponent(s)}`
}

export const kpiHref = (id) => (id === 'confirmed' ? '#/docs' : '#/review')

// The project home (docs/index.md) as the Home's "system" section: without its H1 (the section has its own heading);
// the TL;DR stays as the page's one-line answer. Frontmatter is left alone.
export function withoutH1(raw) {
  const fm = raw.match(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/)
  const head = fm ? fm[0] : ''
  return head + raw.slice(head.length).replace(/^# .*(\r?\n|$)/m, '')
}
