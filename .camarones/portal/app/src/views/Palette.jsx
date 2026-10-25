import { useEffect, useRef, useState } from 'react'
import { uiText as ui } from '@camaron/ui'
import { docsGet } from '../docsApi.js'
import { paletteEntries } from '../zones.js'
import { marked, paletteGroups } from './search.js'
import { readerTrees } from './DocsTree.jsx'
import { core } from '../core.js'


export function Marked({ text, q }) {
  return marked(text || '', q).map((p, i) => (p.hit ? <mark key={i}>{p.text}</mark> : <span key={i}>{p.text}</span>))
}

// ⌘K: ask (on the server), go to a zone or view, open a page by its title, then pages whose text matches.
// The input keeps the focus; ↑↓ move the active option (aria-activedescendant), Enter opens it, Esc closes.
export default function Palette({ open, onClose }) {
  const dialog = useRef(null)
  const [q, setQ] = useState('')
  const [sel, setSel] = useState(0)
  const [content, setContent] = useState(null)
  const t = core.t
  const mode = core.mode()

  useEffect(() => {
    const d = dialog.current
    if (open && !d.open) { setQ(''); setSel(0); setContent(null); d.showModal() }
    if (!open && d.open) d.close()
  }, [open])

  useEffect(() => {                                        // full text after a pause, from 2 letters; newest wins
    setContent(null)
    const s = q.trim()
    if (s.length < 2) return
    let live = true
    const timer = setTimeout(() => {
      docsGet('search', mode === 'static' ? { q: s, lang: core.lang() } : { q: s })
        .then((hits) => { if (live) setContent(hits) }, () => {})
    }, 180)
    return () => { live = false; clearTimeout(timer) }
  }, [q])

  if (!open) return <dialog ref={dialog} className="palette" onClose={onClose} />
  const index = core.tree()
  const byPath = Object.fromEntries((index.docs || []).map((d) => [d.path, d]))
  const { order } = readerTrees()
  const groups = paletteGroups({ q, mode, index, order, byPath, content, t, hrefFor: core.hrefFor,
    places: paletteEntries(mode, index) })
  const items = groups.flatMap((g) => g.items)
  const active = Math.min(sel, Math.max(items.length - 1, 0))
  const go = (href) => { location.hash = href; onClose() }
  const onKey = (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (items.length) setSel((active + (e.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (items[active]) go(items[active].href)
      else if (q.trim()) go(`#/search/${encodeURIComponent(q.trim())}`)
    }
  }
  let n = 0
  return (
    <dialog ref={dialog} className="palette" onClose={onClose} onClick={(e) => { if (e.target === dialog.current) onClose() }}>
      <div className="pal">
        <input value={q} autoFocus type="search" autoComplete="off" spellCheck="false" placeholder={t('searchPh')}
          role="combobox" aria-expanded="true" aria-controls="pal-list" aria-label={t('search')}
          aria-activedescendant={items.length ? `pal-opt-${active}` : undefined}
          onChange={(e) => { setQ(e.target.value); setSel(0) }} onKeyDown={onKey} />
        <div id="pal-list" className="pal-list" role="listbox" aria-label={t('search')}>
          {groups.filter((g) => g.items.length).map((g) => (
            <div key={g.id} role="group" aria-label={g.label}>
              <div className="pal-group" aria-hidden="true">{g.label}</div>
              {g.items.map((it) => {
                const i = n++
                return (
                  <a key={g.id + it.href} id={`pal-opt-${i}`} role="option" aria-selected={i === active}
                    className={'pal-item' + (i === active ? ' on' : '')} href={it.href}
                    onClick={(e) => { e.preventDefault(); go(it.href) }} onMouseMove={() => setSel(i)}>
                    {g.id === 'ask' ? <span className="pal-tag">{t('homeAsk')}</span> : <span aria-hidden="true">→</span>}
                    <span><b><Marked text={it.label} q={q} /></b>
                      {(it.sub || it.where) && <span className="muted small"> <Marked text={it.sub || it.where} q={q} /></span>}
                      {it.space && it.space !== 'docs' && <span className="pal-tag">{t(it.space === 'wiki' ? 'wikis' : 'notes')}</span>}</span>
                  </a>
                )
              })}
            </div>
          ))}
          {!items.length && q.trim() && (content || q.trim().length < 2
            ? <p className="muted pal-empty">{t('noMatch')}</p>
            : <p className="muted pal-empty" aria-busy="true">{ui('loading')}</p>)}
        </div>
        <div className="pal-foot muted small">{t('searchHint')}</div>
      </div>
    </dialog>
  )
}
