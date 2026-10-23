import { useEffect, useRef, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import { t } from './i18n.js'

const link = (path) => (window.hrefFor ? window.hrefFor(path) : `#/docs/${path}`)

// The block the data page holds, drawn by the docs renderer (Mermaid included), so it looks like the page.
function Model({ markdown, path }) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el || !window.render) return
    el.replaceChildren(window.render(markdown, path))
    window.drawMermaid?.(el)
  }, [markdown, path])
  return <div ref={ref} className="doc" />
}

// Each repo's tables and collections, read from the code without AI (lib/schemas.py).
export default function Data({ arg }) {
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { getJSON('schemas').then(setD, (e) => setError(e.message)) }, [])
  async function write() {
    setBusy(true)
    try { await postJSON('schemas', {}); setD(await getJSON('schemas')); window.loadTree?.() } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  if (!d) return <section className="view"><h1>{t('dataTitle')}</h1><p className={error ? 'error' : 'muted'}>{error || t('loading')}</p></section>
  const withData = d.repos.filter((r) => r.entities)
  const repo = withData.find((r) => r.repo === arg) || withData[0]
  return (
    <section className="view data">
      <h1>{t('dataTitle')}</h1>
      <p className="lede">{t('dataLead')}</p>
      {error ? <p className="error" role="alert">{error}</p> : null}
      {!withData.length ? <p className="muted">{t('dataNone')}</p> : (<>
        <div className="seg data-repos" role="tablist">
          {withData.map((r) => (
            <a key={r.repo} role="tab" aria-selected={r === repo} className={r === repo ? 'on' : ''} href={`#/data/${encodeURIComponent(r.repo)}`}>
              {r.repo} <span className="muted small">{r.entities}</span></a>
          ))}
        </div>
        <div className="data-meta">
          {repo.stores.map((s) => <span key={s.kind} className="pill">{t(`dataKind.${s.kind}`)}{s.engines.length ? ` · ${s.engines.join(', ')}` : ''}</span>)}
          {repo.tools.length ? <span className="muted small">{t('dataFrom')} {repo.tools.join(', ')}</span> : null}
          <span className="data-actions">
            {repo.page ? <a className="button ghost small" href={link(repo.page)}>📄 {t('dataPage')}</a>
              : <button type="button" className="small" disabled={busy} onClick={write}>{t('dataWrite')}</button>}
          </span>
        </div>
        <Model markdown={repo.markdown} path={repo.page || `data/${repo.repo}.md`} />
      </>)}
      <p className="muted small">{t('dataCli')}</p>
    </section>
  )
}
