import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Chip, Keys } from '@camaron/ui'
import { acceptBlock, addAttendees, blockedPart, choiceBody, decided, firstOpen, keyEffect, newPointBody, nextPart, partKind, pickOf,
  pointOf, reviewKey, reviewParts } from '../../adr.js'
import { t } from '../../i18n.js'
import { initials } from '../../nav.js'
import { chord, GO, typing } from '../../palette.js'
import { Fold, Page } from '../../parts.jsx'
import { Prose } from './Prose.jsx'
import { AdrHead, Sections, StatusNote, Stepper, heading, said } from './Read.jsx'

// Revisión (spec §2.5): the ADR part by part (its sections approved, edited or deferred, its decision points decided),
// the attendees, then accept or reject. Presenting (P; Esc leaves) gives a meeting one part per screen in a larger type,
// all of it by keyboard. Review holds what the screen is doing (the part in view, drafts, dialogs, keys, focus);
// ReviewView draws it from props, so a test can draw every state. AdrScreen (Decisions.jsx) sends the writes.

const cls = (...names) => names.filter(Boolean).join(' ')
const SEEN = ['approved', 'edited']
const STATUSES = ['pending', ...SEEN, 'deferred']
const MAX_OPTIONS = 9                                         // the number keys reach nine
const letter = (i) => String.fromCharCode(65 + i)
const blankPoint = () => ({ question: '', options: [{ name: '' }, { name: '' }] })
const attendeesOf = (adr) => (adr?.state?.attendees || []).filter((n) => typeof n === 'string' && n.trim())

export function partLabel(adr, id) {
  const kind = partKind(id)
  if (kind === 'affected') return t('adr.review.part.affected')
  if (kind === 'text') return t(`adr.sec.${id}`)
  const tag = id.slice('point:'.length).toUpperCase()
  const q = pointOf(adr, id)?.question
  return q ? `${tag} · ${q}` : tag
}

function statusWord(part) {
  const st = STATUSES.includes(part.status) ? part.status : 'pending'
  return partKind(part.id) === 'point' && st === 'approved' ? t('adr.review.status.chosen') : t(`adr.review.status.${st}`)
}

const choiceName = (p) => {
  if (p.other) return `${t('adr.review.other')} · ${p.other}`
  const o = (p.options || []).find((x) => x.id === p.chosen)
  return o ? `${o.id} · ${o.name}` : ''
}

export function Review({ adr, busy = false, error = '', notice = '', send }) {
  const [current, setCurrent] = useState(() => (decided(adr) ? reviewParts(adr)[0]?.id : firstOpen(reviewParts(adr))) ?? null)
  const [present, setPresent] = useState(false)
  const [ui, setUi] = useState({ drafts: {}, adding: null, dialog: null, why: '', tried: false, attendee: '', say: '' })
  const root = useRef(null)
  const focusNext = useRef(null)        // a selector inside the review that takes the focus after the next render
  const inside = useRef(false)          // the focus was in the review: if what held it goes, it lands on the part again
  const pending = useRef(0)             // when a `g` was pressed: the letter after it is App.jsx's chord, not the review's
  const parts = reviewParts(adr)
  const here = parts.some((p) => p.id === current) ? current : firstOpen(parts)
  const patch = (p) => setUi((u) => ({ ...u, ...p }))
  const draft = (part, p) => setUi((u) => ({ ...u, drafts: { ...u.drafts, [part]: p && { ...u.drafts[part], ...p } } }))

  useEffect(() => {
    const box = root.current
    const sel = focusNext.current
    focusNext.current = null
    if (!box || (!sel && !(inside.current && document.activeElement === document.body))) return
    ;(box.querySelector(sel || '[data-primary]') || box.querySelector('.dk-rv-pane'))?.focus()
  })

  const go = (id) => { setCurrent(id); patch({ adding: null, say: '' }); focusNext.current = '[data-primary]' }
  const presenting = (on) => { setPresent(on); focusNext.current = '[data-primary]' }
  async function write(name, body, then) {
    if (busy) return
    const next = await send(name, body)
    if (next) then(next)
  }
  const onPart = (action, text) => write('part', { part: here, action, ...(action === 'edit' ? { text } : {}) }, (next) => {
    draft(here, null)
    if (action === 'edit') focusNext.current = '[data-primary]'
    else go(nextPart(reviewParts(next), here, 1))
  })
  const onPoint = (body) => {
    const after = nextPart(parts, here, 1)                        // a removed point's place goes to the part after it
    return write('point', body, (next) => {
      if (body.op === 'add') { const last = next.points?.at(-1); return last ? go(`point:${last.id}`) : patch({ adding: null }) }
      draft(here, null)
      patch({ dialog: null })
      go(body.op === 'remove' ? after : nextPart(reviewParts(next), here, 1))
    })
  }
  const onAttendees = (attendees) => write('attendees', { attendees }, () => patch({ attendee: '' }))
  const onAccept = () => write('accept', {}, () => patch({ dialog: null }))          // no attendees sent: the review's stay
  const onReject = (why) => write('reject', { why }, () => patch({ dialog: null, why: '', tried: false }))

  function onKey(e) {
    const field = typing(e.target)
    let chorded = false
    if (e.metaKey || e.ctrlKey || e.altKey || field) pending.current = 0
    else { const r = chord(pending.current, e.key, e.timeStamp, Object.values(GO)); pending.current = r.pending; chorded = !!r.go }
    if (e.defaultPrevented || document.querySelector('dialog[open]')) return      // a modal's keys are its own (a closing one too)
    if (field) {                                                   // Esc leaves a field of the review, keeping what it holds
      if (e.key === 'Escape' && root.current?.contains(e.target) && !e.target.closest?.('dialog')) {
        e.preventDefault()
        root.current.querySelector('.dk-rv-pane')?.focus()
      }
      return
    }
    const point = pointOf(adr, here)
    const fx = keyEffect(adr, here, reviewKey(e, { typing: false, options: point?.options?.length ?? 0, chord: chorded }), { present })
    if (!fx || (ui.adding && 'go' in fx)) return                 // moving away would drop the point being written
    e.preventDefault()
    if ('go' in fx) { go(fx.go); if (fx.blocked) patch({ say: t(fx.blocked.key, { point: fx.blocked.point }) }) }
    else if ('present' in fx) presenting(fx.present)
    else if (fx.pick) { draft(here, { picked: fx.pick }); focusNext.current = '#rv-rationale' }
    else if (fx.edit === 'text') draft(here, { editing: true })
    else if (fx.edit === 'rationale') root.current?.querySelector('#rv-rationale')?.focus()
    else if (fx.defer === 'part') onPart('defer')
    else if (fx.defer === 'point' && point) onPoint({ op: 'defer', point: point.id })
    else if (fx.accept) patch({ dialog: 'accept' })
  }
  // The whole window's keys while the review is open, not only the ones inside it: after a jump the focus sits on the
  // main landmark, and a meeting should not have to click before pressing →.
  const latest = useRef(onKey)
  latest.current = onKey
  useEffect(() => {
    const on = (e) => latest.current(e)
    addEventListener('keydown', on)
    return () => removeEventListener('keydown', on)
  }, [])

  return (
    <div ref={root} onFocus={() => { inside.current = true }}
      onBlur={(e) => { if (e.relatedTarget && !root.current?.contains(e.relatedTarget)) inside.current = false }}>
      <ReviewView adr={adr} current={here} present={present} ui={ui} busy={busy} error={error} notice={notice} onPart={onPart}
        onPoint={onPoint} onAttendees={onAttendees} onAccept={onAccept} onReject={onReject} onPresent={presenting} onGo={go} onUi={patch} />
    </div>
  )
}

// `ui`: what the screen holds that the ADR does not: drafts by part ({editing, draft, picked, rationale, other}), the
// point being added, the open dialog ('accept' | 'reject' | 'remove'), the reason typed to reject, the attendee typed.
export function ReviewView({ adr, current, present = false, ui = {}, busy = false, error = '', notice = '', onPart, onPoint, onAttendees,
  onAccept, onReject, onPresent, onGo, onUi }) {
  const parts = reviewParts(adr)
  const here = parts.some((p) => p.id === current) ? current : firstOpen(parts)
  const closed = decided(adr)
  const kind = partKind(here)
  const at = parts.findIndex((p) => p.id === here)
  const part = parts[at] || { id: here, status: 'pending' }
  const block = closed ? null : acceptBlock(adr)
  const d = ui.drafts?.[here] || {}
  const pane = { adr, here, part, closed, d, setDraft: (p) => onUi({ drafts: { ...ui.drafts, [here]: { ...d, ...p } } }), onPart, onPoint, onUi,
    where: t('adr.review.where', { n: at + 1, total: parts.length }), label: partLabel(adr, here) }
  const adding = !closed && ui.adding
  const Pane = adding ? AddPoint : kind === 'point' ? PointPane : kind === 'affected' ? AffectedPane : TextPane
  return (
    <div className={cls('dk-rv-screen', present && 'dk-present')}>
      <Page wide title={heading(adr)} actions={
        <Button size="sm" variant={present ? 'secondary' : 'ghost'} aria-keyshortcuts={present ? 'Escape' : 'P'} onClick={() => onPresent(!present)}>
          {t(present ? 'adr.review.leave' : 'adr.review.present')}<Keys keys={[present ? 'Esc' : 'P']} />
        </Button>}>
        <AdrHead adr={adr} />
        <Stepper phase={adr.state?.phase} mode={adr.state?.mode} />
        {closed ? (
          <StatusNote adr={adr}>
            <p className="muted small">{t('adr.review.closed')} <a href="#/decisions/new">{t('adr.new')}</a></p>
          </StatusNote>) : null}
        {notice ? <Aviso tone="info" title={notice} /> : null}
        <div className="dk-rv" aria-busy={busy || undefined}>
          <PartsNav adr={adr} parts={parts} here={here} closed={closed} adding={!!adding} present={present} ui={ui} onGo={onGo} onUi={onUi} />
          <section key={adding ? 'add' : here} className="dk-rv-pane" tabIndex={-1} aria-labelledby="rv-h">
            <Pane {...pane} form={ui.adding} />
          </section>
          {error && !ui.dialog ? <div className="dk-rv-err"><Aviso tone="error" title={t('adr.review.failed')} detail={error} /></div> : null}
          <div className="dk-rv-foot">
            <People adr={adr} closed={closed} typed={ui.attendee} onUi={onUi} onAttendees={onAttendees} />
            {closed ? null : <Decide block={block} parts={parts} onGo={onGo} onUi={onUi} />}
          </div>
          <KeyHints adr={adr} here={here} closed={closed} present={present} />
        </div>
        <div className="dk-rv-whole"><Fold label={t('adr.review.whole')}><Sections sections={adr.sections} /></Fold></div>
        <p className="sr-only" role="status">{busy ? t('adr.review.saving') : ui.say || `${pane.where}: ${pane.label}`}</p>
        {closed ? null : <Dialogs adr={adr} here={here} ui={ui} error={error} onUi={onUi} onAccept={onAccept} onReject={onReject} onPoint={onPoint} />}
      </Page>
    </div>
  )
}

function PartsNav({ adr, parts, here, closed, adding, present, ui, onGo, onUi }) {
  return (
    <nav className="dk-rv-nav" aria-label={t('adr.review.parts')}>
      <ol className="dk-rv-parts">
        {parts.map((p) => {
          const on = p.id === here && !adding
          const st = STATUSES.includes(p.status) ? p.status : 'pending'
          return (
            <li key={p.id}>
              <button type="button" className={cls('dk-rv-part', `is-${st}`, on && 'on')} aria-current={on ? 'step' : undefined}
                title={present ? `${partLabel(adr, p.id)} · ${statusWord(p)}` : undefined} onClick={() => onGo(p.id)}>
                <span className="dk-rv-glyph" aria-hidden="true">{on ? '●' : SEEN.includes(st) ? '✓' : '○'}</span>
                <span className="dk-rv-plabel">{partLabel(adr, p.id)}</span>
                <span className={st === 'pending' ? 'sr-only' : 'dk-rv-pstate'}>{statusWord(p)}</span>
              </button>
            </li>
          )
        })}
      </ol>
      {closed ? null : (
        <button type="button" className={cls('dk-rv-addpt', adding && 'on')} onClick={() => onUi({ adding: ui.adding || blankPoint() })}>
          <span aria-hidden="true">+</span> {t('adr.review.addPoint')}
        </button>)}
    </nav>
  )
}

const eyebrow = (where, part) => (part.status && part.status !== 'pending' ? `${where} · ${statusWord(part)}` : where)

function TextPane({ adr, here, part, closed, d, setDraft, where, label, onPart }) {
  const text = adr.sections?.[here] ?? ''
  const head = (<>
    <p className="dk-rv-eyebrow">{eyebrow(where, part)}</p>
    <h2 id="rv-h" className="dk-rv-h">{label}</h2>
  </>)
  if (!closed && d.editing) {
    const value = d.draft ?? text
    return (<>
      {head}
      <form className="dk-rv-editf" onSubmit={(e) => { e.preventDefault(); onPart('edit', value) }}>
        <label className="sr-only" htmlFor="rv-edit">{t('adr.review.editLabel', { part: label })}</label>
        <textarea id="rv-edit" className="cu-input dk-rv-edit" value={value} autoFocus onChange={(e) => setDraft({ draft: e.target.value })} />
        <div className="row dk-rv-acts">
          <Button variant="primary" type="submit" data-primary>{t('adr.review.save')}</Button>
          <Button variant="ghost" onClick={() => setDraft({ editing: false, draft: undefined })}>{t('cancel')}</Button>
        </div>
      </form>
    </>)
  }
  return (<>
    {head}
    {said(text) ? <Prose text={text} /> : <p className="dk-rv-lede muted">{t(closed ? 'adr.review.emptyDone' : 'adr.review.empty')}</p>}
    {closed ? null : (
      <div className="row dk-rv-acts">
        <Button variant="primary" data-primary onClick={() => onPart('approve')}>{t('adr.review.approve')}</Button>
        <Button aria-keyshortcuts="E" onClick={() => setDraft({ editing: true })}>{t('adr.review.edit')}</Button>
        <Button variant="ghost" aria-keyshortcuts="D" onClick={() => onPart('defer')}>{t('adr.review.defer')}</Button>
      </div>)}
  </>)
}

function Option({ o, n, closed, pressed, chosen, primary, onPick }) {
  const head = (<>
    <span className="dk-rv-opt-name">{`${o.id} · ${o.name}`}</span>
    {chosen ? <Chip state="ok">{t('adr.review.chosen')}</Chip> : null}
    {closed || n > MAX_OPTIONS ? null : <Keys keys={[String(n)]} />}
  </>)
  const notes = [...(o.pros || []).map((x) => ['pro', `+ ${x}`]), ...(o.cons || []).map((x) => ['con', `− ${x}`])]
  return (
    <div className={cls('dk-rv-opt', pressed && 'is-picked', chosen && 'is-chosen')}>
      {closed ? <div className="dk-rv-pick">{head}</div> : (
        <button type="button" className="dk-rv-pick" aria-pressed={pressed} aria-describedby={notes.length ? `rv-pc-${o.id}` : undefined}
          data-primary={primary || undefined} onClick={onPick}>{head}</button>)}
      {notes.length ? <ul id={`rv-pc-${o.id}`} className="dk-rv-pc">{notes.map(([k, x], i) => <li key={i} className={`is-${k}`}>{x}</li>)}</ul> : null}
    </div>
  )
}

function PointPane({ adr, here, closed, d, setDraft, where, onPoint, onUi }) {
  const point = pointOf(adr, here)
  if (!point) return null
  const options = point.options || []
  const n = adr.points.indexOf(point) + 1
  const picked = closed ? (point.other ? 'other' : point.chosen) : pickOf(point, d)
  const body = closed ? null : choiceBody(point, d)
  const primary = picked === 'other' ? 'other' : options.some((o) => o.id === picked) ? picked : options[0]?.id
  const otherName = point.other ? `${t('adr.review.other')} · ${point.other}` : t('adr.review.other')
  return (<>
    <p className="dk-rv-eyebrow">{`${t('adr.review.pointOf', { n, total: adr.points.length })} · ${where}`}</p>
    <h2 id="rv-h" className="dk-rv-h dk-rv-q">{point.question}</h2>
    {point.deferred && !closed ? <Aviso tone="warn" title={t('adr.review.deferredNote')} /> : null}
    <div className="dk-rv-opts" role="group" aria-labelledby="rv-h">
      {options.map((o, i) => (
        <Option key={o.id} o={o} n={i + 1} closed={closed} pressed={picked === o.id} chosen={!point.other && point.chosen === o.id}
          primary={primary === o.id} onPick={() => setDraft({ picked: o.id })} />))}
      {closed ? (point.other ? (
        <div className="dk-rv-opt is-other is-chosen">
          <div className="dk-rv-pick"><span className="dk-rv-opt-name">{otherName}</span><Chip state="ok">{t('adr.review.chosen')}</Chip></div>
        </div>) : null) : (
        <div className={cls('dk-rv-opt is-other', picked === 'other' && 'is-picked')}>
          <button type="button" className="dk-rv-pick" aria-pressed={picked === 'other'} data-primary={primary === 'other' || undefined}
            onClick={() => setDraft({ picked: 'other' })}>
            <span className="dk-rv-opt-name">{otherName}</span>
            {point.other ? <Chip state="ok">{t('adr.review.chosen')}</Chip> : null}
          </button>
        </div>)}
    </div>
    {closed ? (point.rationale ? <p className="dk-rv-rat"><span className="eyebrow">{t('adr.review.why')}</span> {point.rationale}</p> : null) : (
      <form className="dk-rv-choose" onSubmit={(e) => {
        e.preventDefault()
        if (body) onPoint(body)
        else e.currentTarget.closest('.dk-rv-pane')?.querySelector('.dk-rv-pick')?.focus()
      }}>
        {picked === 'other' ? (
          <div className="cu-field">
            <label className="cu-field-label" htmlFor="rv-other">{t('adr.review.otherLabel')}</label>
            <input id="rv-other" className="cu-input" value={d.other ?? point.other ?? ''} onChange={(e) => setDraft({ other: e.target.value })} />
          </div>) : null}
        <div className="cu-field">
          <label className="cu-field-label" htmlFor="rv-rationale">{t('adr.review.rationale')}</label>
          <input id="rv-rationale" className="cu-input" value={d.rationale ?? point.rationale ?? ''} onChange={(e) => setDraft({ rationale: e.target.value })} />
        </div>
        <div className="row dk-rv-acts">
          <Button variant="primary" type="submit" aria-disabled={body ? undefined : 'true'} aria-describedby={body ? undefined : 'rv-pick'}>
            {t('adr.review.choose')}</Button>
          <Button aria-keyshortcuts="D" onClick={() => onPoint({ op: 'defer', point: point.id })}>{t('adr.review.deferPoint')}</Button>
          <Button variant="ghost" onClick={() => onUi({ dialog: 'remove' })}>{t('adr.review.remove')}</Button>
        </div>
        {body ? null : <p id="rv-pick" className="muted small">{t('adr.review.pick')}</p>}
      </form>)}
  </>)
}

function AffectedPane({ adr, part, closed, where, label, onPart }) {
  const pages = (adr.affected || []).filter((p) => typeof p === 'string' && p)
  const phase = adr.state?.phase
  const lede = !pages.length ? (closed ? t('adr.review.affected.noneDone') : t('adr.review.affected.none'))
    : phase === 'accepted' ? t('adr.review.affected.done') : phase === 'rejected' ? t('adr.review.affected.rejected') : t('adr.review.affected.lede')
  return (<>
    <p className="dk-rv-eyebrow">{eyebrow(where, part)}</p>
    <h2 id="rv-h" className="dk-rv-h">{label}</h2>
    <p className="dk-rv-lede">{lede}</p>
    {pages.length ? <ul className="dk-rv-pages">{pages.map((p) => <li key={p}><code>{p}</code></li>)}</ul> : null}
    {closed ? null : (
      <div className="row dk-rv-acts"><Button variant="primary" data-primary onClick={() => onPart('approve')}>{t('adr.review.approve')}</Button></div>)}
  </>)
}

function AddPoint({ form, onUi, onPoint }) {
  const set = (p) => onUi({ adding: { ...form, ...p } })
  const setOption = (i, p) => set({ options: form.options.map((o, k) => (k === i ? { ...o, ...p } : o)) })
  const body = newPointBody(form)
  const options = form.options?.length ? form.options : blankPoint().options
  return (
    <form className="dk-rv-addf" onSubmit={(e) => { e.preventDefault(); if (body) onPoint(body); else set({ tried: true }) }}>
      <p className="dk-rv-eyebrow">{t('adr.review.addPoint')}</p>
      <h2 id="rv-h" className="dk-rv-h">{t('adr.review.add.title')}</h2>
      <p className="dk-rv-lede">{t('adr.review.add.lede')}</p>
      <div className="cu-field">
        <label className="cu-field-label" htmlFor="rv-q">{t('adr.review.add.question')}</label>
        <input id="rv-q" className="cu-input" value={form.question ?? ''} autoFocus data-primary onChange={(e) => set({ question: e.target.value })} />
      </div>
      <div className="dk-rv-opts">
        {options.map((o, i) => (
          <fieldset key={i} className="dk-rv-opt dk-rv-newopt">
            <legend className="dk-rv-opt-name">{t('adr.review.add.option', { id: letter(i) })}</legend>
            <div className="cu-field">
              <label className="cu-field-label" htmlFor={`rv-o${i}`}>{t('adr.review.add.name')}</label>
              <input id={`rv-o${i}`} className="cu-input" value={o.name ?? ''} onChange={(e) => setOption(i, { name: e.target.value })} />
            </div>
            <div className="cu-field">
              <label className="cu-field-label" htmlFor={`rv-o${i}-pros`}>{t('adr.review.add.pros')}</label>
              <textarea id={`rv-o${i}-pros`} className="cu-input dk-rv-area" rows={2} value={o.pros ?? ''} onChange={(e) => setOption(i, { pros: e.target.value })} />
            </div>
            <div className="cu-field">
              <label className="cu-field-label" htmlFor={`rv-o${i}-cons`}>{t('adr.review.add.cons')}</label>
              <textarea id={`rv-o${i}-cons`} className="cu-input dk-rv-area" rows={2} value={o.cons ?? ''} onChange={(e) => setOption(i, { cons: e.target.value })} />
            </div>
          </fieldset>))}
      </div>
      {form.tried && !body ? <p className="dk-adr-err" role="alert">{t('adr.review.add.need')}</p> : null}
      <div className="row dk-rv-acts">
        <Button variant="primary" type="submit">{t('adr.review.add.go')}</Button>
        {options.length < MAX_OPTIONS ? <Button onClick={() => set({ options: [...options, { name: '' }] })}>{t('adr.review.add.more')}</Button> : null}
        <Button variant="ghost" onClick={() => onUi({ adding: null })}>{t('cancel')}</Button>
      </div>
    </form>
  )
}

function People({ adr, closed, typed = '', onUi, onAttendees }) {
  const names = attendeesOf(adr)
  const add = (e) => {
    e.preventDefault()
    const next = addAttendees(names, typed)
    if (next.length > names.length) onAttendees(next)
    else onUi({ attendee: '' })
  }
  if (closed && !names.length) return null
  return (
    <div className="dk-rv-people" role="group" aria-labelledby="rv-people">
      <span id="rv-people" className="eyebrow">{t('adr.review.attendees')}</span>
      {names.length ? (
        <ul className="dk-rv-who">
          {names.map((n) => {
            const short = initials(n)
            return (
              <li key={n} className="dk-rv-ini">
                <span title={short === n ? undefined : n}>{short}</span>
                {short === n ? null : <span className="sr-only">{n}</span>}
                {closed ? null : (
                  <button type="button" className="dk-adr-x" aria-label={t('adr.review.attendeeRemove', { name: n })}
                    onClick={() => onAttendees(names.filter((x) => x !== n))}><span aria-hidden="true">✕</span></button>)}
              </li>
            )
          })}
        </ul>) : <span className="muted small">{t('adr.review.noAttendees')}</span>}
      {closed ? null : (
        <form className="dk-rv-addwho" onSubmit={add}>
          <label className="sr-only" htmlFor="rv-who">{t('adr.review.attendeeAdd')}</label>
          <input id="rv-who" className="cu-input" placeholder={t('adr.review.attendeePh')} value={typed} onChange={(e) => onUi({ attendee: e.target.value })} />
          <Button size="sm" type="submit">{t('adr.review.attendeeGo')}</Button>
        </form>)}
    </div>
  )
}

// Accept stays reachable while it is refused: it says why, and takes the person to the part in the way.
function Decide({ block, parts, onGo, onUi }) {
  const to = blockedPart(block, parts)
  const why = block ? t(block.key, { point: block.point }) : ''
  return (
    <div className="dk-rv-decide">
      {block ? (to
        ? <button type="button" id="rv-why" className="dk-rv-why" onClick={() => onGo(to)}>{why}<span aria-hidden="true"> →</span></button>
        : <p id="rv-why" className="dk-rv-why">{why}</p>) : null}
      <div className="row">
        <Button onClick={() => onUi({ dialog: 'reject', tried: false })}>{t('adr.review.reject')}</Button>
        <Button variant="primary" aria-disabled={block ? 'true' : undefined} aria-describedby={block ? 'rv-why' : undefined} aria-keyshortcuts="A"
          onClick={() => (block ? to && onGo(to) : onUi({ dialog: 'accept' }))}>{t('adr.review.accept')}</Button>
      </div>
    </div>
  )
}

function KeyHints({ adr, here, closed, present }) {
  const kind = partKind(here)
  const n = Math.min(MAX_OPTIONS, kind === 'point' ? pointOf(adr, here)?.options?.length || 0 : 0)
  const keys = [[['←', '→'], t('adr.review.k.parts')]]
  if (!closed && n) keys.push([[n > 1 ? `1–${n}` : '1'], t('adr.review.k.choose')])
  if (!closed && kind !== 'affected') keys.push([['E'], t('adr.review.k.edit')], [['D'], t('adr.review.k.defer')])
  if (!closed) keys.push([['A'], t('adr.review.k.accept')])
  keys.push(present ? [['Esc'], t('adr.review.k.leave')] : [['P'], t('adr.review.k.present')])
  return (
    <ul className="dk-rv-keys" aria-label={t('adr.review.keys')}>
      {keys.map(([k, word]) => <li key={word}><Keys keys={k} />{` ${word}`}</li>)}
    </ul>
  )
}

// A native modal (CAMARON: what closes or removes something says what happens, in a <dialog>); Esc and Cancel close it.
// The control marked data-autofocus takes the focus when it opens.
function Modal({ open, onClose, labelledBy, children }) {
  const ref = useRef(null)
  useEffect(() => {
    const dlg = ref.current
    if (!dlg?.showModal) return
    if (open && !dlg.open) { dlg.showModal(); dlg.querySelector('[data-autofocus]')?.focus() }
    if (!open && dlg.open) dlg.close()
  }, [open])
  return <dialog ref={ref} className="dk-dialog dk-rv-dlg" aria-labelledby={labelledBy} onClose={onClose}>{open ? children : null}</dialog>
}

function Dialogs({ adr, here, ui, error, onUi, onAccept, onReject, onPoint }) {
  const close = () => onUi({ dialog: null })
  const names = attendeesOf(adr)
  const why = ui.why ?? ''
  const point = pointOf(adr, here)
  const tag = point ? String(point.id).toUpperCase() : ''
  const refused = error ? <Aviso tone="error" title={t('adr.review.failed')} detail={error} /> : null
  return (<>
    <Modal open={ui.dialog === 'accept'} onClose={close} labelledBy="rv-dlg-accept">
      <h2 id="rv-dlg-accept">{t('adr.review.acceptTitle', { id: adr.id })}</h2>
      <p>{t('adr.review.acceptBody')}</p>
      {adr.points?.length ? (
        <ul className="dk-rv-sum">{adr.points.map((p) => (
          <li key={p.id}><b>{`${String(p.id).toUpperCase()} · ${p.question}`}</b> <span aria-hidden="true">→</span> {choiceName(p)}</li>))}</ul>
      ) : <Prose text={adr.sections?.decision} />}
      <p>{names.length ? t('adr.review.acceptBy', { names: names.join(', ') }) : t('adr.review.noAttendees')}</p>
      {adr.state?.supersedes ? <p>{t('adr.review.supersedes', { id: adr.state.supersedes })}</p> : null}
      {refused}
      <div className="row dk-rv-dlg-acts">
        <Button variant="ghost" onClick={close}>{t('cancel')}</Button>
        <Button variant="primary" data-autofocus onClick={onAccept}>{t('adr.review.accept')}</Button>
      </div>
    </Modal>
    <Modal open={ui.dialog === 'reject'} onClose={close} labelledBy="rv-dlg-reject">
      <form onSubmit={(e) => { e.preventDefault(); if (why.trim()) onReject(why.trim()); else onUi({ tried: true }) }}>
        <h2 id="rv-dlg-reject">{t('adr.review.rejectTitle', { id: adr.id })}</h2>
        <p>{t('adr.review.rejectBody')}</p>
        <div className="cu-field">
          <label className="cu-field-label" htmlFor="rv-reject">{t('adr.review.rejectWhy')}</label>
          <textarea id="rv-reject" className="cu-input dk-rv-area" rows={3} value={why} data-autofocus aria-invalid={(ui.tried && !why.trim()) || undefined}
            onChange={(e) => onUi({ why: e.target.value })} />
        </div>
        {ui.tried && !why.trim() ? <p className="dk-adr-err" role="alert">{t('adr.review.rejectNeed')}</p> : null}
        {refused}
        <div className="row dk-rv-dlg-acts">
          <Button variant="ghost" onClick={close}>{t('cancel')}</Button>
          <Button variant="danger" type="submit">{t('adr.review.rejectGo')}</Button>
        </div>
      </form>
    </Modal>
    {point ? (
      <Modal open={ui.dialog === 'remove'} onClose={close} labelledBy="rv-dlg-remove">
        <h2 id="rv-dlg-remove">{t('adr.review.removeTitle', { id: tag })}</h2>
        <p>{t('adr.review.removeBody')}</p>
        {refused}
        <div className="row dk-rv-dlg-acts">
          <Button variant="ghost" data-autofocus onClick={close}>{t('cancel')}</Button>
          <Button variant="danger" onClick={() => onPoint({ op: 'remove', point: point.id })}>{t('adr.review.removeGo', { id: tag })}</Button>
        </div>
      </Modal>) : null}
  </>)
}
