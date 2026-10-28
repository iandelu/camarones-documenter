// The Plan's canvas: the nodes of the plan's units (a compact card, a read-only terminal while a run's agent works on
// the unit, from the run's events in canvas.js, or a terminal you type in while a session is open with you, Terms.jsx),
// the loose sessions under them, and the container that follows the run and the terminals, lays them out and moves
// between them by keys.
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Background, ReactFlow, ReactFlowProvider, useReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Aviso, Button, fmtDuration, money } from '@camaron/ui'
import { atBottom, canvasKey, clockRuns, emptyFeed, feed, followRun, GLYPH, layout, neighbour, openUnits, place } from '../canvas.js'
import { useTheme } from '../hooks.js'
import { t } from '../i18n.js'
import { tone } from '../plan.js'
import { shown } from '../terminals.js'
import { LaneNode, Ports, PtyNode, useTerminals } from './Terms.jsx'

const OUTCOMES = new Set(['failed', 'limited', 'cancelled', 'retry'])

// What the terminal's header says once the agent is no longer at work: `ok` is only its exit code, so a unit is called
// done when the plan has it done, and otherwise by its state in the plan (to do, paused, blocked, awaiting you…), as
// is a unit with no end of its own in a run that is over (a stopped autopilot).
function endWord(fu, unit) {
  if (fu.outcome === 'ok' || fu.outcome == null) return fu.status === 'done' ? t('cv.st.ok') : t('tone.' + tone(unit))
  return OUTCOMES.has(fu.outcome) ? t(`cv.st.${fu.outcome}`) : (fu.outcome ?? '')
}

// A paused unit (its session closed, the unit still in progress) says so instead of its state and offers to continue
// it, its buttons beside the note: the run's terminal, when a run worked on it, as a glyph that fits there. It drops the
// time and cost a run left (that terminal still has them).
export function UnitNode({ data: { unit, fu, onOpen, onView, onSession, canStart } }) {
  const k = tone(unit)
  const paused = k === 'paused'
  const ran = Boolean(fu?.rows.length)
  const over = fu != null && fu.ended != null && !paused
  return (
    <div className={`dk-card dk-cv-unit tone-${k}` + (ran ? ' has-view' : '') + (paused ? ' is-paused' : '')}>
      <Ports />
      <button type="button" className="dk-cv-open" onClick={() => onOpen(unit.id)} title={unit.title}>
        <span className="dk-card-title">{unit.title}</span>
        {paused ? <span className="dk-card-meta"><span className="dk-cv-note">{t('cv.paused')}</span></span>
          : <span className="dk-card-meta"><i></i>{t('tone.' + k)} · <code>{unit.id}</code></span>}
        {over ? <span className="dk-card-meta dk-cv-stats">{fmtDuration(Math.max(0, (fu.ended - fu.started) / 1000))} · {money(fu.cost)}</span> : null}
      </button>
      {paused || ran ? (
        <span className="dk-cv-acts">
          {paused ? <button type="button" className="dk-cv-btn" disabled={!canStart} onClick={() => onSession(unit.id, 'continue')}>{t('unit.continue')}</button> : null}
          {ran && paused ? <button type="button" className="dk-cv-btn dk-cv-glyph" aria-label={t('cv.view')} title={t('cv.view')}
            onClick={() => onView(unit.id)}>&gt;_</button> : null}
          {ran && !paused ? <button type="button" className="dk-cv-btn" onClick={() => onView(unit.id)}>{t('cv.view')}</button> : null}
        </span>
      ) : null}
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
  const state = !fu ? '' : running ? t('cv.st.running') : endWord(fu, unit)
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

const NODE_TYPES = { unit: UnitNode, term: TermNode, pty: PtyNode, lane: LaneNode }
const POSITIONS = 'dk.canvasPos'
const BATCH_MS = 150
const FIT = { padding: 0.15, maxZoom: 1 }
const WIDE = new Set(['term', 'pty'])

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
// The terminals with you come from useTerminals: a unit's newest one is its node, the loose ones go under the graph.
// `focus`: a terminal to put in front (the Plan's #/plan?term=<id>), once the list has it; then onFocused().
function Flow({ srv, units, run, pilot, onOpen, focus, onFocused, onSession, canStart, noAgent }) {
  const log = useRunFeed(srv, run)
  const ended = log.finished || Boolean(run?.finished)
  const f = useMemo(() => (ended === log.finished ? log : { ...log, finished: true }), [log, ended])
  const terms = useTerminals(srv)
  const theme = useTheme()
  const rf = useReactFlow()
  const frame = useRef(null)
  const back = useRef(null)
  const [now, setNow] = useState(Date.now)
  const [viewed, setViewed] = useState(() => new Set())
  const [saved, setSaved] = useState(savedPositions)
  const [drag, setDrag] = useState({})
  const [max, setMax] = useState(null)              // {id, pty}: a run's terminal (by its unit) or one with you
  const [refit, setRefit] = useState(0)
  const [error, setError] = useState(null)          // {title, detail}: what the server refused
  const [note, setNote] = useState(null)            // {key, vars}: a session that opened in a window, not here
  const live = Boolean(run) && !run.finished
  const onView = useCallback((id) => setViewed((v) => toggled(v, id)), [])
  const maxTerm = useCallback((id) => setMax({ id, pty: false }), [])
  const maxPty = useCallback((id) => setMax({ id, pty: true }), [])
  const session = useCallback((uid, mode) => {
    setError(null)
    setNote(null)
    return Promise.resolve().then(() => onSession(uid, mode)).then((n) => setNote(n || null),
      (e) => setError({ title: 'next.failed', detail: e.message }))
  }, [onSession])
  const close = useCallback((id) => {
    setError(null)
    return terms.close(id).catch((e) => setError({ title: 'unit.failed', detail: e.message }))
  }, [terms.close])
  const dataOf = (unit) => ({ unit, fu: f.units[unit.id], now, viewed: viewed.has(unit.id), finished: f.finished, onOpen, onView,
    onMax: maxTerm, onSession: session, canStart })

  const mine = useMemo(() => shown(terms.list, now), [terms.list, now])
  const { nodes, edges } = useMemo(() => {
    const pty = new Set(mine.units.keys())
    const laid = layout(units, openUnits(units, f, viewed, now, pty), { pty, loose: mine.loose })
    const placed = place(laid.nodes, { ...saved, ...drag })
    const look = (n) => {
      if (n.type === 'lane') return { data: { label: t('pty.loose') } }
      if (n.type !== 'pty') return { ariaLabel: n.data.unit.title, data: dataOf(n.data.unit) }
      const { unit } = n.data
      const term = unit ? mine.units.get(unit.id) : n.data.term
      return { ariaLabel: unit?.title ?? t('pty.update'),
        data: { unit, term, now, attach: terms.attach, onClose: close, onMax: maxPty, onSession: session, canStart } }
    }
    const sized = placed.map((n) => ({ ...n, measured: { width: n.width, height: n.height }, ...look(n) }))
    return { edges: laid.edges, nodes: sized }
  }, [units, f, viewed, now, saved, drag, onOpen, onView, mine, terms.attach, close, session, canStart])
  const opened = nodes.filter((n) => WIDE.has(n.type))
  // A failed terminal shows a time that no longer moves; a clean end ticks through its fold window.
  const ticking = live || clockRuns(f, now) || [...mine.units.values(), ...mine.loose].some((x) => x.ended == null || x.code === 0)

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
  // A run's terminal stays maximised once its unit folds; a terminal with you only while it is on the canvas.
  const maxPtyNode = max?.pty ? nodes.find((n) => n.id === max.id && n.type === 'pty') : null
  const maxUnit = max && !max.pty ? units.find((u) => u.id === max.id) : null
  const maxed = Boolean(maxPtyNode || maxUnit)
  const leave = () => { back.current = max?.id ?? null; setMax(null) }
  useEffect(() => {
    if (max === null && back.current !== null) { nodeEl(back.current)?.focus(); back.current = null }
  }, [max])
  useEffect(() => { if (max && !maxed) leave() }, [max, maxed])
  useEffect(() => { if (maxPtyNode) terms.focus(maxPtyNode.data.term.id) }, [maxPtyNode?.data.term.id])

  // A terminal opened elsewhere (Summary, the detail) may not be listed yet: the list is asked for it.
  useEffect(() => { if (focus && !terms.list.some((x) => x.id === focus)) terms.refresh() }, [focus])
  useEffect(() => {
    const term = focus && terms.list.find((x) => x.id === focus)
    if (!term) return
    const id = term.kind === 'unit' ? term.unit : term.id
    const n = nodes.find((x) => x.id === id && x.type === 'pty' && x.data.term?.id === term.id)
    if (n && max && !(max.pty && max.id === id)) { setMax(null); return }      // the canvas under a maximised node is inert
    if (n) { reveal(n); terms.focus(term.id) }
    onFocused?.()
  }, [focus, terms.list, max])

  const onKeyDown = (e) => {
    const el = e.target.closest('.react-flow__node')
    const what = canvasKey(e.key, { inTerminal: Boolean(e.target.closest('.dk-pty-slot')), inLog: Boolean(e.target.closest('.dk-term-log')),
      maxed, node: Boolean(el), self: e.target === el, mods: e.altKey || e.ctrlKey || e.metaKey })
    if (what === 'leave') { e.preventDefault(); leave(); return }
    if (what === 'node') { e.preventDefault(); el?.focus(); return }
    if (what === 'open') {
      e.preventDefault()
      const n = nodes.find((x) => x.id === el.dataset.id)
      if (n?.type === 'pty') terms.focus(n.data.term.id); else onOpen(el.dataset.id)
      return
    }
    if (!what) return
    const to = neighbour(nodes.filter((n) => n.type !== 'lane'), el.dataset.id, what)
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
      {noAgent ? <Aviso tone="warn" title={t('next.noAgent')}><Button size="sm" href="#/machine">{t('next.machine')}</Button></Aviso> : null}
      {error ? <Aviso tone="error" title={t(error.title)} detail={error.detail} /> : null}
      {note ? <Aviso tone="info" title={t(note.key, note.vars)} /> : null}
      <div ref={frame} className="dk-canvas">
        <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} onNodesChange={onNodesChange} onNodeDragStop={onNodeDragStop}
          colorMode={theme} fitView fitViewOptions={FIT} minZoom={0.2} nodesConnectable={false} edgesFocusable={false}
          deleteKeyCode={null} disableKeyboardA11y proOptions={{ hideAttribution: true }} aria-label={t('cv.label')}
          inert={maxed ? true : undefined}>
          <Background gap={24} size={1} />
        </ReactFlow>
        {maxed ? (
          <div className="dk-term-max">
            <div className="dk-term-max-bar">
              <button type="button" className="dk-cv-btn" autoFocus={!maxPtyNode} onClick={leave}>{t('cv.restore')}</button>
            </div>
            {maxPtyNode ? <PtyNode data={maxPtyNode.data} /> : <TermNode data={dataOf(maxUnit)} />}
          </div>
        ) : null}
      </div>
    </div>
  )
}

export default function Canvas(props) {
  return <ReactFlowProvider><Flow {...props} /></ReactFlowProvider>
}
