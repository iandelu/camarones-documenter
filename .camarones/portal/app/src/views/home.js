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
