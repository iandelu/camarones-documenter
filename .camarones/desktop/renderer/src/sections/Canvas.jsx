// The nodes of the Plan's canvas: a unit that is not open is a compact card like the board's; one that is open is a
// terminal with what its agent does, as rows from the run's events (canvas.js).
import { useLayoutEffect, useRef, useState } from 'react'
import { Handle, Position, useNodeId } from '@xyflow/react'
import { fmtDuration, money } from '@camaron/ui'
import { atBottom, GLYPH } from '../canvas.js'
import { t } from '../i18n.js'
import { tone } from '../plan.js'

const OUTCOMES = new Set(['ok', 'failed', 'limited', 'cancelled', 'retry'])

// The maximised terminal is the same component outside the flow, where a handle has no node to belong to.
function Ports() {
  if (useNodeId() === null) return null
  return (
    <>
      <Handle type="target" position={Position.Left} className="dk-cv-handle" />
      <Handle type="source" position={Position.Right} className="dk-cv-handle" />
    </>
  )
}

export function UnitNode({ data: { unit, fu, onOpen, onView } }) {
  const k = tone(unit)
  const ran = Boolean(fu?.rows.length)
  const over = fu != null && fu.ended != null
  return (
    <div className={`dk-card dk-cv-unit tone-${k}` + (ran ? ' has-view' : '')}>
      <Ports />
      <button type="button" className="dk-cv-open" onClick={() => onOpen(unit.id)} title={unit.title}>
        <span className="dk-card-title">{unit.title}</span>
        <span className="dk-card-meta"><i></i>{t('tone.' + k)} · <code>{unit.id}</code></span>
        {over ? <span className="dk-card-meta dk-cv-stats">{fmtDuration(Math.max(0, (fu.ended - fu.started) / 1000))} · {money(fu.cost)}</span> : null}
      </button>
      {ran ? <button type="button" className="dk-cv-btn" onClick={() => onView(unit.id)}>{t('cv.view')}</button> : null}
    </div>
  )
}

// Follows the end while the person has not scrolled up to read; scrolling up stops it, the button brings it back.
function Log({ rows, label }) {
  const el = useRef(null)
  const [follow, setFollow] = useState(true)
  useLayoutEffect(() => {
    if (follow && el.current) el.current.scrollTop = el.current.scrollHeight
  }, [rows, follow])
  return (
    <div className="dk-term-body">
      <div ref={el} role="log" aria-live="polite" aria-label={label} tabIndex={0} className="dk-term-log nowheel nodrag nokey"
        onScroll={() => setFollow(atBottom(el.current))}>
        {rows.length ? rows.map((r, i) => <div key={i} className={`k-${r.kind}`}><span aria-hidden="true">{GLYPH[r.kind]}</span> {r.text}</div>)
          : <p className="dk-term-wait">{t('cv.waiting')}</p>}
      </div>
      {follow ? null : <button type="button" className="dk-cv-btn dk-term-follow nodrag" onClick={() => setFollow(true)}>{t('cv.follow')}</button>}
    </div>
  )
}

// `viewed`: the person opened this terminal by hand, so folding it is theirs to do; `finished`: the run ended, so a
// unit with no end of its own is not running any more.
export function TermNode({ data: { unit, fu, now, viewed, finished, onOpen, onView, onMax } }) {
  const k = fu?.outcome === 'failed' ? 'blocked' : tone(unit)
  const running = fu?.ended === null && !finished
  const state = running ? t('cv.st.running') : OUTCOMES.has(fu?.outcome) ? t(`cv.st.${fu.outcome}`) : (fu?.outcome ?? '')
  return (
    <div className={`dk-term tone-${k}`}>
      <Ports />
      <div className="dk-term-head">
        <button type="button" className="dk-term-title" onClick={() => onOpen(unit.id)} title={unit.title}>{unit.title}</button>
        {fu ? (
          <span className="dk-term-meta">
            <span>{fu.runner}</span><span>{state}</span>
            <span>{fmtDuration(Math.max(0, ((fu.ended ?? now) - fu.started) / 1000))}</span><span>{money(fu.cost)}</span>
          </span>
        ) : null}
        {viewed && !running ? <button type="button" className="dk-cv-btn" onClick={() => onView(unit.id)}>{t('cv.hide')}</button> : null}
        <button type="button" className="dk-icon" aria-label={t('cv.max')} title={t('cv.max')} onClick={() => onMax(unit.id)}>⤢</button>
      </div>
      <Log rows={fu?.rows ?? []} label={t('cv.log', { unit: unit.title })} />
    </div>
  )
}
