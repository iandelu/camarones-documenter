import { inPanel, sectionFor } from './catalog.js'

// The ⌘K palette and the `g` shortcuts, pure: which letter goes where, what the palette lists, how a query picks.

export const GO = { s: 'summary', p: 'plan', i: 'interviews', t: 'team', q: 'quality', d: 'docs', m: 'machine', k: 'kitdev' }
export const keyFor = (section) => Object.keys(GO).find((k) => GO[k] === section)
const CHORD_MS = 1500

// `g` and then a letter within CHORD_MS: the section the letter names, if this window has it. pending is when the g
// was pressed (0: none).
export function chord(pending, key, at, available) {
  if (pending && at - pending <= CHORD_MS && GO[key] && available.includes(GO[key])) return { pending: 0, go: GO[key] }
  return { pending: key === 'g' ? at : 0, go: null }
}

// Keys typed into a field, or inside a dialog, are text: not shortcuts.
export const typing = (el) => !!el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || !!el.isContentEditable || !!el.closest?.('dialog'))

// The palette's groups: this window's sections with their shortcut, the other projects of this machine (opened in
// this window), the actions that leave the app for the portal, and the commands, each taken to where it runs.
export function entries({ sections, projects = [], commands = [], t, lang = 'es' }) {
  return [
    { id: 'sections', label: t('pal.sections'),
      items: sections.map((s) => ({ id: `go:${s}`, label: t('nav.' + s), keys: ['g', keyFor(s)], href: `#/${s}` })) },
    { id: 'projects', label: t('pal.projects'),
      items: projects.filter((p) => !p.current && p.exists).map((p) => ({ id: `project:${p.path}`, label: p.name, sub: t('pal.switch'), project: p })) },
    { id: 'actions', label: t('pal.actions'), items: [
      { id: 'read', label: t('docs.read'), href: '../#/' },
      { id: 'review', label: t('docs.review'), href: '../#/review' },
      { id: 'search', label: t('docs.search'), href: '../#/search' },
      { id: 'add', label: t('rail.add'), action: 'add' }] },
    { id: 'commands', label: t('pal.commands'), items: commands.flatMap((c) => {
      const s = sectionFor(c, sections)
      return s ? [{ id: `cmd:${c.name}`, label: c[lang] || c.en, sub: `camaron ${c.name}`, href: inPanel(c) ? `#/${s}` : `#/${s}/${c.name}` }] : []
    }) },
  ]
}

const norm = (s) => String(s || '').normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()

// Every word of the query in the label or its hint, accents and case aside; labels that start with the first word go
// first, then the ones with a word that does. With no query, all but the commands (they show once you type).
export function pick(groups, q) {
  const words = norm(q).split(/\s+/).filter(Boolean)
  if (!words.length) return groups.filter((g) => g.id !== 'commands' && g.items.length)
  const rank = (it) => {
    const l = norm(it.label)
    return l.startsWith(words[0]) ? 0 : l.split(/[\s/-]+/).some((w) => w.startsWith(words[0])) ? 1 : 2
  }
  return groups.map((g) => ({ ...g, items: g.items
    .filter((it) => { const text = norm(`${it.label} ${it.sub || ''}`); return words.every((w) => text.includes(w)) })
    .map((it, i) => [rank(it), i, it]).sort((a, b) => a[0] - b[0] || a[1] - b[1]).map((x) => x[2]) }))
    .filter((g) => g.items.length)
}
