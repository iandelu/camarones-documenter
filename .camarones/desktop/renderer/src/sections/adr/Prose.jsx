// An ADR's section read-only: the Markdown a person or the kit wrote, drawn as headings, paragraphs, lists, tables,
// quotes and code. Links stay text (the window never navigates away from the app), HTML is text, comments are dropped.

const COMMENT = /<!--[\s\S]*?-->/g
const ITEM = /^\s*(?:[-*+]|\d+[.)])\s+/
const FENCE = /^\s*(```|~~~)/
const cells = (line) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim())
const ruleRow = (row) => row.every((c) => /^:?-{2,}:?$/.test(c))
const words = (s) => s.replace(/\s+/g, ' ').trim()
const opens = (line) => FENCE.test(line) || /^#{1,6}\s/.test(line) || /^\s*[|>]/.test(line)     // a block that ends a list

// The blocks of a Markdown text, in order: {type: 'h', level, text} · 'p' · 'ul' | 'ol' (items) · 'table' (head, rows) ·
// 'code' · 'quote'. A nested list reads flat; a paragraph joins its lines.
export function blocks(md) {
  const lines = String(md ?? '').replace(COMMENT, '').replace(/\r\n?/g, '\n').split('\n')
  const out = []
  let para = []
  const flush = () => { if (para.length) out.push({ type: 'p', text: words(para.join(' ')) }); para = [] }
  for (let i = 0; i < lines.length;) {
    const line = lines[i]
    const fence = line.match(FENCE)
    if (fence) {
      flush()
      const body = []
      for (i++; i < lines.length && !lines[i].trim().startsWith(fence[1]); i++) body.push(lines[i])
      out.push({ type: 'code', text: body.join('\n') })
      i++
    } else if (!line.trim()) {
      flush(); i++
    } else if (/^#{1,6}\s/.test(line)) {
      flush()
      const [, hashes, text] = line.match(/^(#{1,6})\s+(.*)$/)
      out.push({ type: 'h', level: hashes.length, text: words(text) }); i++
    } else if (/^\s*\|/.test(line)) {
      flush()
      const rows = []
      for (; i < lines.length && /^\s*\|/.test(lines[i]); i++) rows.push(cells(lines[i]))
      const [head, ...rest] = rows
      out.push({ type: 'table', head, rows: rest.filter((r) => !ruleRow(r)) })
    } else if (ITEM.test(line)) {
      flush()
      const items = []
      const ordered = /^\s*\d/.test(line)
      for (; i < lines.length && lines[i].trim() && !opens(lines[i]); i++) {
        if (ITEM.test(lines[i])) items.push(words(lines[i].replace(ITEM, '')))
        else items[items.length - 1] = words(`${items[items.length - 1]} ${lines[i]}`)
      }
      out.push({ type: ordered ? 'ol' : 'ul', items })
    } else if (/^\s*>/.test(line)) {
      flush()
      const quote = []
      for (; i < lines.length && /^\s*>/.test(lines[i]); i++) quote.push(lines[i].replace(/^\s*>\s?/, ''))
      out.push({ type: 'quote', text: words(quote.join(' ')) })
    } else {
      para.push(line); i++
    }
  }
  flush()
  return out
}

const INLINE = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)\s]+\))/
function inline(text) {
  return String(text).split(INLINE).filter(Boolean).map((part, i) => {
    if (/^`[^`]+`$/.test(part)) return <code key={i}>{part.slice(1, -1)}</code>
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={i}>{part.slice(2, -2)}</strong>
    const link = part.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/)
    return link ? <span key={i} className="dk-prose-link" title={link[2]}>{link[1]}</span> : part
  })
}

export function Prose({ text }) {
  return (
    <div className="dk-prose">
      {blocks(text).map((b, i) => {
        if (b.type === 'h') { const H = `h${Math.min(6, Math.max(3, b.level + 1))}`; return <H key={i}>{inline(b.text)}</H> }
        if (b.type === 'ul' || b.type === 'ol') { const L = b.type; return <L key={i}>{b.items.map((it, k) => <li key={k}>{inline(it)}</li>)}</L> }
        if (b.type === 'code') return <pre key={i} className="dk-log">{b.text}</pre>
        if (b.type === 'quote') return <blockquote key={i}>{inline(b.text)}</blockquote>
        if (b.type === 'table') return (
          <div key={i} className="dk-scroll"><table className="dk-table">
            <thead><tr>{b.head.map((c, k) => <th key={k}>{inline(c)}</th>)}</tr></thead>
            <tbody>{b.rows.map((r, k) => <tr key={k}>{r.map((c, j) => <td key={j}>{inline(c)}</td>)}</tr>)}</tbody>
          </table></div>
        )
        return <p key={i}>{inline(b.text)}</p>
      })}
    </div>
  )
}
