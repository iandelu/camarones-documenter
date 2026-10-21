import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import { t } from './i18n.js'

const Canvas = lazy(() => import('./BoardCanvas.jsx'))          // Excalidraw is heavy: only when a board opens

// Excalidraw's fonts come with the portal (public/excalidraw/fonts), never from a CDN: the portal works offline.
window.EXCALIDRAW_ASSET_PATH = new URL('excalidraw/', document.baseURI).href

const dark = () => (document.documentElement.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) === 'dark'

function List() {
  const [boards, setBoards] = useState(null)
  const [name, setName] = useState('')
  const [view, setView] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { getJSON('boards').then(setBoards, (e) => setError(e.message)) }, [])
  const views = window.camaronTree?.().views || []
  async function create(e) {
    e.preventDefault()
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    if (!slug) return
    try {
      const scene = view ? await getJSON(`sketch?view=${encodeURIComponent(view)}`)
        : { type: 'excalidraw', version: 2, elements: [], appState: {}, files: {} }
      await postJSON('board', { name: slug, scene })
      location.hash = `#/boards/${slug}`
    } catch (err) { setError(err.message) }
  }
  return (
    <section className="view">
      <h1>{t('boardsTitle')}</h1>
      <p className="lede">{t('boardsLead')}</p>
      <form className="row box" onSubmit={create}>
        <b>{t('newBoard')}</b>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('name')} aria-label={t('name')} />
        <select value={view} onChange={(e) => setView(e.target.value)} aria-label={t('fromView')}>
          <option value="">{t('blank')}</option>
          {views.map((v) => <option key={v.id} value={v.id}>{t('fromView')}: {v.title}</option>)}
        </select>
        <button type="submit">{t('open')}</button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      {boards === null ? <p className="muted">{t('loading')}</p> : boards.length ? (
        <div className="boards-list">
          {boards.map((b) => <a key={b.name} className="card link" href={`#/boards/${b.name}`}><div><b>{b.name}</b></div></a>)}
        </div>
      ) : <p className="muted">{t('noBoards')}</p>}
    </section>
  )
}

function Board({ name }) {
  const [scene, setScene] = useState(null)
  const [status, setStatus] = useState('')
  const api = useRef(null)
  useEffect(() => { getJSON(`board?name=${encodeURIComponent(name)}`).then(setScene, (e) => setStatus(e.message)) }, [name])
  async function save() {
    const a = api.current
    if (!a) return
    const appState = a.getAppState()
    await postJSON('board', { name, scene: { type: 'excalidraw', version: 2, elements: a.getSceneElements(),
      appState: { viewBackgroundColor: appState.viewBackgroundColor, gridSize: appState.gridSize }, files: a.getFiles() } })
    setStatus(t('saved'))
    setTimeout(() => setStatus(''), 2500)
  }
  return (
    <section>
      <div className="boards-bar">
        <a href="#/boards">{t('allBoards')}</a>
        <b>{name}</b>
        <button type="button" className="small" onClick={save}>{t('save')}</button>
        <span className="muted small" role="status">{status}</span>
      </div>
      <div className="boards-stage">
        {scene ? (
          <Suspense fallback={<p className="muted pad">{t('loading')}</p>}>
            <Canvas scene={scene} dark={dark()} onApi={(a) => { api.current = a }} />
          </Suspense>
        ) : <p className="muted pad">{status || t('loading')}</p>}
      </div>
    </section>
  )
}

export default function Boards({ arg }) {
  return arg ? <Board name={arg} /> : <List />
}
