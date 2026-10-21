// `:::` directives in Markdown pages (R29). They read as plain text on GitHub and in an editor; the portal renders
// them, and lib/docs.py flattens them for agents (llms-full.txt, MCP). Supported:
//   :::tabs / ::tab Label …        tabbed alternatives (one per language, tool, environment)
//   :::cards / - [Title](link): text    a grid of link cards
//   :::steps / 1. …                 a numbered procedure
//   :::details Summary              folded content
//   :::tech / :::business           shown or hidden by the business/technical switch
export const KINDS = ['tabs', 'cards', 'steps', 'details', 'tech', 'business']
const OPEN = /^:::\s*(\w+)\s*(.*)$/
const CLOSE = /^:::\s*$/

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

// The page as a list of parts: {type: 'md', text} or {type: 'directive', kind, arg, body}. Nesting is not supported:
// a directive inside another stays plain text.
export function split(md) {
  const lines = md.split('\n')
  const parts = []
  let buf = []
  let fence = null
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const f = line.match(/^\s*(```|~~~)/)
    if (f) fence = fence ? (line.trim().startsWith(fence) ? null : fence) : f[1]
    const m = !fence && line.match(OPEN)
    if (m && KINDS.includes(m[1].toLowerCase())) {
      const end = lines.findIndex((l, j) => j > i && CLOSE.test(l))
      if (end > i) {
        if (buf.length) parts.push({ type: 'md', text: buf.join('\n') })
        buf = []
        parts.push({ type: 'directive', kind: m[1].toLowerCase(), arg: m[2].trim(), body: lines.slice(i + 1, end).join('\n') })
        i = end
        continue
      }
    }
    buf.push(line)
  }
  if (buf.length) parts.push({ type: 'md', text: buf.join('\n') })
  return parts
}

export function tabs(body) {
  const out = []
  for (const line of body.split('\n')) {
    const m = line.match(/^::tab\s+(.+)$/)
    if (m) out.push({ label: m[1].trim(), body: [] })
    else if (out.length) out.at(-1).body.push(line)
  }
  return out.map((t) => ({ label: t.label, body: t.body.join('\n') }))
}

export function cards(body) {
  return body.split('\n').map((l) => l.match(/^\s*[-*]\s+\[([^\]]+)\]\(([^)\s]+)\)\s*:?\s*(.*)$/)).filter(Boolean)
    .map((m) => ({ title: m[1], href: m[2], text: m[3] }))
}

// HTML for a whole page: `md` renders Markdown (marked.parse in the portal).
export function render(source, md) {
  let n = 0
  return split(source).map((p) => {
    if (p.type === 'md') return md(p.text)
    const id = `dv-${++n}`
    if (p.kind === 'tabs') {
      const ts = tabs(p.body)
      return `<div class="dv-tabs" data-id="${id}"><div class="dv-tablist" role="tablist">${ts.map((t, i) =>
        `<button type="button" role="tab" class="${i ? '' : 'on'}" data-tab="${i}">${esc(t.label)}</button>`).join('')}</div>${ts.map((t, i) =>
        `<div class="dv-tab" role="tabpanel" data-tab="${i}"${i ? ' hidden' : ''}>${md(t.body)}</div>`).join('')}</div>`
    }
    if (p.kind === 'cards') {
      return `<div class="cards dv-cards">${cards(p.body).map((c) => `<a class="card link" href="${esc(c.href)}"><div><b>${esc(c.title)}</b>` +
        `${c.text ? `<p class="muted small">${esc(c.text)}</p>` : ''}</div></a>`).join('')}</div>`
    }
    if (p.kind === 'steps') return `<div class="dv-steps">${md(p.body)}</div>`
    if (p.kind === 'details') return `<details class="dv-details"><summary>${esc(p.arg || 'Details')}</summary>${md(p.body)}</details>`
    return `<div class="dv-${p.kind}" data-audience="${p.kind}">${md(p.body)}</div>`
  }).join('\n')
}
