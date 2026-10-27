import { useId, useRef, useState } from 'react'
import { core } from '../core.js'
import { addDep, addTask, dropDep, editTask, mergeTasks, removeTask, taskNames } from '../stories.js'
import TouchPicker from './TouchPicker.jsx'
import { Suggest } from './Suggest.jsx'

// Step 3, Subtareas propuestas: one row per task with its files, what it waits for (✕ drops a dependency, + adds one),
// what it collides with on the board and its wave. Every change marks the task edited, and the waves are worked out
// again by analyze. Enter on a title moves to the next one.
const t = core.t
const plural = (key, n) => t(`${key}.${n === 1 ? 'one' : 'many'}`, { n })
const short = (s, n = 40) => (s.length > n ? `${s.slice(0, n - 1)}…` : s)

function Row({ task, n, tasks, unknown, change, onEnter }) {
  const others = tasks.filter((x) => x.key !== task.key)
  const name = (dep) => { const o = tasks.find((x) => x.key === dep); return o ? short(o.title || o.key) : dep }
  const set = (fn) => change((d) => ({ ...d, tasks: fn(d.tasks) }))
  const title = task.title || task.key
  return (
    <li className={`st-task${task.checked === false ? ' off' : ''}`}>
      <input type="checkbox" checked={task.checked !== false} aria-label={t('stories.task.include', { title })}
             onChange={(e) => set((ts) => ts.map((x) => (x.key === task.key ? { ...x, checked: e.target.checked } : x)))} />
      <div className="st-task-body">
        <div className="st-task-top">
          <input className="st-task-title" data-task-title value={task.title} maxLength={120} aria-label={t('stories.task.title', { n })}
                 onChange={(e) => set((ts) => editTask(ts, task.key, { title: e.target.value }))}
                 onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); onEnter(e.currentTarget) } }} />
          {task.wave >= 0 ? <span className="st-wave">{t('stories.wave', { n: task.wave + 1 })}</span> : null}
          {task.edited ? <span className="muted small">{t('stories.task.edited')}</span> : null}
          <button type="button" className="icon" aria-label={t('stories.task.remove', { title })}
                  onClick={() => change((d) => removeTask(d, task.key))}>✕</button>
        </div>
        <div className="st-task-meta">
          {task.group ? <span className="st-group">{task.group}</span> : null}
          {task.touches.length ? (
            <details className="st-files"><summary>{plural('stories.task.files', task.touches.length)}</summary>
              <ul>{task.touches.map((f) => <li key={f}><code>{f}</code></li>)}</ul></details>
          ) : <span className="st-warn small">{t('stories.task.nofiles')}</span>}
        </div>
        <div className="st-task-meta">
          <span className="muted small">{t('stories.task.deps')}</span>
          {(task.deps || []).map((d) => (
            <span key={d} className="st-chip dep" title={name(d)}><span className="st-dep-name">{name(d)}</span>
              <button type="button" className="icon" aria-label={t('stories.task.depRemove', { dep: name(d) })}
                      onClick={() => set((ts) => dropDep(ts, task.key, d))}>✕</button></span>
          ))}
          {others.some((o) => !(task.deps || []).includes(o.key)) ? (
            <select className="st-add-dep" value="" aria-label={t('stories.task.depAdd', { title })}
                    onChange={(e) => set((ts) => addDep(ts, task.key, e.target.value))}>
              <option value="">+</option>
              {others.filter((o) => !(task.deps || []).includes(o.key)).map((o) => <option key={o.key} value={o.key}>{short(o.title || o.key)}</option>)}
            </select>
          ) : null}
          {(task.conflicts || []).length ? <span className="muted small">{t('stories.task.clash')}</span> : null}
          {(task.conflicts || []).map((c) => (
            <span key={`${c.id}:${c.kind}`} className={`st-clash k-${c.kind}`} title={(c.files || []).join(', ') || t('stories.kind.near')}>{c.id}</span>
          ))}
          {others.length ? (
            <select className="st-merge" value="" aria-label={t('stories.task.merge', { title })}
                    onChange={(e) => change((d) => mergeTasks(d, task.key, e.target.value))}>
              <option value="">{t('stories.task.mergePick')}</option>
              {others.map((o) => <option key={o.key} value={o.key}>{short(o.title || o.key)}</option>)}
            </select>
          ) : null}
        </div>
        {task.outside?.length ? <p className="st-warn small">{t('stories.task.outside', { files: task.outside.join(', ') })}</p> : null}
        {unknown?.length ? <p className="st-warn small">{t('stories.task.unknown', { refs: unknown.join(', ') })}</p> : null}
      </div>
    </li>
  )
}

function AddTask({ change, groups, onDone }) {
  const id = useId()
  const [title, setTitle] = useState('')
  const [touches, setTouches] = useState([])
  const [more, setMore] = useState({})
  const ok = () => {
    if (!title.trim()) return
    change((d) => ({ ...d, tasks: addTask(d.tasks, title, touches), groups: { ...d.groups, ...more } }))
    onDone()
  }
  return (
    <div className="st-addtask">
      <label htmlFor={`${id}-t`}>{t('stories.add.title')}</label>
      <input id={`${id}-t`} autoFocus value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)}
             onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); ok() } if (e.key === 'Escape') onDone() }} />
      <TouchPicker touches={touches} groups={{ ...groups, ...more }} label={t('stories.touches')}
                   onChange={(next, g) => { setTouches(next); setMore((m) => ({ ...m, ...g })) }} />
      {!touches.length ? <p className="st-warn small">{t('stories.task.nofiles')}</p> : null}
      <div className="row">
        <button type="button" disabled={!title.trim()} onClick={ok}>{t('stories.add.ok')}</button>
        <button type="button" className="ghost" onClick={onDone}>{t('stories.cancel')}</button>
      </div>
    </div>
  )
}

export default function TasksStep({ draft, change, analysis, existing, ai, aiOn }) {
  const id = useId()
  const list = useRef(null)
  const [adding, setAdding] = useState(false)
  const tasks = draft.tasks || []
  const next = (el) => {
    const all = [...(list.current?.querySelectorAll('[data-task-title]') || [])]
    all[all.indexOf(el) + 1]?.focus()
  }
  const why = analysis?.cycle?.length ? t('stories.block.cycle', { keys: taskNames(analysis.cycle, tasks).join(' → ') })
    : analysis?.duplicates?.length ? t('stories.block.duplicates', { keys: analysis.duplicates.join(', ') }) : ''
  return (
    <section className="st-step" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}><span className="st-n">3</span> {t('stories.step.3')}</h2>
      {why ? <p className="aviso st-cycle" role="alert">{why}</p> : null}
      {tasks.length ? (
        <ol ref={list} className="st-tasks">
          {tasks.map((task, i) => (
            <Row key={task.key} task={task} n={i + 1} tasks={tasks} unknown={analysis?.unknown_deps?.[task.key]} change={change} onEnter={next} />
          ))}
        </ol>
      ) : <p className="muted">{t('stories.tasks.none')}</p>}
      {adding ? <AddTask change={change} groups={draft.groups} onDone={() => setAdding(false)} />
        : <button type="button" className="ghost small" onClick={() => setAdding(true)}>+ {t('stories.add')}</button>}
      <Suggest ai={ai} what="tasks" on={aiOn} onAccept={(x) => change((d) => ({ ...d, tasks: addTask(d.tasks, x.title, x.touches || []) }))} />
      {existing.length ? (
        <>
          <h3>{t('stories.tasks.existing')}</h3>
          <ul className="st-existing">
            {existing.map((s) => (
              <li key={s.id}><a href={`#/kanban/${s.id}`}><span className="card-id">{s.id}</span> {s.title}</a>
                <span className="muted small"> · {s.status}</span>
                {s.wave >= 0 ? <span className="st-wave">{t('stories.wave', { n: s.wave + 1 })}</span> : null}</li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  )
}
