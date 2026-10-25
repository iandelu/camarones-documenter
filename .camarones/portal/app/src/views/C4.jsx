import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Chip, EmptyState, Skeleton } from '@camaron/ui'
import { postJSON } from '../api.js'
import { docsGet } from '../docsApi.js'
import { c4Box, drawC4, flowViewId, loadViewers, runBuild } from '../content/doc.js'
import { core } from '../core.js'

const runs = () => core.mode() === 'app'
export const VIEW_GROUPS = ['system', 'element', 'dynamic', 'deployment']
export const viewGroup = (v) => (v.id === 'index' ? 'system' : v.kind)
const defaultView = (views) => (views.find((v) => v.id === 'index') || views[0])?.id || ''
const viewId = (arg, views) => (arg || '').split('/').filter(Boolean)[0] || defaultView(views)

// The sidebar on Architecture: the model's views by kind, the full explorer and the code map.
export function ArchSide({ arg }) {
  const t = core.t
  const index = core.tree()
  const views = index.views || []
  const active = viewId(arg, views) || 'explorer'
  const link = (href, label, on, title) => <a key={href} href={href} className={on ? 'on' : ''} title={title}
    aria-current={on ? 'page' : undefined}>{label}</a>
  return (
    <nav className="arch-side" aria-label={t('c4')}>
      <div className="side-title">{t('c4')}</div>
      {VIEW_GROUPS.map((g) => [g, views.filter((v) => viewGroup(v) === g)]).filter(([, vs]) => vs.length).map(([g, vs]) => (
        <div className="group" key={g}><div className="group-title">{t('kind.' + g)}</div>
          {vs.map((v) => link(`#/c4/${v.id}`, v.title, v.id === active, v.id))}</div>
      ))}
      <div className="group"><div className="group-title">{t('explore')}</div>
        {link('#/c4/explorer', t('explorer'), active === 'explorer')}
        {((index.codeMaps || []).length > 0 || (index.codeGraphs || []).length > 0) && link('#/code', t('codeTab'), false)}</div>
    </nav>
  )
}

function useViewers() {
  const [v, setV] = useState(null)
  useEffect(() => { loadViewers().then((x) => setV(x.c4), () => setV({})) }, [])
  return v
}

const C4State = ({ v, t }) => (v.exists
  ? <span className="muted small">{t('builtAt', { when: core.ago(v.at) })}{v.stale && <> · <span className="warn">{t('stale')}</span></>}</span>
  : <span className="muted small">{t(v.model ? 'notBuilt' : 'noC4')}</span>)

// A bar over a visualizer: its state and, in the app, the button that (re)builds it, with the build's log.
function BuildBar({ children, what, label, t }) {
  const log = useRef(null)
  return (
    <div className="vbar">
      {children}
      {runs() && label && <Button size="sm" onClick={(e) => runBuild(what, '', e.currentTarget, log.current, () => location.reload())}>{label}</Button>}
      <pre ref={log} className="joblog inline" hidden></pre>
    </div>
  )
}

// #/c4/<view>: one view of the C4 model, drawn by LikeC4's web component, with its elements to review below.
export default function C4({ arg }) {
  const t = core.t
  const views = core.tree().views || []
  const id = viewId(arg, views)
  if (!id || id === 'explorer') return <Explorer t={t} />
  const view = views.find((v) => v.id === id)
  if (!view) return <div className="page"><EmptyState title={t('notFound')} action={<Button href="#/c4">{t('c4')}</Button>}><code>{id}</code></EmptyState></div>
  return <C4View key={id} view={view} t={t} />
}

function C4View({ view, t }) {
  const v = useViewers()
  const stage = useRef(null)
  const flowDoc = (core.tree().docs || []).find((d) => flowViewId(d.path) === view.id)
  useEffect(() => {
    if (!v || !stage.current) return
    stage.current.replaceChildren(c4Box(view.id))
    drawC4(stage.current, { caption: false, maxH: () => Math.max(320, innerHeight * 0.7) })
  }, [v])
  if (!v) return <div className="page"><Skeleton lines={4} /></div>
  return (
    <div className="arch">
      <div className="arch-head">
        <div>
          <h1>{view.title}</h1>
          <div className="meta"><Chip>{t('kind.' + viewGroup(view))}</Chip><code>{view.id}</code>
            <span className="muted small">architecture/{view.file}</span></div>
        </div>
        <div className="row">
          {flowDoc && <Button size="sm" variant="ghost" href={core.hrefFor(flowDoc.path)}>{t('readFlow')}</Button>}
          {v.exists && <Button size="sm" variant="ghost" href={`architecture/view/${encodeURIComponent(view.id)}/`} target="_blank" rel="noopener">
            {t('openExplorer')} <span aria-hidden="true">↗</span></Button>}
        </div>
      </div>
      <BuildBar what="c4" label={v.model ? t(v.exists ? 'rebuild' : 'build') : ''} t={t}><C4State v={v} t={t} /></BuildBar>
      <div className="c4stage" ref={stage}></div>
      <Elements id={view.id} model={v.model} t={t} />
    </div>
  )
}

// The view's elements: review, edit and confirm what the AI drafted (lib/c4edit.py), its relations in and out.
function Elements({ id, model, t }) {
  const [v, setV] = useState(null)
  const [error, setError] = useState('')
  const log = useRef(null)
  const load = () => docsGet('c4/view', { id }).then(setV, () => setV({ elements: [] }))
  useEffect(() => { load() }, [id])
  if (!v?.elements?.length) return null
  const edit = v.editable && core.mode() !== 'static'
  const drafts = v.elements.filter((e) => e.draft).length
  const change = async (path, body) => {
    setError('')
    try {
      await postJSON(`c4/${path}`, body)
      core.toast(t('c4Saved'))
      await load()
      if (runs() && model) runBuild('c4', '', null, log.current, () => location.reload())
    } catch (e) { setError(e.message) }
  }
  return (
    <section className="c4el-panel">
      <div className="c4el-head"><h2>{t('c4Elements')}</h2>
        <span className="muted small">{t('c4Count', { n: v.elements.length, d: drafts })}</span>
        {edit && drafts > 0 && <Button size="sm" variant="primary" onClick={() => change('confirm', { view: id })}>{t('c4ConfirmAll')}</Button>}</div>
      {edit && <p className="muted small">{t('c4Help')}</p>}
      {error && <Aviso tone="error" title={t('error')} detail={error} />}
      <pre ref={log} className="joblog" hidden></pre>
      <div className="c4el-list">{v.elements.map((e) => <Element key={e.fqn} e={e} v={v} edit={edit} t={t} change={change} />)}</div>
    </section>
  )
}

function Element({ e, v, edit, t, change }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ title: e.title, kind: e.kind, technology: e.technology || '', description: e.description || '' })
  const [rel, setRel] = useState({ to: '', label: '', kind: '' })
  const title = (fqn) => v.all.find((x) => x.fqn === fqn)?.title || fqn
  const set = (k) => (ev) => setForm({ ...form, [k]: ev.target.value })
  const relation = (r, out) => (
    <li key={(out ? 'o' : 'i') + (out ? r.to : r.from) + r.label}>{out ? '→' : '←'} <b>{title(out ? r.to : r.from)}</b>
      {r.label && <span className="muted"> {r.label}</span>}{r.kind && <Chip>{r.kind}</Chip>}
      {edit && out && <Button size="sm" variant="ghost" aria-label={t('c4RemoveRel')} title={t('c4RemoveRel')}
        onClick={() => change('relation', { action: 'remove', from: e.fqn, to: r.to, label: r.label })}>×</Button>}</li>
  )
  return (
    <article className={'c4el' + (e.draft ? ' draft' : '')}>
      <div className="c4el-h"><b>{e.title}</b><Chip>{e.kind}</Chip><code className="small muted">{e.fqn}</code>
        {e.confirmed ? <Chip state="ok">{t('c4ConfirmedBy', { by: e.confirmedBy || '?', at: e.confirmedAt || '' })}</Chip>
          : e.draft ? <Chip state="warn">{t('c4Draft')}</Chip> : null}
        {edit && <span className="c4el-act">
          <Button size="sm" variant="ghost" aria-expanded={open} onClick={() => setOpen(!open)}>{t('edit')}</Button>
          {!(e.confirmed && !e.draft) && <Button size="sm" onClick={() => change('confirm', { fqns: [e.fqn] })}>{t('c4Confirm')}</Button>}
        </span>}
      </div>
      {(e.technology || e.description) && <p className="small">{e.technology && <b>{e.technology}</b>}{e.technology && e.description ? ' · ' : ''}{e.description}</p>}
      {(e.out.length > 0 || e.in.length > 0) && <ul className="c4rels">{e.out.map((r) => relation(r, true))}{e.in.map((r) => relation(r, false))}</ul>}
      {edit && open && (
        <form className="c4el-form" onSubmit={(ev) => { ev.preventDefault(); change('element', { fqn: e.fqn, ...form }) }}>
          <label>{t('c4Title')}<input className="cu-input" value={form.title} onChange={set('title')} required /></label>
          <label>{t('c4Kind')}<select value={form.kind} onChange={set('kind')}>{v.kinds.map((k) => <option key={k}>{k}</option>)}</select></label>
          <label>{t('c4Tech')}<input className="cu-input" value={form.technology} onChange={set('technology')} /></label>
          <label className="wide">{t('c4Desc')}<input className="cu-input" value={form.description} onChange={set('description')} /></label>
          <div className="row"><Button size="sm" variant="primary" type="submit">{t('save')}</Button>
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>{t('cancel')}</Button></div>
        </form>
      )}
      {edit && (
        <form className="c4rel-form row" onSubmit={(ev) => {
          ev.preventDefault()
          if (rel.to) change('relation', { action: 'add', from: e.fqn, to: rel.to, label: rel.label, kind: rel.kind || null })
        }}>
          <select aria-label={t('c4To')} value={rel.to} onChange={(ev) => setRel({ ...rel, to: ev.target.value })}>
            <option value="">{t('c4AddRel')} {t('c4To')}…</option>
            {v.all.filter((x) => x.fqn !== e.fqn).map((x) => <option key={x.fqn} value={x.fqn}>{x.title} ({x.fqn})</option>)}</select>
          <input className="cu-input" value={rel.label} placeholder={t('c4Label')} aria-label={t('c4Label')}
            onChange={(ev) => setRel({ ...rel, label: ev.target.value })} />
          <select aria-label={t('c4Kind')} value={rel.kind} onChange={(ev) => setRel({ ...rel, kind: ev.target.value })}>
            <option value="">—</option>{v.relKinds.map((k) => <option key={k}>{k}</option>)}</select>
          <Button size="sm" variant="ghost" type="submit" disabled={!rel.to}>{t('c4AddRel')}</Button>
        </form>
      )}
    </article>
  )
}

// #/c4/explorer: LikeC4's full explorer; with no model yet, the app drafts one from the code first.
function Explorer({ t }) {
  const v = useViewers()
  if (!v) return <div className="page"><Skeleton lines={3} /></div>
  return (
    <>
      <BuildBar what={v.model ? 'c4' : 'first-look'} label={v.model ? t(v.exists ? 'rebuild' : 'build') : t('firstLook')} t={t}>
        <b>{t('explorer')}</b><C4State v={v} t={t} />
        {v.exists && <a href="architecture/" target="_blank" rel="noopener">{t('openTab')} <span aria-hidden="true">↗</span></a>}
      </BuildBar>
      {v.exists && <iframe className="viewer" src="architecture/" title="C4"></iframe>}
    </>
  )
}
