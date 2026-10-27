import { createContext, useContext, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Button } from '@camaron/ui'
import { TOURS, holes, place, tourAction } from './tour.js'
import { sectionOf } from './nav.js'
import { typing } from './palette.js'
import { t } from './i18n.js'

// The guided tour over the app's real controls: one overlay for the window, started from the Guide, Machine, the
// palette or the Summary's offer through useTour().start(id). Each step goes to its section, waits a moment for its
// [data-tour] target, dims the rest and points at it; a target that is not on screen gets the bubble centred.

const TourContext = createContext({ start: () => {}, stop: () => {}, active: null })
export const useTour = () => useContext(TourContext)

export function TourProvider({ children }) {
  const [state, setState] = useState(null)               // {id, i}
  const value = { start: (id) => { if (TOURS[id]) setState({ id, i: 0 }) }, stop: () => setState(null), active: state?.id || null }
  return (
    <TourContext.Provider value={value}>
      {children}
      {state ? <TourLayer key={`${state.id}/${state.i}`} state={state} setState={setState} /> : null}
    </TourContext.Provider>
  )
}

const LOOK_MS = 100
const LOOK_TRIES = 15
const reduced = () => typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
const viewport = () => ({ w: innerWidth, h: innerHeight })
const box = (el) => { const r = el.getBoundingClientRect(); return { top: r.top, left: r.left, width: r.width, height: r.height } }

function TourLayer({ state, setState }) {
  const steps = TOURS[state.id]
  const step = steps[state.i]
  const [found, setFound] = useState(undefined)           // undefined: looking; null: not on screen; else the element
  const [rect, setRect] = useState(null)
  const [view, setView] = useState(viewport)
  const [size, setSize] = useState({ w: 340, h: 180 })
  const bubble = useRef(null)
  const go = (i) => (i < 0 ? null : i >= steps.length ? setState(null) : setState({ id: state.id, i }))
  useEffect(() => {
    if (step.section && sectionOf(location.hash, {}) !== step.section) location.hash = `#/${step.section}`
    let tries = 0
    let timer
    const look = () => {
      const el = document.querySelector(`[data-tour="${step.target}"]`)
      const r = el && el.getBoundingClientRect()
      if (r && r.width > 0 && r.height > 0) {
        el.scrollIntoView({ block: 'center', behavior: reduced() ? 'auto' : 'smooth' })
        setFound(el)
        setRect(box(el))
      } else if (++tries >= LOOK_TRIES) setFound(null)
      else timer = setTimeout(look, LOOK_MS)
    }
    look()
    return () => clearTimeout(timer)
  }, [])
  useEffect(() => {                                       // the window moves: draw again where the target is now
    const redraw = () => { setView(viewport()); if (found) setRect(box(found)) }
    addEventListener('resize', redraw)
    addEventListener('scroll', redraw, true)
    const settle = found ? setTimeout(redraw, reduced() ? 0 : 350) : null   // after a smooth scroll into view
    return () => { removeEventListener('resize', redraw); removeEventListener('scroll', redraw, true); clearTimeout(settle) }
  }, [found])
  useEffect(() => {                                       // the tour's keys, on the bubble only; the page keeps its own
    const on = (e) => {
      const b = bubble.current
      const at = e.target
      const inBubble = !!b && at !== b && b.contains(at)
      const onBubble = at === b || !at || at === document.body
      if (e.key === 'Tab' && (inBubble || onBubble)) { trap(e, b); return }
      const k = tourAction(e.key, { typing: typing(at), inBubble, onBubble })
      if (!k) return
      e.preventDefault()
      e.stopPropagation()
      if (k === 'close') setState(null)
      else go(state.i + (k === 'next' ? 1 : -1))
    }
    addEventListener('keydown', on, true)
    const away = () => { if (step.section && sectionOf(location.hash, {}) !== step.section) setState(null) }   // left mid-tour (g + a letter)
    addEventListener('hashchange', away)
    return () => { removeEventListener('keydown', on, true); removeEventListener('hashchange', away) }
  }, [])
  useLayoutEffect(() => {
    if (!bubble.current) return
    const b = { w: bubble.current.offsetWidth, h: bubble.current.offsetHeight }
    if (b.w !== size.w || b.h !== size.h) setSize(b)
    bubble.current.focus({ preventScroll: true })
  }, [found])
  if (found === undefined) return <div className="dk-tour" aria-hidden="true"><div className="dk-tour-dim" style={{ top: 0, left: 0, width: view.w, height: view.h }} /></div>
  const target = found ? rect : null
  const where = place(target, size, view)
  return (
    <div className="dk-tour">
      {target
        ? holes(target, view).map((b, i) => <div key={i} className="dk-tour-dim" style={b} />)
        : <div className="dk-tour-dim" style={{ top: 0, left: 0, width: view.w, height: view.h }} />}
      {target ? <div className="dk-tour-ring" style={{ top: target.top - 6, left: target.left - 6, width: target.width + 12, height: target.height + 12 }} /> : null}
      <TourBubble innerRef={bubble} style={{ top: where.top, left: where.left }} side={where.side}
        title={t(`tour.${state.id}.${state.i + 1}.t`)} body={t(`tour.${state.id}.${state.i + 1}.b`)} n={state.i + 1} m={steps.length}
        missing={!found} onBack={() => go(state.i - 1)} onNext={() => go(state.i + 1)} onClose={() => setState(null)} />
    </div>
  )
}

// Tab stays inside the bubble while the tour is open.
function trap(e, root) {
  const items = root ? [...root.querySelectorAll('button')] : []
  if (!items.length) return
  const at = items.indexOf(document.activeElement)
  const next = e.shiftKey ? (at <= 0 ? items.length - 1 : at - 1) : (at === items.length - 1 ? 0 : at + 1)
  e.preventDefault()
  items[next].focus()
}

export function TourBubble({ title, body, n, m, missing = false, onBack, onNext, onClose, style, side = 'center', innerRef }) {
  return (
    <div ref={innerRef} className={`dk-tour-bubble ${side}`} role="dialog" aria-modal="true" aria-labelledby="dk-tour-title"
      tabIndex={-1} style={style}>
      <span className="eyebrow">{t('tour.of', { n, m })}</span>
      <b id="dk-tour-title" className="dk-tour-title">{title}</b>
      {missing ? <p className="muted small">{t('tour.missing')}</p> : null}
      <p className="dk-tour-body">{body}</p>
      <div className="row">
        {n > 1 ? <Button size="sm" variant="ghost" onClick={onBack}>{t('tour.back')}</Button> : null}
        <span className="dk-grow"></span>
        <Button size="sm" variant="ghost" onClick={onClose}>{t('tour.close')}</Button>
        <Button size="sm" variant="primary" onClick={onNext}>{n === m ? t('tour.done') : t('tour.next')}</Button>
      </div>
    </div>
  )
}
