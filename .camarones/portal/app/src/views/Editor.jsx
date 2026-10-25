import { useEffect, useRef, useState } from 'react'
import { Aviso, Button } from '@camaron/ui'
import { postJSON } from '../api.js'
import { newPagePath } from './docpage.js'

const L = () => window.CamaronLegacy

// Edit a page in its Markdown with a live preview; saving can commit it (cam-docs is a git repo).
export default function Editor({ d, onDone }) {
  const legacy = L()
  const t = legacy.t
  const lang = legacy.lang()
  const [src, setSrc] = useState(d.raw || `---\ntitle: ${d.title}\n---\n\n# ${d.title}\n`)
  const [msg, setMsg] = useState('')
  const [commit, setCommit] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const preview = useRef(null)

  useEffect(() => {                                     // the preview follows the text after a short pause
    const h = setTimeout(() => {
      const el = legacy.renderMd(src, d.path)
      preview.current.replaceChildren(el)
      legacy.drawMermaid(el)
    }, 250)
    return () => clearTimeout(h)
  }, [src])

  const save = async () => {
    setBusy(true)
    setError('')
    try {
      await postJSON('doc', { path: d.path, lang, raw: src })
      if (commit) {
        const c = await postJSON('commit', { message: msg || `edit ${d.path}` })
        legacy.toast(c.committed ? `${t('savedCommitted')}: ${c.head}` : t('nothingToCommit'))
      } else legacy.toast(t('saved'))
      await legacy.reload()
      const href = legacy.hrefFor(d.path)
      if (location.hash === href) window.CamaronShell.go(); else location.hash = href
    } catch (e) { setError(e.message); setBusy(false) }
  }
  return (
    <div className="page wide editing">
      <h1>{t('editing')}: {d.title}</h1>
      <div className="meta"><code>{d.file}</code>{lang && <span className="small muted"> · {t('translation')} {lang}</span>}</div>
      {d.trust === 'confirmed' && <Aviso tone="warn" title={t('confirmedWarn')} />}
      {error && <Aviso tone="error" title={t('error')} detail={error} />}
      <div className="editor">
        <textarea value={src} onChange={(e) => setSrc(e.target.value)} spellCheck="true" aria-label={t('editing')} />
        <div className="preview" ref={preview}></div>
      </div>
      <div className="row">
        <input className="cu-input" value={msg} onChange={(e) => setMsg(e.target.value)} placeholder={t('commitMsg')}
          aria-label={t('commitMsg')} style={{ flex: 1, minWidth: '14rem' }} />
        <label><input type="checkbox" checked={commit} onChange={(e) => setCommit(e.target.checked)} /> {t('commitBox')}</label>
        <Button variant="primary" disabled={busy} onClick={save}>{t('save')}</Button>
        <Button variant="ghost" onClick={onDone}>{t('cancel')}</Button>
      </div>
    </div>
  )
}

// #/new: a page's title and where it goes; once created it opens in the editor.
export function NewPage() {
  const legacy = L()
  const t = legacy.t
  const [title, setTitle] = useState('')
  const [path, setPath] = useState('')
  const [created, setCreated] = useState(null)
  const [error, setError] = useState('')
  if (created) return <Editor d={created} onDone={() => { location.hash = legacy.hrefFor(created.path) }} />
  const create = async () => {
    try {
      const d = await postJSON('new', { path, title })
      await legacy.reload()
      history.replaceState(null, '', legacy.hrefFor(d.path))
      setCreated(d)
    } catch (e) { setError(e.message) }
  }
  return (
    <div className="page">
      <h1>{t('newPage').replace('+ ', '')}</h1>
      {error && <Aviso tone="error" title={t('error')} detail={error} />}
      <div className="box doc-panel">
        <input className="cu-input" value={title} placeholder={t('newTitle')} aria-label={t('newTitle')}
          onChange={(e) => { setTitle(e.target.value); setPath(newPagePath(e.target.value)) }} />
        <input className="cu-input" value={path} placeholder={t('newPath')} aria-label={t('newPath')} onChange={(e) => setPath(e.target.value)} />
        <div className="row"><Button variant="primary" disabled={!title.trim() || !path.trim()} onClick={create}>{t('create')}</Button></div>
      </div>
    </div>
  )
}
