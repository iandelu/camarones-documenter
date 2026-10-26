import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Chip, Field, Skeleton } from '@camaron/ui'
import { STATUS_LABELS } from '@camaron/ui/kanban.js'
import { allowedParents, parentOf } from '../board.js'
import { t } from '../i18n.js'

// The Board's side panels: a picked card (a story also lists its tasks and adds one) and the add form. One of them
// sits beside the columns at a time.
export const known = (key, fallback) => { const v = t(key); return v === key ? fallback : v }
export const label = (l, status) => (STATUS_LABELS[l] || STATUS_LABELS.en)[status] || status
const TYPES = ['story', 'task', 'bug', 'spike', 'epic']
const PRIORITIES = ['P0', 'P1', 'P2', 'P3']

// Like the portal's useDrawer: the panel takes the focus when it opens (its `data-first` field, else itself), Escape
// closes it, and the focus goes back to what opened it (a card, the Add button) if that is still on the page. When the
// same panel moves on to another card the focus follows it, unless the person is working inside the panel.
function useDrawer(onClose, id) {
  const ref = useRef(null)
  const first = useRef(true)
  useEffect(() => {
    const opener = document.activeElement
    const el = ref.current
    ;(el?.querySelector('[data-first]:not(:disabled)') || el)?.focus()
    return () => { if (opener && opener !== document.body && opener.isConnected) opener.focus() }
  }, [])
  useEffect(() => {
    if (first.current) { first.current = false; return }
    const active = document.activeElement
    if (!active || active === document.body) ref.current?.focus()
  }, [id])
  return { ref, tabIndex: -1, onKeyDown: (e) => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } } }
}

const Checks = ({ id, list }) => (
  <ul className="dk-bd-checks">{list.map((c) => (
    <li key={c.n}><span aria-hidden="true">{c.done ? '☑' : '☐'}</span> {id ? <code>{id}/AC-{c.n}</code> : null} {c.text}
      <span className="sr-only"> ({c.done ? t('yes') : t('no')})</span></li>))}</ul>
)

// The picked card. `item` is what GET kanban/item returned (null while it loads, with `error` when it could not);
// `children` are the board's rows under it. Only a story lists its tasks and adds one.
export function StoryPanel({ item = null, id, error = '', children = [], lang, writable = true, onAddTask, onOpen, onClose }) {
  const drawer = useDrawer(onClose || (() => {}), id ?? item?.id)
  const name = item?.id ?? id
  const parent = item && parentOf(item)
  return (
    <Card as="aside" className="dk-bd-panel" aria-label={name} {...drawer}>
      <div className="row"><h2 className="dk-bd-panel-id">{name}</h2><span className="dk-grow"></span>
        <button type="button" className="dk-icon" aria-label={t('close')} onClick={onClose}>×</button></div>
      {error ? <Aviso tone="error" title={t('bd.itemFailed')} detail={error} /> : !item ? <Skeleton lines={4} /> : (
        <>
          <p className="dk-bd-panel-title">{item.title}</p>
          <div className="row">
            <Chip>{label(lang, item.status)}</Chip>
            {item.type ? <Chip state={item.type === 'bug' ? 'bad' : undefined}>{known(`bd.type.${item.type}`, item.type)}</Chip> : null}
            {item.priority ? <Chip>{item.priority}</Chip> : null}
          </div>
          {parent ? <p className="muted small">↳ {parent}</p> : null}
          <h3 className="eyebrow">{t('bd.description')}</h3>
          {item.description ? <p className="dk-bd-desc">{item.description}</p> : <p className="muted small">{t('bd.noDescription')}</p>}
          <h3 className="eyebrow">{t('bd.criteria')}</h3>
          {item.criteria?.length ? <Checks id={item.id} list={item.criteria} /> : <p className="muted small">{t('bd.nothing')}</p>}
          {item.dod?.length ? <><h3 className="eyebrow">{t('bd.dod')}</h3><Checks list={item.dod} /></> : null}
          {item.type === 'story' ? (
            <div className="dk-bd-kids">
              <h3 className="eyebrow">{t('bd.tasks')} <span className="muted">{children.length}</span></h3>
              {children.length ? (
                <ul>{children.map((c) => (
                  <li key={c.id}><button type="button" className="dk-bd-kid" onClick={() => onOpen(c.id)}>
                    <b className="dk-bd-id">{c.id}</b> <span>{c.title}</span> <Chip>{label(lang, c.status)}</Chip></button></li>))}</ul>
              ) : <p className="muted small">{t('bd.noTasks')}</p>}
              <Button variant="primary" size="sm" disabled={!writable} onClick={() => onAddTask(item.id)}>{t('bd.addTask')}</Button>
            </div>
          ) : null}
        </>
      )}
    </Card>
  )
}

// A new item: a type, a title, optionally a parent the type may go under and a priority. `prefill` fills the first
// render ({type, parent, title}); a refusal (`error`) stays above the buttons and nothing typed is lost.
export function AddForm({ cards, prefill = {}, busy = false, error = '', onSubmit, onClose }) {
  const drawer = useDrawer(onClose)
  const [f, setF] = useState({ type: prefill.type || 'story', title: prefill.title || '', parent: prefill.parent || '', priority: '' })
  const [need, setNeed] = useState(false)
  const parents = allowedParents(f.type, cards)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const setType = (e) => {                             // a parent the new type cannot go under is dropped
    const type = e.target.value
    setF({ ...f, type, parent: allowedParents(type, cards).some((c) => c.id === f.parent) ? f.parent : '' })
  }
  function submit(e) {
    e.preventDefault()
    if (!f.title.trim()) return setNeed(true)
    setNeed(false)
    onSubmit({ type: f.type, title: f.title.trim(), ...(f.parent ? { parent: f.parent } : {}), ...(f.priority ? { priority: f.priority } : {}) })
  }
  return (
    <Card as="aside" className="dk-bd-panel" aria-labelledby="bd-add-h" {...drawer}>
      <div className="row"><h2 id="bd-add-h" className="dk-bd-panel-id">{t('bd.addTitle')}</h2><span className="dk-grow"></span>
        <button type="button" className="dk-icon" aria-label={t('close')} onClick={onClose}>×</button></div>
      <form className="dk-bd-form" onSubmit={submit}>
        <fieldset disabled={busy}>
          <div className="cu-field"><label className="cu-field-label" htmlFor="bd-f-type">{t('bd.fType')}</label>
            <select id="bd-f-type" className="cu-input" value={f.type} onChange={setType}>
              {TYPES.map((ty) => <option key={ty} value={ty}>{known(`bd.type.${ty}`, ty)}</option>)}</select></div>
          <Field id="bd-f-title" label={t('bd.fTitle')} value={f.title} onChange={set('title')} required data-first
            aria-invalid={need || undefined} />
          <div className="cu-field"><label className="cu-field-label" htmlFor="bd-f-parent">{t('bd.fParent')}</label>
            <select id="bd-f-parent" className="cu-input" value={f.parent} onChange={set('parent')} disabled={!parents.length}>
              <option value="">{t('bd.noParent')}</option>
              {parents.map((c) => <option key={c.id} value={c.id}>{c.id} · {c.title}</option>)}</select></div>
          <div className="cu-field"><label className="cu-field-label" htmlFor="bd-f-prio">{t('bd.fPriority')}</label>
            <select id="bd-f-prio" className="cu-input" value={f.priority} onChange={set('priority')}>
              <option value="">{t('bd.noPriority')}</option>
              {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}</select></div>
          {need ? <p className="small" role="alert">{t('bd.needTitle')}</p> : null}
          {error ? <Aviso tone="error" title={t('bd.addFailed')} detail={error} /> : null}
          <div className="row">
            <Button type="submit" variant="primary" disabled={busy}>{t('bd.create')}</Button>
            <Button onClick={onClose}>{t('cancel')}</Button>
          </div>
        </fieldset>
      </form>
    </Card>
  )
}
