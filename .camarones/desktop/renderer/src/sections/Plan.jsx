import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Chip, EmptyState, PlanCost, Skeleton, uiText } from '@camaron/ui'
import { board, phases, sessionLine, tone, waitsFor } from '../plan.js'
import { arrivedLive, defaultView, runLive } from '../canvas.js'
import { useAgents, useCmd, useStore } from '../hooks.js'
import { AgentPicker, Failed, Fold, JobOutput, Page, UnitActions } from '../parts.jsx'
import Commands from './Commands.jsx'
import { ago } from '../jobs.js'
import { lang, t } from '../i18n.js'

const Canvas = lazy(() => import('./Canvas.jsx'))           // React Flow loads only with this view

// The Plan by task: run the ready units (in parallel, or the autopilot one after another) or stop what runs; then
// every unit coloured by its state (running yellow, done green, ready white, blocked red, awaiting you in the accent),
// as a board by state or lane by phase like the portal, or as the canvas: the graph, where each unit a run works on is
// a live terminal (canvas.js). A unit opens beside the view with the one action that moves it. A unit in progress with
// no terminal window open is paused; an open one says what its agent is doing. With no view picked, the canvas opens
// as soon as a run is on during the visit (already on when the plan arrives, or started from here) and stays until the
// person picks another; a terminal opened by hand on one unit does not count. Under the view, what the plan cost.
const VIEWS = ['board', 'phases', 'canvas']
const TONES = ['ready', 'running', 'paused', 'awaiting', 'blocked', 'waiting', 'done']

export default function Plan({ srv, jobs }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [view, setView] = useState(() => { try { return localStorage.getItem('dk.planView') } catch { return null } })
  const [open, setOpen] = useState(null)
  const [held, setHeld] = useState(null)               // a run was live at some point of this visit: decides the default view
  const a = useAgents(srv)
  const { running } = useStore(jobs)
  const pilot = running.find((j) => j.kind.startsWith('cmd:autopilot'))
  const load = () => srv.get('pipeline', { lang: lang() }).then((d) => { setData(d); setError('') }, (e) => setError(e.message))
  const active = runLive(data?.run, pilot)
  const windows = !!data?.units.some((u) => u.session?.live)
  const arrived = data ? arrivedLive(held, active) : held
  if (arrived !== held) setHeld(arrived)
  const shown = defaultView(view, arrived)
  useEffect(() => {                                   // often while something runs, rarely otherwise
    load()
    const id = setInterval(load, active ? 3000 : windows ? 5000 : 15000)
    return () => clearInterval(id)
  }, [active, windows, running.length])
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
      <div className="row dk-units-head" data-tour="plan-units">
        <b>{t('plan.progress', { done, total: live.length })}</b>
        <progress className="dk-progress dk-grow" value={done} max={live.length || 1} aria-label={t('stat.plan')} />
        <div className="dk-seg" role="tablist" aria-label={t('plan.view')}>
          {VIEWS.map((v) => <button key={v} type="button" role="tab" aria-selected={shown === v} className={shown === v ? 'on' : ''}
            onClick={() => pick(v)}>{t('plan.' + v)}</button>)}
        </div>
        <AgentPicker a={a} />
      </div>
      <div className="row dk-legend" aria-hidden="true">
        {TONES.map((k) => <span key={k} className={`dk-tone tone-${k}`}><i></i>{t('tone.' + k)}</span>)}
      </div>
      <div className={'dk-plan' + (unit ? ' with-detail' : '')}>
        {shown === 'canvas' ? (
          <Suspense fallback={<Skeleton lines={6} />}>
            <Canvas srv={srv} units={data.units} run={data.run} pilot={pilot} onOpen={setOpen} />
          </Suspense>
        ) : shown === 'board' ? (
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
      <div data-tour="plan-cost"><Cost srv={srv} active={active} /></div>
      <Commands srv={srv} jobs={jobs} section="plan" />
      <Reset srv={srv} jobs={jobs} onChanged={load} />
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
  const state = { running: 'warn', done: 'ok', blocked: 'bad', awaiting: 'info', paused: 'info' }[k]
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
      <Session u={u} a={a} />
      {waits.length && k === 'waiting' ? <p className="muted small">{t('unit.waits', { list: waits.join(', ') })}</p> : null}
      <UnitActions u={u} srv={srv} a={a} plan={plan} onChanged={onChanged} />
      <a className="small" href={`../#/pipeline/${encodeURIComponent(u.id)}`}>{t('plan.inPortal')}</a>
    </Card>
  )
}

// The unit's agent session: paused, or open and what its agent did last (lib/sessions.py reads Claude Code's
// transcript; other agents only say it is open).
function Session({ u, a }) {
  const now = Date.now() / 1000
  const l = sessionLine(u, now)
  if (!l) return null
  const when = l.ts ? ago(l.ts, now, t) : ''
  const what = l.tool ? <code>{l.tool}{l.arg ? ' ' + l.arg : ''}</code> : null
  return (
    <div className="dk-session small" role="status">
      {l.key === 'sess.paused' ? <span>{t('sess.paused')}</span> : null}
      {l.key === 'sess.open' ? <span>{t('sess.open', { agent: a.label(u.session.agent) })}</span> : null}
      {l.key === 'sess.waiting' ? <><b>{t('sess.waiting')}</b>{l.text ? <q>{l.text}</q> : null}</> : null}
      {l.key === 'sess.tool' ? <span>{t('sess.tool', { tool: '' })}{what}</span> : null}
      {l.key === 'sess.stuck' ? <span>{t('sess.stuck', { tool: l.tool, ago: when })}</span> : null}
      {when && l.key !== 'sess.stuck' ? <span className="muted">{t('sess.last', { ago: when })}</span> : null}
    </div>
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
    <Card className="dk-run" data-tour="plan-run">
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

// What the plan took from zero (`camaron plan cost`): POST harvests this machine's unit sessions, then answers the
// team's bill. Asked when the section opens and when a run starts or ends, not on every poll of the board.
function Cost({ srv, active }) {
  const [bill, setBill] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => {
    setBusy(true)
    return srv.post('plan/cost', {}).then((b) => { setBill(b); setError('') }, (e) => setError(e.message))
      .finally(() => setBusy(false))
  }
  useEffect(() => { load() }, [active])
  return <CostView bill={bill} error={error} busy={busy} onRefresh={load} onRetry={load} />
}

export function CostView({ bill, error, busy, onRefresh, onRetry }) {
  if (error) return <Failed title={uiText('pc.failed')} detail={error} onRetry={onRetry} />
  return bill ? <PlanCost bill={bill} busy={busy} onRefresh={onRefresh} /> : null
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
    <Card className="dk-run" data-tour="plan-keep">
      <span className="eyebrow">{t('plan.keep')}</span>
      <div className="row"><span>{t('plan.update')}</span><span className="dk-grow"></span>
        <Button size="sm" disabled={!a.agent} onClick={open}>{t('next.start', { agent: a.label(a.agent) })}</Button></div>
      {note.ok ? <p className="muted small" role="status">{note.ok}</p> : null}
      {note.error ? <Aviso tone="error" title={t('next.failed')} detail={note.error} /> : null}
    </Card>
  )
}

// Start the docs again (`docs reset`), previewed first like uninstall: redo reopens every finished unit (nothing is
// deleted), wipe deletes the generated docs (tagged in cam-docs' git first) and starts the plan over; the interviews
// and the pages a person wrote or confirmed stay. A preview counts only for the options it was made with. No jokes here.
const RESET = { redo: { label: 'rs.redo', what: 'rs.redoWhat', go: 'rs.goRedo', ask: 'rs.confirmRedo', text: 'rs.confirmRedoText', done: 'rs.doneRedo' },
  wipe: { label: 'rs.wipe', what: 'rs.wipeWhat', go: 'rs.goWipe', ask: 'rs.confirmWipe', text: 'rs.confirmWipeText', done: 'rs.doneWipe' } }

export function Reset({ srv, jobs, onChanged }) {
  const preview = useCmd(srv, jobs)
  const go = useCmd(srv, jobs)
  const [opts, setOpts] = useState({ mode: 'redo', templates: false })
  const [seen, setSeen] = useState('')
  const dialog = useRef(null)
  const key = JSON.stringify(opts)
  const lines = seen === key && preview.job?.status === 'done' ? preview.job.lines : null
  const steps = (lines || []).filter((l) => l.trim().startsWith('•'))
  const m = RESET[opts.mode]
  const args = (dry) => ({ action: 'reset', mode: opts.mode, ...(opts.templates ? { templates: true } : {}), ...(dry ? { dry_run: true } : {}) })
  const look = () => { setSeen(key); preview.run('docs', args(true)) }
  const run = async () => { dialog.current.close(); await go.run('docs', args(false), true); setSeen(''); onChanged() }
  return (
    <Card className="dk-run dk-cmd careful" data-tour="plan-reset">
      <span className="eyebrow">{t('rs.title')}</span>
      <p className="small">{t('rs.lead')}</p>
      <div className="dk-seg" role="radiogroup" aria-label={t('rs.mode')}>
        {Object.keys(RESET).map((k) => <button key={k} type="button" role="radio" aria-checked={opts.mode === k} className={opts.mode === k ? 'on' : ''}
          disabled={go.running} onClick={() => setOpts((o) => ({ ...o, mode: k }))}>{t(RESET[k].label)}</button>)}
      </div>
      <p className="muted small">{t(m.what)}</p>
      <label className="dk-check"><input type="checkbox" checked={opts.templates} disabled={go.running}
        onChange={(e) => setOpts((o) => ({ ...o, templates: e.target.checked }))} />{t('rs.templates')}</label>
      <div className="row">
        <Button size="sm" disabled={preview.running || go.running} onClick={look}>{t('rs.preview')}</Button>
        {steps.length ? <Button size="sm" variant="danger" disabled={go.running} onClick={() => dialog.current.showModal()}>{t(m.go)}</Button> : null}
      </div>
      {lines && !go.job ? <pre className="dk-log">{lines.join('\n')}</pre> : <JobOutput c={go.job ? go : preview} />}
      {go.job?.status === 'done' ? <p className="small" role="status">{t(m.done)}</p> : null}
      <dialog ref={dialog} className="dk-dialog">
        <h2>{t(m.ask)}</h2>
        <p>{t(m.text)}</p>
        <pre className="dk-log">{steps.join('\n')}</pre>
        <div className="row">
          <Button variant="ghost" onClick={() => dialog.current.close()}>{t('cancel')}</Button>
          <Button variant="danger" onClick={run}>{t(m.go)}</Button>
        </div>
      </dialog>
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
