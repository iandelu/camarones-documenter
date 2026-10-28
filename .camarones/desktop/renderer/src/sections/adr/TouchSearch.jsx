import { useEffect, useState } from 'react'
import { addHit } from '../../adr.js'
import { t } from '../../i18n.js'

// Toca: the search box of Historias (GET stories/files: the code map's files and groups, and the doc pages) and what
// the ADR touches as chips. A group adds its files, a file or a page itself (adr.js `addHit`). TouchSearchView draws
// it from its state alone; TouchSearch asks the server as the person types.
const WAIT_MS = 150

function split(touch) {
  const s = String(touch)
  const at = s.indexOf(':')
  return at < 0 ? ['', s] : [s.slice(0, at), s.slice(at + 1)]
}

// `onRemove` makes it removable; without it the chip only shows (the evidence step).
export function TouchChip({ touch, onRemove }) {
  const [repo, path] = split(touch)
  return (
    <li className="dk-adr-tchip" title={touch}>
      <code>{repo ? <span className="muted">{`${repo}:`}</span> : null}{path}</code>
      {onRemove ? <button type="button" className="dk-adr-x" aria-label={t('adr.touch.remove', { touch })} onClick={() => onRemove(touch)}>✕</button> : null}
    </li>
  )
}

const kindOf = (h) => (h.kind === 'group' ? t('adr.touch.group', { n: (h.files || []).length })
  : h.kind === 'page' ? t('adr.touch.page') : [t('adr.touch.file'), h.group].filter(Boolean).join(' · '))

// `hits`: null before a search, else what it found; `error`: why it could not search.
export function TouchSearchView({ id, label, help, q, hits, error = '', touches, onQ, onPick, onRemove }) {
  const query = String(q ?? '').trim()
  return (
    <div className="dk-adr-touch">
      <label className="cu-field-label" htmlFor={`${id}-q`}>{label}</label>
      {help ? <span id={`${id}-help`} className="muted small">{help}</span> : null}
      <div className="dk-adr-find">
        <span aria-hidden="true">⌕</span>
        <input id={`${id}-q`} type="search" className="cu-input" value={q ?? ''} placeholder={t('adr.touch.search')} autoComplete="off"
          aria-describedby={help ? `${id}-help` : undefined} onChange={(e) => onQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Escape' && q) { e.stopPropagation(); onQ('') } }} />
      </div>
      {error ? <p className="small dk-adr-err" role="alert">{`${t('adr.touch.failed')}: `}<code>{error}</code></p>
        : hits?.length ? (
          <ul className="dk-adr-hits" aria-label={t('adr.touch.search')}>
            {hits.map((h) => (
              <li key={`${h.kind}:${h.touch}`}>
                <button type="button" className="dk-adr-hit" onClick={() => onPick(h)}>
                  <code>{h.kind === 'page' && h.title ? h.title : h.touch}</code>
                  <span className="muted small">{kindOf(h)}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : hits && query ? <p className="muted small" role="status">{t('adr.touch.none', { q: query })}</p> : null}
      {touches?.length ? (
        <ul className="dk-adr-touches" aria-label={t('adr.touch.picked')}>
          {touches.map((x) => <TouchChip key={x} touch={x} onRemove={onRemove} />)}
        </ul>
      ) : <p className="muted small">{t('adr.touch.empty')}</p>}
    </div>
  )
}

// `search(q)` resolves to the hits (keep it stable: a new function searches again); `onChange(touches)` the new list.
export function TouchSearch({ id, label, help, touches, search, onChange }) {
  const [q, setQ] = useState('')
  const [hits, setHits] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const query = q.trim()
    if (!query || !search) { setHits(null); setError(''); return undefined }
    let live = true
    const timer = setTimeout(() => {
      Promise.resolve(search(query)).then((r) => { if (live) { setHits(Array.isArray(r) ? r : []); setError('') } },
        (e) => { if (live) { setHits(null); setError(e.message) } })
    }, WAIT_MS)
    return () => { live = false; clearTimeout(timer) }
  }, [q, search])
  const pick = (hit) => {
    onChange(addHit(touches, hit))
    setQ(''); setHits(null)
    document.getElementById(`${id}-q`)?.focus()
  }
  return (
    <TouchSearchView id={id} label={label} help={help} q={q} hits={hits} error={error} touches={touches} onQ={setQ} onPick={pick}
      onRemove={(touch) => onChange((touches || []).filter((x) => x !== touch))} />
  )
}
