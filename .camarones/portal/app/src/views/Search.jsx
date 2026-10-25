import { useEffect, useState } from 'react'
import { Aviso, Button, EmptyState, Skeleton } from '@camaron/ui'
import { docsGet } from '../docsApi.js'
import { Marked } from './Palette.jsx'
import { rankBySpace } from './search.js'

const L = () => window.CamaronLegacy

// #/search/<q>: every page whose text matches, docs first, with the matching lines.
export default function Search({ arg }) {
  const q = arg || ''
  const legacy = L()
  const t = legacy.t
  const mode = legacy.mode()
  const [hits, setHits] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    docsGet('search', mode === 'static' ? { q, lang: legacy.lang() } : { q, track: 1 })
      .then((h) => setHits(rankBySpace(h, Object.fromEntries((legacy.tree().docs || []).map((d) => [d.path, d])))),
        (e) => setError(e.message))
  }, [q])
  const space = (p) => legacy.byPath(p)?.space
  return (
    <div className="page">
      <h1>{t('results')} “{q}”</h1>
      {error && <Aviso tone="error" title={t('error')} detail={error} />}
      {!hits && !error && <Skeleton lines={4} />}
      {hits && !hits.length && (
        <EmptyState title={t('noResults')}
          action={mode === 'static' ? <Button href="#/docs">{t('docs')}</Button>
            : <Button variant="primary" href={`#/ask/${encodeURIComponent(q)}`}>{t('homeAsk')} “{q}”</Button>} />
      )}
      {hits?.map((h) => (
        <div className="hit" key={h.path}>
          <a href={legacy.hrefFor(h.path)}>{h.title}</a>
          {space(h.path) && space(h.path) !== 'docs' && <span className="pal-tag">{t(space(h.path) === 'wiki' ? 'wikis' : 'notes')}</span>}
          <span className="muted small"> {h.path}</span>
          {h.lines.map((l, i) => <div className="snip" key={i}><Marked text={l} q={q} /></div>)}
        </div>
      ))}
    </div>
  )
}
