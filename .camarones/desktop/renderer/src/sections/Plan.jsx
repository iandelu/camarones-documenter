import { useEffect, useState } from 'react'
import { Aviso, Button, Card, Chip, EmptyState, Skeleton } from '@camaron/ui'
import { board, phases, tone, waitsFor } from '../plan.js'
import { useAgents, useCmd, useStore } from '../hooks.js'
import { AgentPicker, Failed, Fold, JobOutput, Page, UnitActions } from '../parts.jsx'
import Commands from './Commands.jsx'
import { lang, t } from '../i18n.js'

// The Plan by task: run the ready units (in parallel, or the autopilot one after another) or stop what runs; then
// every unit coloured by its state (running yellow, done green, ready white, blocked red, awaiting you in the accent),
// as a board by state or lane by phase like the portal. A unit opens beside the board with the one action that moves
// it. The graph with its arrows stays in the portal.
const VIEWS = ['board', 'phases']
const TONES = ['ready', 'running', 'awaiting', 'blocked', 'waiting', 'done']

export default function Plan({ srv, jobs }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [view, setView] = useState(() => { try { return localStorage.getItem('dk.planView') || 'board' } catch { return 'board' } })
  const [open, setOpen] = useState(null)
  const a = useAgents(srv)
  const { running } = useStore(jobs)
  const pilot = running.find((j) => j.kind.startsWith('cmd:autopilot'))
  const load = () => srv.get('pipeline', { lang: lang() }).then((d) => { setData(d); setError('') }, (e) => setError(e.message))
  const active = !!pilot || (data?.run && !data.run.finished)
  useEffect(() => {                                   // often while something runs, rarely otherwise
    load()
    const id = setInterval(load, active ? 3000 : 15000)
    return () => clearInterval(id)
  }, [active, running.length])
  const pick = (v) => { setView(v); try { localStorage.setItem('dk.planView', v) } catch { /* private window: not kept */ } }
  if (error) return <Page title={t('nav.plan')}><Failed title={t('plan.failed')} detail={error} onRetry={() => { setError(''); load() }} /></Page>
  if (!data) return <Page title={t('nav.plan')}><Skeleton lines={6} /></Page>
  if (!data.units.length) return <Page title={t('nav.plan')}><NoPlan srv={srv} jobs={jobs} onDone={load} /></Page>
  const live = data.units.filter((u) => u.status !== 'dropped')
  const done = live.filter((u) => u.status === 'done').length
  const ready = live.filter((u) => tone(u) === 'ready').length
  const unit = open && data.units.find((u) => u.id === open)
  const card = (u) => <UnitCard key={u.id} u={u} on={u.id === open} onOpen={() => setOpen(u.id === open ? null : u.id)} />
  return (
    <Page title={t('nav.plan')} wide>
      <Run srv={srv} jobs={jobs} run={data.run} pilot={pilot} onChanged={load} ready={ready} />
      <Update srv={srv} a={a} />
      <div className="row dk-units-head">
        <b>{t('plan.progress', { done, total: live.length })}</b>
        <progress className="dk-progress dk-grow" value={done} max={live.length || 1} aria-label={t('stat.plan')} />
        <div className="dk-seg" role="tablist" aria-label={t('plan.view')}>
          {VIEWS.map((v) => <button key={v} type="button" role="tab" aria-selected={view === v} className={view === v ? 'on' : ''}
            onClick={() => pick(v)}>{t('plan.' + v)}</button>)}
        </div>
        <AgentPicker a={a} />
      </div>
      <div className="row dk-legend" aria-hidden="true">
        {TONES.map((k) => <span key={k} className={`dk-tone tone-${k}`}><i></i>{t('tone.' + k)}</span>)}
      </div>
      <div className={'dk-plan' + (unit ? ' with-detail' : '')}>
        {view === 'board' ? (
          <div className="dk-board">{board(data.units).map((c) => (
            <section key={c.key} className="dk-col" aria-label={t('col.' + c.key)}>
              <h2 className="eyebrow dk-col-head">{t('col.' + c.key)} <span>{c.units.length}</span></h2>
              {c.units.map(card)}
              {!c.units.length ? <p className="muted small dk-col-empty">{t('col.empty')}</p> : null}
            </section>
          ))}</div>
        ) : (
          <div className="dk-lanes">{phases(data.units).map((p) => (
            <section key={p.phase} className="dk-col" aria-label={t('plan.phase', { n: p.phase })}>
              <h2 className="eyebrow dk-col-head">{t('plan.phase', { n: p.phase })} <span>{p.done}/{p.units.length}</span></h2>
              {p.units.map(card)}
            </section>
          ))}</div>
        )}
        {unit ? <Detail u={unit} all={data.units} srv={srv} a={a} plan={data} onClose={() => setOpen(null)} onChanged={load} /> : null}
      </div>
      <Commands srv={srv} jobs={jobs} section="plan" />
    </Page>
  )
}

// A unit on the board: its colour says its state, a pulse while it runs; it opens the detail.
function UnitCard({ u, on, onOpen }) {
  const k = tone(u)
  return (
    <button type="button" className={`dk-card tone-${k}` + (on ? ' on' : '')} aria-expanded={on} onClick={onOpen} title={u.title}>
      <span className="dk-card-title">{u.title}</span>
      <span className="dk-card-meta"><i></i>{t('tone.' + k)} · <code>{u.id}</code></span>
    </button>
  )
}

// The unit opened: what it is, what it waits for, its notes and the one action that moves it.
function Detail({ u, all, srv, a, plan, onClose, onChanged }) {
  const waits = waitsFor(u, all)
  const k = tone(u)
  const state = { running: 'warn', done: 'ok', blocked: 'bad', awaiting: 'info' }[k]
  return (
    <Card as="aside" className={`dk-detail tone-${k}`} aria-label={u.title}>
      <div className="row"><Chip state={state}>{t('tone.' + k)}</Chip><span className="dk-grow"></span>
        <button type="button" className="dk-icon" aria-label={t('close')} onClick={onClose}>×</button></div>
      <h2 className="dk-detail-title">{u.title}</h2>
      <dl className="dk-pairs">
        <dt>{t('plan.id')}</dt><dd><code>{u.id}</code></dd>
        <dt>{t('plan.phaseOf')}</dt><dd>{u.phase}</dd>
        <dt>{t('plan.by')}</dt><dd>{u.runner === 'agent' ? t('plan.byAgent') : t('plan.byYou')}</dd>
        {u.repo ? <><dt>{t('plan.repo')}</dt><dd>{u.repo}</dd></> : null}
        {(u.deps || []).length ? <><dt>{t('plan.deps')}</dt><dd>{u.deps.map((d) => <code key={d} className={waits.includes(d) ? '' : 'muted'}>{d} </code>)}</dd></> : null}
      </dl>
      {u.notes ? <p className="small dk-detail-notes">{u.notes}</p> : null}
      {waits.length && k === 'waiting' ? <p className="muted small">{t('unit.waits', { list: waits.join(', ') })}</p> : null}
      <UnitActions u={u} srv={srv} a={a} plan={plan} onChanged={onChanged} />
      <a className="small" href={`../#/pipeline/${encodeURIComponent(u.id)}`}>{t('plan.inPortal')}</a>
    </Card>
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
