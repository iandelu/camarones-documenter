// Generated blocks in Markdown pages (lib/genblocks.py): `<!-- generated:<kind> repo=<repo> [id=<id>] [confirmed=<sha>
// by=<name>] sha=<hash> -->` … `<!-- /generated:<kind> -->`. HTML comments never reach the page (marked and DOMPurify
// drop them), so the markers become a wrapper with a small badge before the Markdown is rendered:
//   from the code      the kit wrote it and nobody has confirmed it
//   edited by hand     its body no longer matches what the kit wrote
//   confirmed by <who> a person confirmed this diagram (the marker carries `confirmed=` and `by=`)
//   the code changed   the code moved on: a stale block, a confirmed one whose code changed, or one whose source is gone
// The opening marker is read exactly as genblocks.parse_attrs reads it: it starts a line, attributes in any order,
// `repo=` required, `by=` a word or a quoted name (an unquoted name runs up to the next `name=`).
const W = '[\\p{L}\\p{N}_-]'
const OPEN = new RegExp(`^<!-- generated:(${W}+)((?:[ \\t][^\\n]*?)?)[ \\t]*-->[ \\t\\r]*$`, 'u')
const ATTR = new RegExp(`[ \\t]+(${W}+)=(?:"([^"\\n]*)"|([^\\n]*?))(?=[ \\t]+${W}+=|[ \\t]*$)`, 'uy')
const NAME = /^[\p{L}\p{N}_.-]+$/u

// {kind, repo, id, confirmed, by, sha} of an opening marker line (absent attributes are null), or null when the line
// is not one genblocks would read.
export function parseOpen(line) {
  const m = line.match(OPEN)
  if (!m) return null
  const attrs = m[2]
  const got = {}
  ATTR.lastIndex = 0
  while (ATTR.lastIndex < attrs.length) {
    const a = ATTR.exec(attrs)
    if (!a || Object.hasOwn(got, a[1])) return null
    got[a[1]] = a[2] ?? a[3]
  }
  const val = (k) => got[k] || null
  if (!NAME.test(val('repo') ?? '') || (val('id') !== null && !NAME.test(val('id')))) return null
  return { kind: m[1], repo: val('repo'), id: val('id'), confirmed: val('confirmed'), by: val('by'), sha: val('sha') }
}

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

// The badge state: what the server said about the block (kind/repo/id) wins; without it the marker decides.
function stateOf(open, blocks) {
  const known = blocks.find((b) => b.kind === open.kind && b.repo === open.repo && (b.id ?? null) === open.id)
  const s = known?.state
  if (s === 'stale' || s === 'confirmed-stale' || s === 'gone') return 'stale'
  if (s === 'edited') return 'edited'
  if (s === 'confirmed' || (!s && open.confirmed)) return 'confirmed'
  return 'from-code'
}

function badge(state, by, t) {
  if (state === 'stale') return t('gen.stale')
  if (state === 'edited') return t('gen.edited')
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
    const open = !fence && !f && parseOpen(line)
    if (open) {
      const end = lines.findIndex((l, j) => j > i && l.trim() === `<!-- /generated:${open.kind} -->`)
      if (end > i) {
        const state = stateOf(open, blocks || [])
        const text = badge(state, open.by, t)
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
