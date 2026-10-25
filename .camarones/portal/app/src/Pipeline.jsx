import { Background, Controls, Handle, Position, ReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { AnimatePresence, motion } from 'motion/react'
import { memo, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { getJSON, postJSON, RUNS } from './api.js'
import { t } from './i18n.js'
import { apply, changedRun, COLUMNS, columns, initial, layout } from './board.js'

const LABEL = { todo: 'To do', running: 'Running', blocked: 'Blocked', done: 'Done', dropped: 'Dropped' }

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
        pipeline = pipeline || (await getJSON('pipeline'))
        const run = pipeline.run
        const detail = run && run.finished ? await getJSON(`runs/${run.run}`) : null
        if (stop) return
        if (source) source.close()
        source = null
        shown.current = run
        dispatch({ type: 'load', pipeline, detail })
        if (run && !run.finished) {
          source = new EventSource(`/api/runs/${encodeURIComponent(run.run)}/events`)
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
        const pipeline = await getJSON('pipeline')
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
      <div className="node-meta">{u.awaiting ? 'awaiting approval' : (u.live.runner || u.status)}{u.isolation === 'worktree' ? ' · own copy' : ''}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  )
})
const NODE_TYPES = { unit: UnitNode }

function Graph({ units, onSelect }) {
  const { nodes, edges } = useMemo(() => layout(units), [units])
  return (
    <div className="graph">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={NODE_TYPES} fitView colorMode="system" nodesDraggable={false}
                 nodesConnectable={false} proOptions={{ hideAttribution: true }} onNodeClick={(_, n) => onSelect(n.id)}>
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
          <div className="col-head">{LABEL[c]} <span>{cols[c].length}</span></div>
          {cols[c].map((u) => (
            <motion.button layout="position" key={u.id} className={`unit s-${u.status}`} onClick={() => onSelect(u.id)}
                           transition={{ duration: 0.2 }}>
              <span className="card-id">{u.id}</span>
              <span className="card-meta">{u.awaiting ? 'awaiting approval · ' : ''}{u.live.runner ? `${u.live.runner} · ` : ''}phase {u.phase}</span>
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
  const rows = [['status', unit.status], ['agent', l.runner], ['outcome', l.outcome], ['merge', l.merge],
    ['time', l.seconds != null ? `${l.seconds}s` : null], ['works in', unit.isolation === 'worktree' ? 'its own copy' : 'cam-docs'],
    ['context tokens', l.tokens_in + l.tokens_cache || null], ['output tokens', l.tokens_out || null],
    ['cost', l.cost_usd ? `$${l.cost_usd.toFixed(2)}` : null], ['waits for', (unit.deps || []).join(', ') || null]]
  return (
    <motion.aside className="drawer" initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }}
                  exit={{ x: 40, opacity: 0 }} transition={{ duration: 0.18 }}>
      <button className="close" onClick={onClose} aria-label="Close">×</button>
      <h2>{unit.id}</h2>
      <p className="muted">{unit.title}</p>
      <dl>{rows.filter(([, v]) => v != null && v !== '').map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{String(v)}</dd></div>)}</dl>
      {unit.notes ? <p className="note">{unit.notes}</p> : null}
      {unit.awaiting
        ? <button className="small" onClick={() => act('units/approve')}>Approve — let the next units start</button>
        : unit.status === 'blocked' ? <button className="small" onClick={() => act('units/retry')}>Retry this unit</button> : null}
      {message ? <p className="error" role="alert">{message}</p> : null}
      {RUNS && unit.runner === 'agent' && ['todo', 'doing'].includes(unit.status) ? <a className="button small" href="./desktop/#/plan">{t('pInApp')}</a> : null}
      <h3>Live log</h3>
      <pre className="log">{l.log.length ? l.log.join('\n') : 'Nothing yet in this run.'}</pre>
    </motion.aside>
  )
}

export default function Pipeline({ arg }) {
  const { state, error, reload } = usePipeline()
  const [mode, setMode] = useState('graph')
  const [selected, setSelected] = useState(arg)
  useEffect(() => setSelected(arg), [arg])
  if (error) return <p className="muted">The portal server is not answering ({error}). Start it with <code>camaron up</code>.</p>
  if (!state) return <p className="muted">Loading…</p>
  const run = state.run
  const unit = selected && state.units[selected]
  const counts = columns(state.units)
  return (
    <section className="pipeline view">
      <div className="pipe-head">
        <div>
          <h1>Pipeline</h1>
          <p className="lede">
            {counts.done.length}/{Object.keys(state.units).length} units done
            {run ? ` · last run ${run.run} ${state.finished ? 'finished' : 'running now'}` : ' · no run yet: camaron run'}
          </p>
        </div>
        {RUNS ? <a className="button small" href="./desktop/#/plan">{t('pInApp')}</a> : null}
        <div className="seg" role="tablist">
          {['graph', 'board'].map((m) => (
            <button key={m} role="tab" aria-selected={mode === m} className={mode === m ? 'on' : ''}
                    onClick={() => setMode(m)}>{m === 'graph' ? 'Graph' : 'Board'}</button>
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
