import { useEffect, useId, useRef, useState } from 'react'
import { getJSON } from '../api.js'
import { core } from '../core.js'
import { chipGroups, pickHit } from '../stories.js'

// Toca: a search box over GET /api/stories/files (the code map's files and groups, and the doc pages) and the picked
// files as chips, one row per group. A group hit adds its files, never the group; a page hit adds the page.
const t = core.t
const SEARCH_MS = 150
const pathOf = (touch) => touch.slice(touch.indexOf(':') + 1)

// `onChange(touches, groups)`: the new list and the group of each file a hit named.
export default function TouchPicker({ touches, groups, onChange, label, error, describedBy }) {
  const [q, setQ] = useState('')
  const [hits, setHits] = useState(null)
  const input = useRef(null)
  const id = useId()
  useEffect(() => {
    const query = q.trim()
    if (!query) { setHits(null); return undefined }
    const ctrl = new AbortController()
    const h = setTimeout(() => {
      getJSON(`stories/files?q=${encodeURIComponent(query)}&limit=20`, { signal: ctrl.signal }).then(setHits, (e) => {
        if (e.name !== 'AbortError') setHits([])
      })
    }, SEARCH_MS)
    return () => { clearTimeout(h); ctrl.abort() }
  }, [q])

  function pick(hit) {
    const named = hit.kind === 'group' ? hit.files || [] : [hit.touch]
    onChange(pickHit(touches, hit), Object.fromEntries(named.map((f) => [f, hit.group])))
    setQ(''); setHits(null); input.current?.focus()
  }
  const remove = (touch) => onChange(touches.filter((x) => x !== touch), {})
  const rows = chipGroups(touches, groups)
  return (
    <div className="st-touches">
      <label htmlFor={`${id}-q`}>{label}</label>
      <input ref={input} id={`${id}-q`} type="search" value={q} onChange={(e) => setQ(e.target.value)}
             placeholder={t('stories.touches.search')} aria-describedby={describedBy}
             onKeyDown={(e) => { if (e.key === 'Escape' && q) { e.stopPropagation(); setQ('') } }} />
      {hits ? (hits.length ? (
        <ul className="st-hits" aria-label={t('stories.touches.search')}>
          {hits.map((h) => (
            <li key={`${h.kind}:${h.touch}`}>
              <button type="button" className="st-hit" onClick={() => pick(h)}>
                <code>{h.kind === 'page' && h.title ? h.title : h.touch}</code>
                <span className="muted small">{h.kind === 'group' ? t('stories.kind.group', { n: (h.files || []).length })
                  : t(`stories.kind.${h.kind}`)}{h.group && h.kind !== 'group' ? ` · ${h.group}` : ''}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : <p className="muted small" role="status">{t('stories.touches.none', { q: q.trim() })}</p>) : null}
      {rows.length ? (
        <div className="st-chips">
          {rows.map((r) => (
            <div key={r.group} className="st-chiprow">
              <span className="st-group">{r.group}</span>
              {r.touches.map((touch) => (
                <span key={touch} className="st-chip" title={touch}>
                  <code>{pathOf(touch)}</code>
                  <button type="button" className="icon" aria-label={t('stories.touches.remove', { touch })} onClick={() => remove(touch)}>✕</button>
                </span>
              ))}
            </div>
          ))}
        </div>
      ) : <p className="muted small">{t('stories.touches.empty')}</p>}
      {error ? <p className="error" role="alert">{error}</p> : null}
    </div>
  )
}
