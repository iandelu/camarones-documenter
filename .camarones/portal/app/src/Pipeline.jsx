import { Background, Controls, Handle, Position, ReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { AnimatePresence, motion } from 'motion/react'
import { memo, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { Aviso, Button, Skeleton } from '@camaron/ui'
import { getJSON, postJSON } from './api.js'
import { lang, t } from './i18n.js'
import { apply, changedRun, column, COLUMNS, columns, initial, layout, pipelinePath } from './board.js'

// A column's name, and a unit's state in words (doing is the running column).
const LABEL = { todo: () => t('pipe.todo'), running: () => t('pipe.running'), blocked: () => t('pipe.blocked'),
  done: () => t('pipe.done'), dropped: () => t('pipe.dropped') }

function reducer(state, action) {
  if (action.type === 'load') return initial(action.pipeline, action.detail)
  return apply(state, action.event)
}

// Loads the plan and the latest run; streams a running one; with no stream open, checks every few seconds for a
// new run (`camaron run` started while the page was open) and connects to it.
function usePipeline() {
  const [state, dispatch] = useReducer(reducer, null)
  const [error, setError] = useState(null)
  const shown = useRef(null)
  const reload = useRef(() => {})
  useEffect(() => {
    let source = null
    let stop = false
    async function load(pipeline) {
      try {
        pipeline = pipeline || (await getJSON(pipelinePath(lang())))
        const run = pipeline.run
        const detail = run && run.finished ? await getJSON(`runs/${run.run}`) : null
        if (stop) return
        if (source) source.close()
        source = null
        shown.current = run
        dispatch({ type: 'load', pipeline, detail })
        setError(null)
        if (run && !run.finished) {
          source = new EventSource(`/api/runs/${encodeURIComponent(run.run)}/events`)
          const es = source
          source.onerror = () => {   // closed for good (a 204: a run stopped from outside, read to its end): back to the poll
            if (es.readyState === EventSource.CLOSED && source === es) source = null
          }
          source.onmessage = (m) => {
            const event = JSON.parse(m.data)
            dispatch({ type: 'event', event })
            if (event.type === 'run.finished') {
              source.close()
              source = null
              shown.current = { ...run, finished: true }
            }
          }
        }
      } catch (e) {
        if (!stop) setError(e.message)
      }
    }
    load()
    reload.current = () => load()
    const timer = setInterval(async () => {
      if (source || stop) return
      try {
        const pipeline = await getJSON(pipelinePath(lang()))
        if (changedRun(shown.current, pipeline.run)) load(pipeline)
      } catch { /* the next tick retries */ }
    }, 5000)
    return () => { stop = true; clearInterval(timer); if (source) source.close() }
  }, [])
  return { state, error, reload: () => reload.current() }
}

const UnitNode = memo(function UnitNode({ data }) {
  const u = data.unit
  return (
    <div className={`node s-${u.status}${u.awaiting ? ' awaiting' : ''}`} title={u.title}>
      <Handle type="target" position={Position.Left} />
      <div className="node-id">{u.id}</div>
      <div className="node-meta">{u.awaiting ? t('pipe.awaiting') : (u.live.runner || LABEL[column(u)]())}{u.isolation === 'worktree' ? ` · ${t('pipe.ownCopy')}` : ''}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
})
const NODE_TYPES = { unit: UnitNode }

function Graph({ units, onSelect }) {
  const { nodes, edges } = useMemo(() => layout(units), [units])
  return (
    // Enter or Space on a focused node opens it like a click: the nodes are ours (no onNodesChange), so React Flow's
    // own keyboard selection never lands.
    <div className="graph" onKeyDown={(e) => {
      const node = e.target.closest?.('.react-flow__node')
      if (node && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onSelect(node.dataset.id) }
    }}>
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} fitView colorMode="system" nodesDraggable={false}
                 nodesConnectable={false} edgesFocusable={false} proOptions={{ hideAttribution: true }}
                 onNodeClick={(_, n) => onSelect(n.id)}>
        <Background gap={24} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}

function Board({ units, onSelect }) {
  const cols = useMemo(() => columns(units), [units])
  return (
    <div className="board">
      {COLUMNS.map((c) => (
        <div key={c} className="col">
          <div className="col-head">{LABEL[c]()} <span>{cols[c].length}</span></div>
          {cols[c].map((u) => (
            <motion.button layout="position" key={u.id} className={`unit s-${u.status}`} onClick={() => onSelect(u.id)}
                           transition={{ duration: 0.2 }}>
              <span className="card-id">{u.id}</span>
              <span className="card-meta">{u.awaiting ? `${t('pipe.awaiting')} · ` : ''}{u.live.runner ? `${u.live.runner} · ` : ''}{t('pipe.phase', { n: u.phase })}</span>
            </motion.button>
          ))}
        </div>
      ))}
    </div>
  )
}

function Drawer({ unit, onClose, onChanged }) {
  const [message, setMessage] = useState(null)
  async function act(path) {
    try { await postJSON(path, { unit: unit.id }); onChanged() } catch (e) { setMessage(e.message) }
  }
  const l = unit.live
  const rows = [[t('pipe.status'), LABEL[column(unit)]()], [t('pipe.agent'), l.runner], [t('pipe.outcome'), l.outcome],
    [t('pipe.merge'), l.merge], [t('pipe.time'), l.seconds != null ? `${l.seconds} s` : null],
    [t('pipe.where'), unit.isolation === 'worktree' ? t('pipe.ownCopyLong') : 'cam-docs'],
    [t('pipe.tokensIn'), l.tokens_in + l.tokens_cache || null], [t('pipe.tokensOut'), l.tokens_out || null],
    [t('pipe.cost'), l.cost_usd ? `$${l.cost_usd.toFixed(2)}` : null], [t('pipe.waits'), (unit.deps || []).join(', ') || null]]
  return (
    <motion.aside className="drawer" initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }}
                  exit={{ x: 40, opacity: 0 }} transition={{ duration: 0.18 }}>
      <button className="close" onClick={onClose} aria-label={t('pipe.close')}>×</button>
      <h2>{unit.id}</h2>
      <p className="muted">{unit.title}</p>
      <dl>{rows.filter(([, v]) => v != null && v !== '').map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{String(v)}</dd></div>)}</dl>
      {unit.notes ? <p className="note">{unit.notes}</p> : null}
      {unit.awaiting
        ? <button className="small" onClick={() => act('units/approve')}>{t('pipe.approve')}</button>
        : unit.status === 'blocked' ? <button className="small" onClick={() => act('units/retry')}>{t('pipe.retry')}</button> : null}
      {message ? <p className="error" role="alert">{message}</p> : null}
      <h3>{t('pipe.log')}</h3>
      <pre className="log">{l.log.length ? l.log.join('\n') : t('pipe.noLog')}</pre>
    </motion.aside>
  )
}

export default function Pipeline({ arg }) {
  const { state, error, reload } = usePipeline()
  const [mode, setMode] = useState('graph')
  const [selected, setSelected] = useState(arg)
  useEffect(() => setSelected(arg), [arg])
  if (error) return (
    <section className="pipeline view">
      <Aviso tone="error" title={t('pipe.down')} detail={error}
        action={<Button size="sm" onClick={reload}>{t('retry')}</Button>}>{t('pipe.downHow')}</Aviso>
    </section>
  )
  if (!state) return <section className="pipeline view"><Skeleton lines={5} /></section>
  const run = state.run
  const unit = selected && state.units[selected]
  const counts = columns(state.units)
  return (
    <section className="pipeline view">
      <div className="pipe-head">
        <div>
          <h1>{t('pipe.title')}</h1>
          <p className="lede">
            {t('pipe.count', { done: counts.done.length, total: Object.keys(state.units).length })}
            {' · '}{run ? t(state.finished ? 'pipe.runDone' : 'pipe.runNow', { run: run.run }) : t('pipe.noRun')}
          </p>
        </div>
        <div className="seg" role="tablist">
          {['graph', 'board'].map((m) => (
            <button key={m} role="tab" aria-selected={mode === m} className={mode === m ? 'on' : ''}
                    onClick={() => setMode(m)}>{t(m === 'graph' ? 'pipe.graph' : 'pipe.board')}</button>
          ))}
        </div>
      </div>
      {mode === 'graph' ? <Graph units={state.units} onSelect={setSelected} /> : <Board units={state.units} onSelect={setSelected} />}
      <AnimatePresence>
        {unit ? <Drawer key={unit.id} unit={unit} onClose={() => setSelected(null)} onChanged={reload} /> : null}
      </AnimatePresence>
    </section>
  )
}
