// Generated blocks in Markdown pages (lib/genblocks.py): `<!-- generated:<kind> repo=<repo> [id=<id>] [confirmed=<sha>
// by=<name>] sha=<hash> -->` … `<!-- /generated:<kind> -->`. HTML comments never reach the page (marked and DOMPurify
// drop them), so the markers become a wrapper with a small badge before the Markdown is rendered:
//   from the code      the kit wrote it and nobody has confirmed it
//   confirmed by <who> a person confirmed this diagram (the marker carries `confirmed=` and `by=`)
//   the code changed   the code moved on: a stale block, or a confirmed one whose code changed
const OPEN = /^<!-- generated:([\w-]+) repo=([\w.-]+)((?: [\w-]+=[^\s>]+)*) -->\s*$/
const attr = (attrs, name) => attrs.match(new RegExp(`(?:^| )${name}=([^\\s>]+)`))?.[1] ?? null

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

// The badge state: what the server said about the block (kind/repo/id) wins; without it the marker decides.
function stateOf(kind, repo, id, attrs, blocks) {
  const known = blocks.find((b) => b.kind === kind && b.repo === repo && (b.id ?? null) === id)
  const s = known?.state
  if (s === 'stale' || s === 'confirmed-stale') return 'stale'
  if (s === 'confirmed' || (!s && attr(attrs, 'confirmed'))) return 'confirmed'
  return 'from-code'
}

function badge(state, by, t) {
  if (state === 'stale') return t('gen.stale')
  if (state === 'confirmed') return t('gen.confirmed', { by: by || '' }).trim()
  return t('gen.fromCode')
}

// `md` with every block wrapped as <div class="gen-block" data-state="…"><p class="gen-badge">…</p>\n\n<body>\n\n</div>.
// Markers inside a code fence are left alone, and text without markers comes back as it was.
export function mark(md, blocks, t) {
  if (!md.includes('<!-- generated:')) return md
  const lines = md.split('\n')
  const out = []
  let fence = null
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const f = line.match(/^\s*(```|~~~)/)
    if (f) fence = fence ? (line.trim().startsWith(fence) ? null : fence) : f[1]
    const m = !fence && line.match(OPEN)
    if (m) {
      const end = lines.findIndex((l, j) => j > i && l.trim() === `<!-- /generated:${m[1]} -->`)
      if (end > i) {
        const attrs = m[3]
        const state = stateOf(m[1], m[2], attr(attrs, 'id'), attrs, blocks || [])
        const text = badge(state, attr(attrs, 'by'), t)
        out.push(`<div class="gen-block" data-state="${state}"><p class="gen-badge">${esc(text)}</p>`, '',
          ...lines.slice(i + 1, end), '', '</div>')
        i = end
        continue
      }
    }
    out.push(line)
  }
  return out.join('\n')
}
