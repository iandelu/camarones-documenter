// The canvas's real terminals: a session opened by hand runs on a PTY of the project's server (lib/terminals.py) and
// shows on its node as an xterm.js screen, fed by one server-sent stream for every terminal (terminals.js).
// useTerminals keeps that stream and one screen per terminal; PtyNode shows one, LaneNode titles the loose ones.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Handle, Position, useNodeId } from '@xyflow/react'
import '@xterm/xterm/css/xterm.css'
import { fmtDuration } from '@camaron/ui'
import { useTheme } from '../hooks.js'
import { t } from '../i18n.js'
import { tone } from '../plan.js'
import { bytes, elapsed, fitSize, followTerminals, historyBytes, inputPieces, nap, needsScreen, screenFeed } from '../terminals.js'

const LIST = 'app/terminals'
const SETTLE_MS = 150
const RETRY_MS = 2000
const SCREEN = { scrollback: 5000, screenReaderMode: true, fontSize: 12 }

// xterm.js needs a DOM: it loads with the first terminal, never on import, so the nodes render to text in the tests.
let modules = null
const xterm = () => (modules ??= Promise.all([import('@xterm/xterm'), import('@xterm/addon-fit')]).then(
  ([{ Terminal }, { FitAddon }]) => ({ Terminal, FitAddon }),
  (e) => { modules = null; throw e }))

// F6 is the canvas's, the way out of a terminal (canvas.js canvasKey): xterm leaves it alone. Shift+Tab is the agent's
// alone (Claude Code changes its permission mode with it): xterm sends it, and it no longer moves the focus out too.
export function screenKey(e) {
  if (e.key === 'F6') return false
  if (e.type === 'keydown' && e.key === 'Tab' && e.shiftKey) e.preventDefault()
  return true
}

// The maximised node is the same component outside the flow, where a handle has no node to belong to.
export function Ports() {
  if (useNodeId() === null) return null
  return (
    <>
      <Handle type="target" position={Position.Left} className="dk-cv-handle" />
      <Handle type="source" position={Position.Right} className="dk-cv-handle" />
    </>
  )
}

// One screen per terminal: an xterm opened once into a host div that moves between the slots showing it. The slots
// stack (the node, then its maximised copy): the newest has the screen, and when it goes the one below takes it back.
function desk(srv, onList) {
  const screens = new Map()
  const ended = new Set()          // the server says an end again on every reconnect: the list is asked once
  const gone = new Set()           // closed here: what they print on the way out has no screen to go to
  let offsets = {}
  let list = []
  let upTo = new Map()             // how far each terminal's output went when the stream opened: history up to there
  let busy = null
  let again = false

  // One request at a time; asked again while one is out, it runs once more after it, so the list is never older.
  // Resolves to null once listed, else the refusal.
  const refresh = () => {
    if (busy) { again = true; return busy }
    busy = (async () => {
      let failed = null
      do {
        again = false
        try {
          const r = await srv.get(LIST)
          list = r.terminals || []
          failed = null
          onList({ list, available: Boolean(r.available) })
        } catch (e) { failed = e }   // a server without terminals, or gone: the list stays as it was
      } while (again)
      busy = null
      return failed
    })()
    return busy
  }

  // Keys go in order, one request after another; what is typed meanwhile goes in the next. A refused piece (the
  // program ended, or took nothing for 5 s) drops the rest of that paste rather than type it with a hole.
  const send = async (x, data) => {
    x.queue.push(data)
    if (x.sending) return
    x.sending = true
    while (x.queue.length && !x.gone) {
      for (const piece of inputPieces(x.queue.splice(0).join(''))) {
        try { await srv.post(`${LIST}/${x.id}/input`, { data: piece }) } catch { break }
      }
    }
    x.sending = false
  }

  // The slot's font and colours, so the screen is the dark body of the read-only log in either theme.
  const style = (x, slot) => {
    const css = getComputedStyle(slot)
    const o = x.term.options
    if (o.fontFamily !== css.fontFamily) o.fontFamily = css.fontFamily
    if (o.theme?.background !== css.backgroundColor || o.theme?.foreground !== css.color) {
      o.theme = { background: css.backgroundColor, foreground: css.color }
    }
  }

  // A slot with no size (hidden) proposes nothing: the program keeps the size it had.
  const fit = (x) => {
    const slot = x.slots.at(-1)
    if (!x.term || x.gone || !slot?.clientWidth || !slot.clientHeight) return
    const size = fitSize(x.fitter.proposeDimensions())
    if (size && (size.cols !== x.term.cols || size.rows !== x.term.rows)) x.term.resize(size.cols, size.rows)
  }

  const place = (x) => {
    const slot = x.slots.at(-1)
    x.ro?.disconnect()
    x.ro = null
    if (!slot) { x.host.remove(); return }
    if (x.host.parentNode !== slot) slot.append(x.host)
    if (!x.term) return
    style(x, slot)
    fit(x)
    x.ro = new ResizeObserver(() => { clearTimeout(x.fitting); x.fitting = setTimeout(() => fit(x), SETTLE_MS) })
    x.ro.observe(slot)
    if (x.wantsFocus) { x.wantsFocus = false; x.term.focus() }
  }

  // A terminal the list does not know yet is asked for first: its xterm starts at the PTY's size, so what the
  // program drew for that size is read at it.
  const make = (id) => {
    const host = document.createElement('div')
    host.className = 'dk-pty-screen nowheel nodrag nopan nokey'
    const x = { id, host, slots: [], term: null, fitter: null, queue: [], sending: false, wantsFocus: false, gone: false }
    const meta = () => list.find((m) => m.id === id)
    x.ready = Promise.all([xterm(), meta() ? null : refresh()]).then(([{ Terminal, FitAddon }]) => {
      if (x.gone) return null
      const m = meta()
      const term = new Terminal({ ...SCREEN, cols: m?.cols || 80, rows: m?.rows || 24 })
      x.fitter = new FitAddon()
      term.loadAddon(x.fitter)
      term.attachCustomKeyEventHandler(screenKey)
      term.open(host)
      x.write = screenFeed(term, (data) => send(x, data))
      term.onResize(({ cols, rows }) => {
        clearTimeout(x.sizing)
        x.sizing = setTimeout(() => srv.post(`${LIST}/${id}/resize`, { cols, rows }).catch(() => {}), SETTLE_MS)
      })
      x.term = term
      place(x)
      return term
    }).catch(() => null)
    screens.set(id, x)
    return x
  }
  const screen = (id) => screens.get(id) ?? make(id)

  const drop = (x) => {
    x.gone = true
    clearTimeout(x.fitting)
    clearTimeout(x.sizing)
    x.ro?.disconnect()
    x.term?.dispose()
    x.host.remove()
    if (screens.get(x.id) === x) screens.delete(x.id)
  }

  const onEvent = (ev) => {
    const id = ev?.t
    if (typeof id !== 'string') return
    if (Number.isFinite(ev.o)) offsets[id] = ev.o
    if ('end' in ev) {
      if (!ended.has(id)) { ended.add(id); refresh() }
      return
    }
    if (gone.has(id) || typeof ev.d !== 'string') return
    if (!screens.has(id) && !needsScreen(id, list, Date.now())) return
    const x = screen(id)
    const data = bytes(ev.d)
    const cut = historyBytes(ev.o, data.length, upTo.get(id))
    x.ready.then((term) => {
      if (!term || x.gone) return
      if (cut > 0) x.write(data.subarray(0, cut), true)
      if (cut < data.length) x.write(data.subarray(cut), false)
    })
  }

  return {
    refresh,
    onEvent,
    offsets: () => offsets,
    // Called with the list the stream opens after: what each terminal had printed by its listed offset is history.
    mark() { upTo = new Map(list.map((m) => [m.id, m.offset])) },
    attach(id, el) {
      if (gone.has(id)) return () => {}
      const x = screen(id)
      x.slots.push(el)
      place(x)
      return () => {
        const at = x.slots.lastIndexOf(el)
        if (at < 0) return
        x.slots.splice(at, 1)
        if (at === x.slots.length && !x.gone) place(x)
      }
    },
    focus(id) {
      if (gone.has(id)) return
      const x = screen(id)
      if (x.term && x.slots.length) x.term.focus(); else x.wantsFocus = true
    },
    // Live: the server hangs it up; ended: it forgets it. Either way its screen goes.
    async close(id) {
      try {
        await srv.post(`${LIST}/${id}/close`, {})
        gone.add(id)
        if (screens.has(id)) drop(screens.get(id))
      } finally { await refresh() }
    },
    restyle() {
      for (const x of screens.values()) if (x.term && x.slots.length) style(x, x.slots.at(-1))
    },
    // The stream's life ends here; a remount (React's dev double effect) replays every terminal from the start.
    dispose() {
      for (const x of [...screens.values()]) drop(x)
      offsets = {}
      upTo = new Map()
      ended.clear()
    },
  }
}

export function useTerminals(srv) {
  const [state, setState] = useState({ list: [], available: false })
  const d = useMemo(() => desk(srv, setState), [srv])
  const theme = useTheme()
  // The stream opens once the list has come: it says where each terminal's history ends. A server without terminals
  // (an older one, or the token refused) is not asked again.
  useEffect(() => {
    const stop = new AbortController()
    const { signal } = stop
    ;(async () => {
      for (let e = await d.refresh(); e; e = await d.refresh()) {
        if (signal.aborted || e.status === 403 || e.status === 404) return
        await nap(RETRY_MS, signal)
        if (signal.aborted) return
      }
      if (signal.aborted) return
      d.mark()
      await followTerminals(srv, d.onEvent, { signal, offsets: d.offsets })
    })()
    return () => { stop.abort(); d.dispose() }
  }, [d, srv])
  useEffect(() => { d.restyle() }, [d, theme])
  return { ...state, attach: d.attach, focus: d.focus, close: d.close, refresh: d.refresh }
}

// A terminal with you: a unit's session, or a loose one (the docs update). A unit's that ended with an error keeps its
// screen to read and offers a new session; one closed or forgotten leaves the canvas with the list.
export function PtyNode({ data: { unit, term, now, attach, onClose, onMax, onSession, canStart } }) {
  const slot = useRef(null)
  useEffect(() => attach(term.id, slot.current), [attach, term.id])
  const live = term.ended == null
  const failed = !live && term.code !== 0
  const k = live ? 'running' : failed ? 'blocked' : unit ? tone(unit) : 'done'
  const name = unit?.title ?? t('pty.update')
  return (
    <div className={`dk-term dk-pty tone-${k}`}>
      <Ports />
      <div className="dk-term-head">
        <span className="dk-term-title" title={name}>{name}</span>
        <span className="dk-term-meta">
          <span>{term.agent}</span><span>{live ? t('pty.you') : t('pty.ended', { code: term.code ?? '—' })}</span>
          <span>{fmtDuration(elapsed(term, now))}</span>
        </span>
        {unit && failed ? (
          <button type="button" className="dk-cv-btn" disabled={!canStart} onClick={() => onSession(unit.id, 'new')}>{t('pty.fresh')}</button>
        ) : null}
        <button type="button" className="dk-cv-btn" onClick={() => onClose(term.id)}>{live ? t('pty.close') : t('pty.remove')}</button>
        <button type="button" className="dk-icon" aria-label={t('cv.max')} title={t('cv.max')} onClick={() => onMax(unit?.id ?? term.id)}>⤢</button>
      </div>
      <div ref={slot} className="dk-term-body dk-pty-slot nowheel nodrag nokey nopan" role="group" aria-label={t('pty.label', { name })}
        aria-description={t('pty.leave')} />
    </div>
  )
}

export function LaneNode({ data: { label } }) {
  return <div className="dk-cv-lane eyebrow">{label}</div>
}
