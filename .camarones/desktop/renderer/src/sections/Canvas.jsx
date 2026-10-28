// The Plan's canvas: the nodes of the plan's units (a compact card, or a terminal while the unit's agent works, from
// the run's events in canvas.js) and the container that follows the run, lays them out and moves between them by keys.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Background, ReactFlow, ReactFlowProvider, useReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Button, fmtDuration, money } from '@camaron/ui'
import { atBottom, clockRuns, emptyFeed, feed, followRun, GLYPH, layout, neighbour, openUnits, place } from '../canvas.js'
import { useTheme } from '../hooks.js'
import { t } from '../i18n.js'
import { tone } from '../plan.js'
import { Ports } from './Terms.jsx'

const OUTCOMES = new Set(['failed', 'limited', 'cancelled', 'retry'])

// What the terminal's header says once the agent is no longer at work: `ok` is only its exit code, so a unit is called
// done when the plan has it done, and otherwise by its state in the plan (to do, paused, blocked, awaiting you…), as
// is a unit with no end of its own in a run that is over (a stopped autopilot).
function ended(fu, unit) {
  if (fu.outcome === 'ok' || fu.outcome == null) return fu.status === 'done' ? t('cv.st.ok') : t('tone.' + tone(unit))
  return OUTCOMES.has(fu.outcome) ? t(`cv.st.${fu.outcome}`) : (fu.outcome ?? '')
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
// Only a unit at work waits for its agent: one that ended with no line has nothing more to show.
function Log({ rows, label, running }) {
  const el = useRef(null)
  const [follow, setFollow] = useState(true)
  useLayoutEffect(() => {
    if (follow && el.current) el.current.scrollTop = el.current.scrollHeight
  }, [rows, follow])
  return (
    <div className="dk-term-body">
      <div ref={el} role="log" aria-live="polite" aria-label={label} tabIndex={0} className="dk-term-log nowheel nodrag nokey"
        onScroll={() => setFollow(atBottom(el.current))}>
        {rows.length ? rows.map((r) => <div key={r.seq} className={`k-${r.kind}`}><span aria-hidden="true">{GLYPH[r.kind]}</span> {r.text}</div>)
          : running ? <p className="dk-term-wait">{t('cv.waiting')}</p> : null}
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
  const state = !fu ? '' : running ? t('cv.st.running') : ended(fu, unit)
  return (
    <div className={`dk-term tone-${k}`}>
      <Ports />
      <div className="dk-term-head">
        <button type="button" className="dk-term-title" onClick={() => onOpen(unit.id)} title={unit.title}>{unit.title}</button>
        {fu ? (
          <span className="dk-term-meta">
            <span>{fu.runner}</span><span>{state}</span>
            <span>{fmtDuration(Math.max(0, ((fu.ended ?? (running ? now : fu.last ?? now)) - fu.started) / 1000))}</span><span>{money(fu.cost)}</span>
          </span>
        ) : null}
        {viewed && !running ? <button type="button" className="dk-cv-btn" onClick={() => onView(unit.id)}>{t('cv.hide')}</button> : null}
        <button type="button" className="dk-icon" aria-label={t('cv.max')} title={t('cv.max')} onClick={() => onMax(unit.id)}>⤢</button>
      </div>
      <Log rows={fu?.rows ?? []} label={t('cv.log', { unit: unit.title })} running={running} />
    </div>
  )
}

const NODE_TYPES = { unit: UnitNode, term: TermNode }
const POSITIONS = 'dk.canvasPos'
const BATCH_MS = 150
const FIT = { padding: 0.15, maxZoom: 1 }
const ARROW = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' }

const savedPositions = () => {
  try { return JSON.parse(localStorage.getItem(POSITIONS)) || {} } catch { return {} }
}

// A run's events, folded into one feed every BATCH_MS: a busy agent would otherwise render on every line. Once the
// Plan's poll says the run is over, a stream that ends is not opened again.
function useRunFeed(srv, run) {
  const [f, setF] = useState(() => emptyFeed(run?.run ?? null))
  const id = run?.run
  const over = useRef(false)
  over.current = Boolean(run?.finished)
  useEffect(() => {
    if (!id) return undefined
    const stop = new AbortController()
    const buffer = []
    const flush = () => {
      if (stop.signal.aborted || !buffer.length) return
      const events = buffer.splice(0)
      setF((cur) => events.reduce(feed, cur))
    }
    setF(emptyFeed(id))
    const timer = setInterval(flush, BATCH_MS)
    followRun(srv, id, (ev) => buffer.push(ev), { signal: stop.signal, over: () => over.current })
      .finally(() => { clearInterval(timer); flush() })
    return () => { stop.abort(); clearInterval(timer) }
  }, [srv, id])
  return f
}

const toggled = (ids, id) => {
  const next = new Set(ids)
  if (!next.delete(id)) next.add(id)
  return next
}

// The run is over when its log says so or when the Plan's poll does: a run stopped from outside never logs its end.
function Flow({ srv, units, run, pilot, onOpen }) {
  const log = useRunFeed(srv, run)
  const ended = log.finished || Boolean(run?.finished)
  const f = useMemo(() => (ended === log.finished ? log : { ...log, finished: true }), [log, ended])
  const theme = useTheme()
  const rf = useReactFlow()
  const frame = useRef(null)
  const back = useRef(null)
  const [now, setNow] = useState(Date.now)
  const [viewed, setViewed] = useState(() => new Set())
  const [saved, setSaved] = useState(savedPositions)
  const [drag, setDrag] = useState({})
  const [max, setMax] = useState(null)
  const [refit, setRefit] = useState(0)
  const live = Boolean(run) && !run.finished
  const onView = useCallback((id) => setViewed((v) => toggled(v, id)), [])
  const maxed = max === null ? null : units.find((u) => u.id === max)
  const dataOf = (unit) => ({ unit, fu: f.units[unit.id], now, viewed: viewed.has(unit.id), finished: f.finished, onOpen, onView, onMax: setMax })

  const { nodes, edges } = useMemo(() => {
    const open = openUnits(units, f, viewed, now)
    const laid = layout(units, open)
    const placed = place(laid.nodes, { ...saved, ...drag })
    const sized = placed.map((n) => ({ ...n, measured: { width: n.width, height: n.height }, ariaLabel: n.data.unit.title, data: dataOf(n.data.unit) }))
    return { edges: laid.edges, nodes: sized }
  }, [units, f, viewed, now, saved, drag, onOpen, onView])
  const opened = nodes.filter((n) => n.type === 'term')
  const ticking = live || clockRuns(f, now)

  useEffect(() => {
    if (!ticking) return undefined
    setNow(Date.now())
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [ticking])

  const fit = () => rf.fitView({ ...FIT, duration: 200, nodes: opened.length ? opened.map(({ id }) => ({ id })) : undefined })
  useEffect(() => { if (refit) fit() }, [refit])
  const relayout = () => {
    try { localStorage.removeItem(POSITIONS) } catch { /* private window: nothing was kept */ }
    setSaved({})
    setDrag({})
    setRefit((n) => n + 1)
  }

  const onNodesChange = useCallback((changes) => {
    const moved = changes.filter((c) => c.type === 'position' && c.position)
    if (moved.length) setDrag((d) => ({ ...d, ...Object.fromEntries(moved.map((c) => [c.id, c.position])) }))
  }, [])
  const onNodeDragStop = (_, __, dragged) => {
    const next = { ...saved, ...Object.fromEntries(dragged.map((n) => [n.id, { x: n.position.x, y: n.position.y }])) }
    setSaved(next)
    setDrag({})
    try { localStorage.setItem(POSITIONS, JSON.stringify(next)) } catch { /* private window: not kept */ }
  }

  const nodeEl = (id) => [...frame.current.querySelectorAll('.react-flow__node')].find((el) => el.dataset.id === id)
  const reveal = (n) => {
    const { x, y, zoom } = rf.getViewport()
    const box = frame.current.getBoundingClientRect()
    const left = n.position.x * zoom + x
    const top = n.position.y * zoom + y
    if (left < 0 || top < 0 || left + n.width * zoom > box.width || top + n.height * zoom > box.height) {
      rf.setCenter(n.position.x + n.width / 2, n.position.y + n.height / 2, { zoom, duration: 200 })
    }
  }
  const leave = () => { back.current = max; setMax(null) }
  useEffect(() => {
    if (max === null && back.current !== null) { nodeEl(back.current)?.focus(); back.current = null }
  }, [max])

  const onKeyDown = (e) => {
    if (e.key === 'Escape' && maxed) { e.preventDefault(); leave(); return }
    if (e.target.closest('.nokey')) return
    const el = e.target.closest('.react-flow__node')
    if (!el) return
    if ((e.key === 'Enter' || e.key === ' ') && e.target === el) { e.preventDefault(); onOpen(el.dataset.id); return }
    const dir = ARROW[e.key]
    if (!dir || e.altKey || e.ctrlKey || e.metaKey) return
    const to = neighbour(nodes, el.dataset.id, dir)
    if (!to) return
    e.preventDefault()
    nodeEl(to)?.focus({ preventScroll: true })
    reveal(nodes.find((n) => n.id === to))
  }

  const started = run && Date.parse(run.started)
  const status = live
    ? t('cv.status', { kind: t(pilot ? 'cv.pilot' : 'cv.run'), done: run.done, units: run.units,
      time: fmtDuration(Number.isFinite(started) ? Math.max(0, (now - started) / 1000) : run.seconds), cost: money(run.cost_usd) })
    : t('cv.idle')
  return (
    <div className="dk-cv" onKeyDown={onKeyDown}>
      <div className="row">
        <span className="dk-grow">{status}</span>
        <Button size="sm" onClick={fit}>{t('cv.fit')}</Button>
        <Button size="sm" onClick={relayout}>{t('cv.relayout')}</Button>
      </div>
      <div ref={frame} className="dk-canvas">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} onNodesChange={onNodesChange} onNodeDragStop={onNodeDragStop}
          colorMode={theme} fitView fitViewOptions={FIT} minZoom={0.2} nodesConnectable={false} edgesFocusable={false}
          disableKeyboardA11y proOptions={{ hideAttribution: true }} aria-label={t('cv.label')} inert={maxed ? true : undefined}>
          <Background gap={24} size={1} />
        </ReactFlow>
        {maxed ? (
          <div className="dk-term-max">
            <div className="dk-term-max-bar">
              <button type="button" className="dk-cv-btn" autoFocus onClick={leave}>{t('cv.restore')}</button>
            </div>
            <TermNode data={dataOf(maxed)} />
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default function Canvas(props) {
  return <ReactFlowProvider><Flow {...props} /></ReactFlowProvider>
}
