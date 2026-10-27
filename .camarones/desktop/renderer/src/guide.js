// The kit's guides as data, pure: the Markdown subset they are written in → blocks the Guide renders as React elements
// (no Markdown library, no innerHTML), their chapters, links, addresses and search. Markers are HTML comments alone on
// a line (<!-- go:plan -->, cmd:, portal:, tour:): invisible in the portal and on GitHub, buttons here.

const MARKER = /^<!--\s*(go|cmd|portal|tour):(\S+)\s*-->\s*$/
const CALLOUT = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$/i
const ITEM = /^(\s*)([-*]|\d+\.)\s+(.*)$/
const TOKEN = /`([^`]+)`|<kbd>(.*?)<\/kbd>|\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|\*([^*\s][^*]*)\*/g

const plain = (s) => String(s).replace(/<kbd>(.*?)<\/kbd>/g, '$1').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/[`*]/g, '')

// The portal's rule (content/doc.js slugify, lib/docs.py slug), on the heading's text without its markup.
export const slug = (s) => plain(s).toLowerCase().trim().replace(/[^\p{L}\p{N}\s_-]/gu, '').replace(/\s+/g, '-')

export function inline(text) {
  const out = []
  let at = 0
  const push = (t) => { if (t) out.push({ t: 'text', text: t }) }
  for (const m of String(text).matchAll(TOKEN)) {
    push(text.slice(at, m.index))
    if (m[1] !== undefined) out.push({ t: 'code', text: m[1] })
    else if (m[2] !== undefined) out.push({ t: 'kbd', text: m[2] })
    else if (m[3] !== undefined) out.push({ t: 'a', text: m[3], href: m[4] })
    else if (m[5] !== undefined) out.push({ t: 'b', text: m[5] })
    else out.push({ t: 'i', text: m[6] })
    at = m.index + m[0].length
  }
  push(text.slice(at))
  return out
}

function cells(line) {
  const row = line.trim().replace(/^\|/, '').replace(/\|$/, '')
  const out = []
  let cur = '', code = false
  for (let i = 0; i < row.length; i++) {
    const c = row[i]
    if (c === '\\' && row[i + 1] === '|') { cur += '|'; i++ }
    else if (c === '`') { code = !code; cur += c }
    else if (c === '|' && !code) { out.push(cur.trim()); cur = '' }
    else cur += c
  }
  return [...out, cur.trim()]
}

const isSeparator = (line) => /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(line || '')

export function parse(md, seen = {}) {
  const lines = String(md).replace(/\r\n?/g, '\n').split('\n')
  const blocks = []
  let i = 0
  const starts = (l) => /^(#{1,4})\s/.test(l) || /^```/.test(l) || /^>/.test(l) || ITEM.test(l) || /^\s*\|/.test(l) || /^<!--/.test(l)
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) { i++; continue }
    let m
    if ((m = line.match(/^```\s*([\w-]*)/))) {
      const body = []
      for (i++; i < lines.length && !/^```\s*$/.test(lines[i]); i++) body.push(lines[i])
      blocks.push({ t: 'code', lang: m[1], text: body.join('\n') })
      i++
    } else if ((m = line.match(MARKER))) {
      const last = blocks.at(-1)
      const item = { kind: m[1], target: m[2] }
      if (last?.t === 'actions') last.items.push(item); else blocks.push({ t: 'actions', items: [item] })
      i++
    } else if (/^<!--/.test(line)) {
      while (i < lines.length && !lines[i].includes('-->')) i++
      i++
    } else if ((m = line.match(/^(#{1,4})\s+(.*?)\s*#*\s*$/))) {
      const level = m[1].length
      if (level > 1) {
        let id = slug(m[2]) || 'section'
        if (id in seen) id += '-' + (++seen[id]); else seen[id] = 0
        blocks.push({ t: 'h', level, text: m[2], id })
      }
      i++
    } else if (/^>/.test(line)) {
      const inner = []
      for (; i < lines.length && /^>/.test(lines[i]); i++) inner.push(lines[i].replace(/^>\s?/, ''))
      const kind = inner[0]?.match(CALLOUT)?.[1].toLowerCase() || null
      blocks.push({ t: 'quote', kind, blocks: parse((kind ? inner.slice(1) : inner).join('\n'), seen) })
    } else if (/^\s*\|/.test(line) && isSeparator(lines[i + 1])) {
      const head = cells(line)
      const rows = []
      for (i += 2; i < lines.length && /^\s*\|/.test(lines[i]); i++) rows.push(cells(lines[i]))
      blocks.push({ t: 'table', head, rows })
    } else if ((m = line.match(ITEM)) && !m[1]) {
      const t = /^\d/.test(m[2]) ? 'ol' : 'ul'
      const items = []
      while (i < lines.length) {
        const l = lines[i]
        const it = l.match(ITEM)
        if (it && !it[1] && (/^\d/.test(it[2]) ? 'ol' : 'ul') === t) items.push({ text: it[3] })
        else if (it && it[1] && items.length) (items.at(-1).items ||= []).push({ text: it[3] })
        else if (l.trim() && /^\s+/.test(l) && items.length) {
          const host = items.at(-1).items?.at(-1) || items.at(-1)
          host.text += ' ' + l.trim()
        } else break
        i++
      }
      blocks.push({ t, items })
    } else {
      const text = []
      for (; i < lines.length && lines[i].trim() && !starts(lines[i]); i++) text.push(lines[i].trim())
      if (!text.length) { blocks.push({ t: 'p', text: line.trim() }); i++ } else blocks.push({ t: 'p', text: text.join(' ') })
    }
  }
  return blocks
}

export function chapters(blocks) {
  const out = []
  for (const b of blocks) {
    if (b.t !== 'h') continue
    if (b.level === 2) out.push({ id: b.id, text: b.text, sections: [] })
    else if (b.level === 3 && out.length) out.at(-1).sections.push({ id: b.id, text: b.text })
  }
  return out
}

export function linkTarget(href, names) {
  const h = String(href || '')
  if (h.startsWith('#')) return { kind: 'anchor', anchor: h.slice(1) }
  if (/^https?:\/\//i.test(h)) return { kind: 'external', href: h }
  const m = h.match(/^(?:\.\/)?([\w-]+)\.md(?:#(.*))?$/)
  return m && names.includes(m[1]) ? { kind: 'guide', name: m[1], anchor: m[2] || '' } : null
}

export const guideHref = (name, anchor) => `#/guide/${name}${anchor ? '/' + encodeURIComponent(anchor) : ''}`

export function guideAt(hash) {
  const [, name = '', anchor = ''] = String(hash || '').match(/^#\/guide(?:\/([\w-]+))?(?:\/(.+))?$/) || []
  try { return { name, anchor: decodeURIComponent(anchor) } } catch { return { name, anchor } }
}

const norm = (s) => String(s || '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()

function textOf(b) {
  if (b.t === 'p' || b.t === 'code') return b.text
  if (b.t === 'ul' || b.t === 'ol') return b.items.map((it) => [it.text, ...(it.items || []).map((x) => x.text)].join(' ')).join(' ')
  if (b.t === 'table') return [b.head, ...b.rows].flat().join(' ')
  if (b.t === 'quote') return b.blocks.map(textOf).join(' ')
  return ''
}

function snippet(text, word) {
  const s = plain(text).replace(/\s+/g, ' ').trim()
  const at = Math.max(0, norm(s).indexOf(word) - 40)
  return (at ? '…' : '') + s.slice(at, at + 160) + (s.length > at + 160 ? '…' : '')
}

// From two characters: the places (a heading and what follows it) whose heading or text holds every word.
export function searchGuides(guides, q) {
  const words = norm(q).split(/\s+/).filter(Boolean)
  if (norm(q).trim().length < 2) return []
  const out = []
  for (const g of guides) {
    let chapter = '', id = '', title = g.title
    const found = new Set()
    for (const b of g.blocks) {
      if (out.length >= 20) return out
      if (b.t === 'h') {
        if (b.level === 2) chapter = b.text
        id = b.id
        title = b.text
      }
      const text = b.t === 'h' ? '' : textOf(b)
      const hay = norm(plain(`${title} ${text}`))
      if (found.has(id) || !words.every((w) => hay.includes(w))) continue
      if (b.t === 'h' && !words.every((w) => norm(plain(title)).includes(w))) continue
      found.add(id)
      out.push({ name: g.name, guideTitle: g.title, chapter: plain(chapter), id, title: plain(title),
        snippet: text ? snippet(text, words[0]) : '' })
    }
  }
  return out
}

// The palette's Guide group: every chapter of every guide, opened in the Guide.
export const guideEntries = (guides) => guides.flatMap((g) => chapters(g.blocks)
  .map((c) => ({ id: `guide:${g.name}/${c.id}`, label: plain(c.text), sub: g.title, href: guideHref(g.name, c.id) })))
