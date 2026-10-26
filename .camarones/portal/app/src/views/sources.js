// A doc page's Sources card, pure: where each source opens (the reader's editor on this machine, the forge from the
// deployed portal), how its path reads, and how they group. The entries are api/doc's `sourceInfo`
// (lib/sourcelinks.py): {ref, kind: code|symbol|doc|c4, state: fresh|changed|missing|unchecked, repo, path, lines,
// line, url, file (live portal only), commits…}.

const vscodeLike = (scheme) => (file, line) =>
  `${scheme}://file${file.startsWith('/') ? '' : '/'}${encodeURI(file)}:${line}:1`
const jetbrains = (scheme) => (file, line) => `${scheme}://open?file=${encodeURIComponent(file)}&line=${line}`

export const IDES = [
  { id: 'vscode', label: 'VS Code', href: vscodeLike('vscode') },
  { id: 'cursor', label: 'Cursor', href: vscodeLike('cursor') },
  { id: 'windsurf', label: 'Windsurf', href: vscodeLike('windsurf') },
  { id: 'vscodium', label: 'VSCodium', href: vscodeLike('vscodium') },
  { id: 'idea', label: 'IntelliJ IDEA', href: jetbrains('idea') },
  { id: 'webstorm', label: 'WebStorm', href: jetbrains('webstorm') },
  { id: 'pycharm', label: 'PyCharm', href: jetbrains('pycharm') },
]

// open: an editor id or 'repo'. Without the file here (the deployed portal) the forge is the only way; without a forge
// the editor is. {href, external, where: ide|repo} or null when the source opens nowhere.
export function openTarget(e, open) {
  if (e.kind !== 'code' && e.kind !== 'symbol') return null
  const ide = IDES.find((i) => i.id === open) || IDES[0]
  const inIde = e.file && (open !== 'repo' || !e.url)
  if (inIde) return { href: ide.href(e.file, e.line || 1), external: false, where: 'ide' }
  return e.url ? { href: e.url, external: true, where: 'repo' } : null
}

export function splitPath(path) {
  const i = path.lastIndexOf('/')
  return i < 0 ? { dir: '', name: path } : { dir: path.slice(0, i), name: path.slice(i + 1) }
}

export function lineLabel(e) {
  if (e.kind === 'symbol' && e.symbol) return '#' + e.symbol.split('.').pop()     // the file already names the class
  if (!e.lines) return ''
  return e.lines[0] === e.lines[1] ? `L${e.lines[0]}` : `L${e.lines[0]}–${e.lines[1]}`
}

// [{key: repo | 'docs' | 'c4', items}], repos in the order the page first cites them.
export function groupSources(entries) {
  const groups = new Map()
  const key = (e) => (e.kind === 'doc' ? 'docs' : e.kind === 'c4' ? 'c4' : e.repo || 'docs')
  for (const e of entries) {
    if (!groups.has(key(e))) groups.set(key(e), [])
    groups.get(key(e)).push(e)
  }
  const rank = (k) => (k === 'c4' ? 2 : k === 'docs' ? 1 : 0)
  return [...groups].map(([k, items]) => ({ key: k, items })).sort((a, b) => rank(a.key) - rank(b.key))
}

// The page's own state (fresh | suspect | stale | unverified) in the sources' words, so both share their icons.
export const pageFresh = (fresh) => ({ fresh: 'fresh', suspect: 'changed', stale: 'missing' })[fresh] || 'unchecked'
