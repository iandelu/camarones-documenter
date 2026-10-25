import { useEffect, useState } from 'react'
import { Aviso, Button, Card, EmptyState, Skeleton } from '@camaron/ui'
import { groups } from '../plan.js'
import { useAgents, useCmd, useStore } from '../hooks.js'
import { AgentPicker, Fold, JobOutput, Page, UnitRow } from '../parts.jsx'
import Commands from './Commands.jsx'
import { lang, t } from '../i18n.js'

// The Plan by task: run the ready units (in parallel, or the autopilot one after another) or stop what runs; then the
// units grouped by what they ask of you, each with the one action that moves it. The graph stays in the portal.
const ASKS = ['awaiting', 'blocked', 'doing', 'ready']

export default function Plan({ srv, jobs }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const a = useAgents(srv)
  const { running } = useStore(jobs)
  const pilot = running.find((j) => j.kind.startsWith('cmd:autopilot'))
  const load = () => srv.get('pipeline').then((d) => { setData(d); setError('') }, (e) => setError(e.message))
  const active = !!pilot || (data?.run && !data.run.finished)
  useEffect(() => {                                   // often while something runs, rarely otherwise
    load()
    const id = setInterval(load, active ? 3000 : 15000)
    return () => clearInterval(id)
  }, [active, running.length])
  if (error) return <Page title={t('nav.plan')}><Aviso tone="error" title={t('plan.failed')} detail={error} /></Page>
  if (!data) return <Page title={t('nav.plan')}><Skeleton lines={6} /></Page>
  if (!data.units.length) return <Page title={t('nav.plan')}><NoPlan srv={srv} jobs={jobs} onDone={load} /></Page>
  const g = groups(data.units)
  const row = (u) => <UnitRow key={u.id} u={u} all={data.units} srv={srv} a={a} onChanged={load} />
  return (
    <Page title={t('nav.plan')}>
      <Run srv={srv} jobs={jobs} run={data.run} pilot={pilot} onChanged={load} ready={g.ready.length} />
      <Update srv={srv} a={a} />
      <div className="row dk-units-head"><span className="muted small">{t('plan.progress', {
        done: g.done.length, total: data.units.filter((u) => u.status !== 'dropped').length })}</span>
        <span className="dk-grow"></span><AgentPicker a={a} /></div>
      {ASKS.map((k) => (g[k].length ? (
        <section key={k} className="dk-group-block">
          <h2 className="eyebrow dk-group">{t('grp.' + k)} ({g[k].length})</h2>
          <ul className="dk-units">{g[k].map(row)}</ul>
        </section>
      ) : null))}
      {g.waiting.length ? <Fold label={`${t('grp.waiting')} (${g.waiting.length})`}><ul className="dk-units">{g.waiting.map(row)}</ul></Fold> : null}
      {g.done.length ? <Fold label={`${t('grp.done')} (${g.done.length})`}><ul className="dk-units">{g.done.map(row)}</ul></Fold> : null}
      <Commands srv={srv} jobs={jobs} section="plan" />
    </Page>
  )
}

// Run the plan: the ready units in parallel (POST runs), or the autopilot (a catalog command, a job of the server);
// while either runs, the way to stop it. The options fold away.
function Run({ srv, jobs, run, pilot, onChanged, ready }) {
  const [opts, setOpts] = useState({ parallel: 2, per_runner: '', max_units: '', include_interviews: false })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pilotCmd = useCmd(srv, jobs)
  const set = (k) => (e) => setOpts((o) => ({ ...o, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))
  const max = opts.max_units === '' ? null : Number(opts.max_units)
  async function act(fn) {
    setBusy(true)
    setError('')
    try { await fn(); jobs.refresh(); onChanged(); setTimeout(onChanged, 1500) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  const live = run && !run.finished
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('plan.run')}</span>
      {pilot ? (
        <div className="row"><span role="status">{t('plan.pilotOn')}</span>
          <Button size="sm" variant="danger" disabled={busy} onClick={() => act(() => srv.post(`app/jobs/${pilot.id}/cancel`, {}))}>{t('plan.pilotStop')}</Button></div>
      ) : live ? (
        <div className="row"><span role="status">{t('plan.running', { done: run.done, units: run.units })}</span>
          <Button size="sm" variant="danger" disabled={busy} onClick={() => act(() => srv.post(`runs/${encodeURIComponent(run.run)}/cancel`, {}))}>{t('plan.cancel')}</Button></div>
      ) : (<>
        <div className="row">
          <label className="dk-inline">{t('plan.atOnce')}
            <select className="cu-input dk-select dk-narrow" value={opts.parallel} disabled={busy} onChange={set('parallel')}>
              {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}</select></label>
          <Button variant="primary" disabled={busy || !ready} onClick={() => act(() => srv.post('runs', {
            parallel: Number(opts.parallel), per_runner: opts.per_runner.trim(), lang: lang(), max_units: max,
            include_interviews: opts.include_interviews }))}>{t('plan.go')}</Button>
          <Button disabled={busy || pilotCmd.running || !ready} onClick={() => act(async () => {
            pilotCmd.run('autopilot', { lang: lang(), include_interviews: opts.include_interviews, ...(max ? { max_units: max } : {}) })
          })}>{t('plan.pilot')}</Button>
        </div>
        <Fold label={t('plan.options')}>
          <div className="dk-fields">
            <div className="cu-field"><label className="cu-field-label" htmlFor="o-runner">{t('plan.perRunner')} <code className="cu-flag">--per-runner</code></label>
              <input id="o-runner" className="cu-input" value={opts.per_runner} placeholder="claude=2,codex=1" onChange={set('per_runner')} /></div>
            <div className="cu-field"><label className="cu-field-label" htmlFor="o-max">{t('plan.maxUnits')} <code className="cu-flag">--max-units</code></label>
              <input id="o-max" className="cu-input" type="number" min="1" value={opts.max_units} onChange={set('max_units')} /></div>
            <label className="dk-check"><input type="checkbox" checked={opts.include_interviews} onChange={set('include_interviews')} />
              {t('plan.interviews')} <code className="cu-flag">--include-interviews</code></label>
          </div>
        </Fold>
      </>)}
      {run && run.finished ? <span className="muted small">{t('plan.last', { done: run.done, failed: run.failed })}</span> : null}
      {error ? <Aviso tone="error" title={t('unit.failed')} detail={error} /> : null}
      {pilotCmd.error || pilotCmd.job?.status === 'failed' ? <JobOutput c={pilotCmd} /> : null}
    </Card>
  )
}

// Keep it current: the docs update (what changed in the code since the docs were written) as a session with the
// agent in its own terminal, like the wizard's "update" (lib/agents.py).
function Update({ srv, a }) {
  const [note, setNote] = useState({ ok: '', error: '' })
  if (a.agents && !a.agents.length) return null
  async function open() {
    setNote({ ok: '', error: '' })
    try {
      await srv.post('app/agent', { unit: 'update', agent: a.agent, lang: lang() })
      setNote({ ok: t('next.opened', { agent: a.label(a.agent) }), error: '' })
    } catch (e) { setNote({ ok: '', error: e.message }) }
  }
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('plan.keep')}</span>
      <div className="row"><span>{t('plan.update')}</span><span className="dk-grow"></span>
        <Button size="sm" disabled={!a.agent} onClick={open}>{t('next.start', { agent: a.label(a.agent) })}</Button></div>
      {note.ok ? <p className="muted small" role="status">{note.ok}</p> : null}
      {note.error ? <Aviso tone="error" title={t('next.failed')} detail={note.error} /> : null}
    </Card>
  )
}

// A project without a plan yet: `plan sync` builds it from the pipeline and the repos.
function NoPlan({ srv, jobs, onDone }) {
  const c = useCmd(srv, jobs)
  return (
    <EmptyState title={t('plan.empty')} action={
      <Button variant="primary" disabled={c.running} onClick={async () => { await c.run('plan', { action: 'sync' }); onDone() }}>{t('plan.create')}</Button>}>
      {t('plan.emptyBody')}<JobOutput c={c} />
    </EmptyState>
  )
}
