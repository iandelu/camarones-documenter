import { useState } from 'react'
import { Aviso, Button, Chip, Thinking } from '@camaron/ui'
import { shape } from '@camaron/ui/result.js'
import { chip, state } from './jobs.js'
import { useCmd } from './hooks.js'
import { unitAction, waitsFor } from './plan.js'
import { lang, t } from './i18n.js'

// The pieces the sections share: the page, the agent picker, a fold, a job's outcome and a plan unit's row.

// `wide` widens the page; `full` takes the whole window, however wide, and its height (the Board's columns).
export const Page = ({ title, children, wide = false, full = false }) => (
  <div className={'dk-page' + (wide ? ' wide' : '') + (full ? ' full' : '')}><h1 className="t-impact">{title}</h1>{children}</div>
)

// A read that failed: what, the server's own message, and a way out.
export const Failed = ({ title, detail, onRetry }) => (
  <Aviso tone="error" title={title} detail={detail}
    action={onRetry ? <Button size="sm" onClick={onRetry}>{t('retry')}</Button> : null} />
)

export function AgentPicker({ a }) {
  if (!a.agents || a.agents.length < 2) return null
  return (
    <select className="cu-input dk-select" aria-label={t('next.agent')} value={a.agent} onChange={(e) => a.setAgent(e.target.value)}>
      {a.agents.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
    </select>
  )
}

export function Fold({ label, children, open = false }) {
  return (
    <details className="dk-fold" open={open}>
      <summary>{label}</summary>
      <div className="dk-fold-body">{children}</div>
    </details>
  )
}

// A job's state as a chip; while it runs the word shimmers (Thinking), so a long job reads as at work, not stuck.
export function JobChip({ job }) {
  const word = t('job.' + state(job))
  return <Chip state={chip(job)}>{state(job) === 'running' ? <Thinking>{word}</Thinking> : word}</Chip>
}

// A command's outcome under its panel: the state, the error, and the output folded (open by itself when it failed).
export function JobOutput({ c }) {
  if (!c.job && !c.error) return null
  const failed = c.job && c.job.status === 'failed' && !c.job.stopped
  return (
    <div className="dk-out">
      {c.job ? <JobChip job={c.job} /> : null}
      {c.error ? <Aviso tone="error" title={t('unit.failed')} detail={c.error} /> : null}
      {c.job?.lines.length ? (
        <details open={failed}>
          <summary className="muted small">{t('cmds.output')}</summary>
          <pre className="dk-log">{c.job.lines.join('\n')}</pre>
        </details>
      ) : null}
    </div>
  )
}

// A command's --json result in one generic view (ui/result.js): rows as a table, an object as pairs, else text.
const cell = (v) => (v === true ? t('yes') : v === false ? t('no') : v == null || v === '' ? '—' : String(v))
export function ResultView({ result }) {
  const s = shape(result)
  if (s.kind === 'empty') return <p className="muted small">{t('nothing')}</p>
  if (s.kind === 'text') return <pre className="dk-log">{s.text}</pre>
  if (s.kind === 'pairs') return (
    <table className="dk-table"><tbody>{s.rows.map(([k, v]) => <tr key={k}><th>{k}</th><td>{cell(v)}</td></tr>)}</tbody></table>
  )
  return (
    <div className="dk-scroll"><table className="dk-table">
      <thead><tr>{s.cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>{s.rows.map((r, i) => <tr key={i}>{r.map((v, k) => <td key={k}>{cell(v)}</td>)}</tr>)}</tbody>
    </table></div>
  )
}

// How the interviews run, chosen once per project (`interview mode`): the agent refuses an interview unit until then.
// Each option says what it means; `compact` is the plan row's version, two buttons.
export function ModeChoice({ srv, jobs, onChosen, compact = false }) {
  const c = useCmd(srv, jobs)
  const pick = async (mode) => { const end = await c.run('interview', { action: 'mode', args: [mode] }); if (end?.status === 'done') onChosen?.(mode) }
  if (compact) return (<>
    <Button size="sm" variant="primary" disabled={c.running} onClick={() => pick('team')}>{t('iv.team')}</Button>
    <Button size="sm" disabled={c.running} onClick={() => pick('live')}>{t('iv.live')}</Button>
    {c.error || c.job?.status === 'failed' ? <JobOutput c={c} /> : null}
  </>)
  return (
    <div className="dk-modes">
      {['team', 'live'].map((m) => (
        <button key={m} type="button" className="dk-mode" disabled={c.running} onClick={() => pick(m)}>
          <b>{t(m === 'team' ? 'iv.team' : 'iv.live')}</b>
          <span className="muted small">{t(m === 'team' ? 'iv.teamWhat' : 'iv.liveWhat')}</span>
        </button>
      ))}
      {c.error || c.job?.status === 'failed' ? <JobOutput c={c} /> : null}
    </div>
  )
}

// The one action that moves a plan unit (plan.js): approve, retry, continue or start with the agent picked, choose
// how interviews run first, or go where a unit the wizard runs is done. A half-done one can also start over.
// plan: {interviews} from the pipeline; onChanged: look again.
export function UnitActions({ u, srv, a, plan, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState({ ok: '', error: '' })
  const act = unitAction(u, plan)
  const redo = useCmd(srv)
  async function go(fn, ok = '') {
    setBusy(true)
    setNote({ ok: '', error: '' })
    try { await fn(); setNote({ ok, error: '' }); onChanged?.() } catch (e) { setNote({ ok: '', error: e.message }) } finally { setBusy(false) }
  }
  const agent = (mode) => go(() => srv.post('app/agent', { unit: u.id, agent: a.agent, lang: lang(), mode }),
    t('next.opened', { agent: a.label(a.agent) }))
  const noAgent = act?.kind === 'agent' && a.agents && !a.agents.length
  const reopen = () => go(async () => {
    const end = await redo.run('plan', { action: 'redo', unit: u.id })
    if (end?.status !== 'done') throw new Error(end?.lines?.at(-1) || t('unit.failed'))
  }, t('unit.redone'))
  return (<>
    <div className="row dk-unit-acts">
      {act?.kind === 'approve' ? <Button size="sm" variant="primary" disabled={busy} onClick={() => go(() => srv.post('units/approve', { unit: u.id }))}>{t(act.label)}</Button> : null}
      {act?.kind === 'retry' ? <Button size="sm" disabled={busy} onClick={() => go(() => srv.post('units/retry', { unit: u.id }))}>{t(act.label)}</Button> : null}
      {act?.kind === 'link' ? <Button size="sm" href={act.href}>{t(act.label)}</Button> : null}
      {act?.kind === 'redo' ? <Button size="sm" variant="ghost" disabled={busy} onClick={reopen}>{t(act.label)}</Button> : null}
      {act?.kind === 'mode' ? <><span className="muted small">{t('iv.choose')}:</span><ModeChoice srv={srv} compact onChosen={onChanged} /></> : null}
      {act?.kind === 'agent' && !noAgent ? (<>
        <Button size="sm" variant={act.mode === 'continue' ? 'primary' : 'secondary'} disabled={busy || !a.agent}
          onClick={() => agent(act.mode)}>{t(act.label, { agent: a.label(a.agent) })}</Button>
        {act.mode === 'continue' ? <Button size="sm" variant="ghost" disabled={busy || !a.agent} onClick={() => agent('restart')}>{t('unit.restart')}</Button> : null}
      </>) : null}
      {noAgent ? <Button size="sm" href="#/machine">{t('next.machine')}</Button> : null}
      {act?.kind === 'live' ? <span className="muted small">{t('sess.openShort')}</span> : null}
    </div>
    {note.ok ? <p className="muted small dk-unit-note" role="status">{note.ok}</p> : null}
    {note.error ? <div className="dk-unit-note"><Aviso tone="error" title={t('unit.failed')} detail={note.error} /></div> : null}
  </>)
}

// A plan unit as a list row: its title, what it waits for, and its action.
export function UnitRow({ u, all, srv, a, plan, onChanged }) {
  const waits = u.status === 'todo' && !u.ready ? waitsFor(u, all) : []
  return (
    <li className="dk-unit">
      <div className="dk-unit-main">
        <b>{u.title}</b>
        <span className="muted small"><code>{u.id}</code>{waits.length ? <> · {t('unit.waits', { list: waits.join(', ') })}</> : null}</span>
      </div>
      <UnitActions u={u} srv={srv} a={a} plan={plan} onChanged={onChanged} />
    </li>
  )
}
