import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Chip, HealthBoard, Skeleton, sonarConnectHash } from '@camaron/ui'
import { severities } from '@camaron/ui/result.js'
import { ago } from '../jobs.js'
import { openedWith } from '../plan.js'
import { BOARD_ACTIONS, doctorRows, seconds } from '../quality.js'
import { useAgents, useCmd, useJob, useStore } from '../hooks.js'
import { AgentPicker, Failed, Fold, JobOutput, Page, ResultView, UnitRow } from '../parts.jsx'
import Commands from './Commands.jsx'
import { SEV, sevWord } from './Libs.jsx'
import { lang, t } from '../i18n.js'

// Quality is the project's health board (ui/src/health.jsx) on the snapshot of `camaron health`: machine, docs and code
// in one view. The board draws the figures and the rows; each row this app owns opens on the control that used to be a
// card of its own (BOARD_ACTIONS), and the rest of the commands stay folded below. KPIs are the portal's.
const CARDS = { doctor: Doctor, drift: Drift, fresh: Fresh, evals: Evals, context: Context, blocks: Blocks, ab: Ab, libs: Libs }
const LINKS = { review: '../#/review' }
const repoHref = (r) => '../#/health/' + encodeURIComponent(r)

export default function Quality({ srv, jobs }) {
  const [user, setUser] = useState('')
  useEffect(() => { srv.get('app/info').then((i) => setUser(i.user), () => {}) }, [])
  const [snap, setSnap] = useState(undefined)             // undefined: not read yet; null: never built
  const [error, setError] = useState('')
  const build = useCmd(srv, jobs, { quiet: true })
  const busy = useRef(false)                              // one refresh at a time; one asked meanwhile runs after it
  const again = useRef(false)
  const load = () => srv.get('health').then((d) => { setSnap(d.snapshot); setError(''); return d.snapshot }, (e) => { setError(e.message) })
  const refresh = async () => {
    if (busy.current) { again.current = true; return }
    busy.current = true
    try { await build.run('health', { refresh: true }); await load() } finally { busy.current = false }
    if (again.current) { again.current = false; refresh() }
  }
  useEffect(() => { load().then((s) => { if (s === null) refresh() }) }, [])
  // The snapshot goes stale when a job ends (a repair, a scan, a confirmation…): build it again. Quiet jobs are not in
  // `running`, so the refresh itself does not come back here.
  const { running } = useStore(jobs)
  const was = useRef(running.length)
  useEffect(() => {
    if (running.length < was.current) refresh()
    was.current = running.length
  }, [running.length])

  const p = { srv, jobs, user }
  const actions = Object.fromEntries(BOARD_ACTIONS.map((id) => {
    const Body = CARDS[id]
    return [id, () => <Body {...p} />]
  }))
  const loading = !error && (snap === undefined || (snap === null && build.running))      // the first read, or the first build
  return (
    <Page title={t('nav.quality')}>
      {error ? <Failed title={t('q.healthFailed')} detail={error} onRetry={() => { setError(''); load().then((s) => { if (s === null) refresh() }) }} /> : null}
      {snap === undefined || loading ? (loading ? <Skeleton lines={6} /> : null) : (
        <HealthBoard snapshot={snap} actions={actions} links={LINKS} repoHref={repoHref} connectHref={sonarConnectHash} onRefresh={refresh} refreshing={build.running} />
      )}
      {snap === null && !build.running ? <JobOutput c={build} /> : null}
      <div className="row"><Button size="sm" variant="ghost" href="../#/kpis">{t('q.kpis')}</Button></div>
      <Commands srv={srv} jobs={jobs} section="quality" />
    </Page>
  )
}

const now = () => Date.now() / 1000

// What the kit wrote on this machine that is no longer as it left it: put it back (repair). The Doctor row shows which.
function Drift({ srv, jobs }) {
  const c = useCmd(srv, jobs)
  return (
    <div className="dk-body">
      <div className="row"><Button size="sm" disabled={c.running} onClick={() => c.run('repair', {})}>{t('q.repairNow')}</Button></div>
      <JobOutput c={c} />
    </div>
  )
}

// The doctor, kept (lib/doctor.check): shown at once, checked again on request — and once by itself, the first time
// there is nothing kept. What is missing comes first, each with the command that fixes it.
function Doctor({ srv, jobs }) {
  const [rec, setRec] = useState(undefined)         // undefined: loading; null: never checked here
  const check = useJob(srv, jobs, () => srv.post('app/doctor', {}))
  const fix = useCmd(srv, jobs)
  const load = () => srv.get('app/doctor').then((d) => { setRec(d.checked); return d.checked }, () => setRec(null))
  const again = async () => { await check.run(); load() }
  useEffect(() => { load().then((c) => { if (c === null) again() }) }, [])
  const r = rec?.result
  const { missing, optional, fine } = doctorRows(r)
  const busy = check.running || fix.running
  const run = async (f) => { await fix.run(f.cmd, f.args); again() }
  const at = seconds(rec?.at)
  return (
    <div className="dk-body dk-run">
      <div className="row"><span className="dk-grow"></span>
        {at ? <span className="muted small">{t('q.checked', { when: ago(at, now(), t) })}</span> : null}
        <Button size="sm" variant="ghost" disabled={busy} onClick={again}>{t('q.again')}</Button></div>
      {!r ? (check.running || rec === undefined ? <Skeleton lines={3} /> : null) : missing.length ? (
        <ul className="dk-units">{missing.map((x) => (
          <li key={x.kind + x.name} className="dk-unit">
            <div className="dk-unit-main"><b>{x.name}</b>
              <span className="muted small">{x.kind !== 'tool' ? x.hint || x.note || ''
                : x.found ? t('q.pinned', { found: x.found, pinned: x.pinned }) : t('q.absent', { pinned: x.pinned })}</span></div>
            <div className="row dk-unit-acts"><Chip state="bad">{t('q.missing')}</Chip>
              {x.fix ? <Button size="sm" disabled={busy} onClick={() => run(x.fix)}>{x.fix.cmd === 'setup' ? t('q.prepare') : t('q.install')}</Button> : null}</div>
          </li>))}</ul>
      ) : <p className="small">{t('q.allGood')}</p>}
      {r?.drift.length ? (
        <Aviso tone="warn" title={t('q.drift', { n: r.drift.length })}>
          <span className="row"><span className="muted small">{r.drift.map((d) => d.path).join(', ')}</span>
            <Button size="sm" disabled={busy} onClick={() => run(r.fix_drift)}>{t('q.repair')}</Button></span>
        </Aviso>
      ) : null}
      {r && (optional.length || fine.length) ? (
        <Fold label={t('q.all', { n: optional.length + fine.length })}>
          <table className="dk-table"><tbody>{[...optional, ...fine].map((x) => (
            <tr key={x.kind + x.name}><th>{x.name}</th><td>{x.found || '—'}{x.pinned ? <span className="muted small"> · {t('q.pinnedTo', { v: x.pinned })}</span> : null}</td>
              <td>{x.ok ? <Chip state="ok">{t('q.ok')}</Chip> : <Chip state="warn">{t('q.optional')}</Chip>}</td></tr>))}</tbody></table>
        </Fold>
      ) : null}
      {fix.job || fix.error ? <JobOutput c={fix} /> : check.error || check.job?.status === 'failed' ? <JobOutput c={check} /> : null}
    </div>
  )
}

// What an agent session reads before the first page (doctor --context): the total against the budget, the items folded.
function Context({ srv, jobs }) {
  const c = useCmd(srv, jobs, { quiet: true })
  useEffect(() => { c.run('doctor', { context: true, json: true }) }, [])
  const r = c.job?.result
  return (
    <div className="dk-body dk-run">
      {r ? (<>
        <div className="row"><b>{t('q.tokens', { n: r.total, budget: r.budget })}</b>
          <Chip state={r.over ? 'bad' : 'ok'}>{r.over ? t('q.over') : t('q.under')}</Chip>
          {r.on_use ? <span className="muted small">{t('q.onUse', { n: r.on_use })}</span> : null}</div>
        <Fold label={t('q.items', { n: r.items.length })}>
          <table className="dk-table"><tbody>{r.items.map((x) => (
            <tr key={x.path}><th>{x.kind}</th><td><code>{x.path}</code></td><td>{x.tokens}</td>
              <td className="muted small">{x.kit ? t('q.kit') : t('q.project')}</td></tr>))}</tbody></table>
        </Fold>
      </>) : <JobOutput c={c} />}
    </div>
  )
}

// Golden questions (eval): confirm the right ones, ask the confirmed, or propose more: `eval draft` adds the unit
// eval-questions to the plan and the agent picked opens on it at once; while that unit is open, its row says how it goes.
const DRAFT = 'eval-questions'
function Evals({ srv, jobs, user }) {
  const list = useCmd(srv, jobs, { quiet: true })
  const act = useCmd(srv, jobs)
  const a = useAgents(srv)
  const [plan, setPlan] = useState(null)
  const [note, setNote] = useState({ ok: '', error: '' })
  const loadPlan = () => srv.get('pipeline', { lang: lang() }).then(setPlan, () => {})
  const load = () => { list.run('eval', { action: 'list', json: true }); loadPlan() }
  useEffect(() => { load() }, [])
  const qs = list.job?.result || []
  const run = async (args) => { await act.run('eval', args); load() }
  const confirmed = qs.filter((q) => q['x-confirmed']).length
  const unit = plan?.units.find((u) => u.id === DRAFT && ['todo', 'doing', 'blocked'].includes(u.status))
  async function propose() {
    setNote({ ok: '', error: '' })
    const end = await act.run('eval', { action: 'draft' })
    if (end?.status !== 'done') return
    try {
      const res = await srv.post('app/agent', { unit: DRAFT, agent: a.agent, lang: lang(), mode: 'new' })
      setNote({ ok: t('q.proposing', { agent: openedWith(a.label(a.agent), res) }), error: '' })
    } catch (e) { setNote({ ok: '', error: e.message }) }
    loadPlan()
  }
  const noAgent = a.agents && !a.agents.length
  return (
    <div className="dk-body dk-run">
      <div className="row"><span className="cu-chip cu-chip--info">{t('cmds.ai')}</span></div>
      <p className="muted small">{t('q.evalsWhat')}</p>
      {list.job?.result ? (qs.length ? (
        <ul className="dk-units">{qs.map((q) => (
          <li key={q.id} className="dk-unit"><div className="dk-unit-main"><b>{q.q}</b><span className="muted small"><code>{q.id}</code></span></div>
            <div className="row dk-unit-acts">{q['x-confirmed'] ? <Chip state="ok">{t('q.confirmed')}</Chip>
              : <Button size="sm" disabled={act.running || !user} onClick={() => run({ action: 'confirm', ids: [q.id], by: user })}>{t('q.confirm')}</Button>}</div>
          </li>))}</ul>
      ) : <p className="muted small">{t('q.noEvals')}</p>) : <JobOutput c={list} />}
      {unit ? <ul className="dk-units"><UnitRow u={unit} all={plan.units} srv={srv} a={a} plan={plan} onChanged={load} /></ul> : null}
      <div className="row">
        {confirmed ? <Button size="sm" variant="primary" disabled={act.running} onClick={() => run({ action: 'run', json: true })}>{t('q.ask', { n: confirmed })}</Button> : null}
        {!unit && noAgent ? <Button size="sm" href="#/machine">{t('next.machine')}</Button> : null}
        {!unit && !noAgent ? (<>
          <Button size="sm" variant={confirmed ? 'ghost' : 'primary'} disabled={act.running || !a.agent} onClick={propose}>{t('q.propose', { agent: a.label(a.agent) })}</Button>
          <AgentPicker a={a} />
        </>) : null}
      </div>
      {note.ok ? <p className="muted small" role="status">{note.ok}</p> : null}
      {note.error ? <Aviso tone="error" title={t('next.failed')} detail={note.error} /> : null}
      <JobOutput c={act} />
      {act.job?.result ? <ResultView result={act.job.result} /> : null}
    </div>
  )
}

// The same question with and without cam-docs (ab --qa), side by side.
function Ab({ srv, jobs }) {
  const c = useCmd(srv, jobs)
  const [q, setQ] = useState('')
  const clean = q.trim()
  return (
    <div className="dk-body dk-run">
      <div className="row"><span className="cu-chip cu-chip--info">{t('cmds.ai')}</span></div>
      <div className="row">
        <input className="cu-input dk-grow" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('q.abAsk')} aria-label={t('q.abAsk')} />
        {c.running ? <Button size="sm" variant="danger" onClick={c.stop}>{t('job.stop')}</Button>
          : <Button size="sm" disabled={!clean || clean.startsWith('-')} onClick={() => c.run('ab', { qa: clean, json: true })}>{t('q.compare')}</Button>}
      </div>
      <JobOutput c={c} />
      {c.job?.result ? <ResultView result={c.job.result} /> : null}
    </div>
  )
}

// The libraries row of the board: the count and the worst findings, and the way to the Libraries section, where each
// one opens on why it is there, its advisories and an update.
function Libs({ srv }) {
  const [inv, setInv] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { srv.get('inventory').then(setInv, (e) => setError(e.message)) }, [])
  const rows = inv?.libraries || []
  const sev = severities(rows)
  return (
    <div className="dk-body dk-run">
      {error ? <Failed title={t('q.cvFailed')} detail={error} /> : null}
      {inv ? (
        <div className="row">
          <b>{t('q.libsCount', { n: new Set(rows.map((r) => r.ecosystem + r.name)).size })}</b>
          {inv.vulns ? (sev.length ? sev.map(([s, n]) => <Chip key={s} state={SEV[s]}>{n} {sevWord(s)}</Chip>) : <Chip state="ok">{t('q.cvClean')}</Chip>)
            : <span className="muted small">{t('q.cvNever')}</span>}
          <span className="dk-grow"></span>
          <Button size="sm" variant="primary" href="#/libs">{t('q.libsOpen')}</Button>
        </div>
      ) : !error ? <Skeleton lines={1} /> : null}
    </div>
  )
}

// Pages whose cited code changed (suspect) or is gone (stale): "still holds", or a unit that refreshes them.
function Fresh({ srv, jobs, user }) {
  const list = useCmd(srv, jobs, { quiet: true })
  const act = useCmd(srv, jobs)
  const load = () => list.run('fresh', { json: true })
  useEffect(() => { load() }, [])
  const rows = (list.job?.result || []).filter((p) => p.state === 'suspect' || p.state === 'stale')
  const run = async (args) => { await act.run('fresh', args); load() }
  return (
    <div className="dk-body dk-run">
      {list.job?.result ? (rows.length ? (<>
        <ul className="dk-units">{rows.map((p) => (
          <li key={p.path} className="dk-unit">
            <div className="dk-unit-main"><a href={`../#/docs/${p.path}`}><b>{p.path}</b></a>
              <span className="muted small"><code>{[...p.changed, ...p.missing].slice(0, 3).join(', ')}</code></span></div>
            <div className="row dk-unit-acts"><Chip state={p.state === 'stale' ? 'bad' : 'warn'}>{t(`fr.${p.state}`)}</Chip>
              {p.state === 'suspect' ? <Button size="sm" variant="ghost" disabled={act.running || !user} onClick={() => run({ ack: [p.path], by: user })}>{t('q.ack')}</Button> : null}</div>
          </li>))}</ul>
        <div className="row"><Button size="sm" disabled={act.running} onClick={() => run({ plan: true })}>{t('q.freshPlan')}</Button></div>
      </>) : <p className="small">{t('q.allFresh')}</p>) : <JobOutput c={list} />}
      <JobOutput c={act} />
    </div>
  )
}

// The facts read from the code without AI in every generated block (blocks).
function Blocks({ srv, jobs }) {
  const c = useCmd(srv, jobs)
  const r = c.job?.result
  return (
    <div className="dk-body dk-run">
      <div className="row">
        <Button size="sm" disabled={c.running} onClick={() => c.run('blocks', { json: true })}>{t('q.blocksGo')}</Button>
        {r ? ['created', 'updated', 'edited', 'human'].map((k) => <Chip key={k} state={k === 'edited' && r[k].length ? 'warn' : undefined}>{t(`bl.${k}`)}: {r[k].length}</Chip>) : null}
      </div>
      {r?.edited.length ? <p className="muted small">{t('q.blocksEdited')}</p> : null}
      <JobOutput c={c} />
    </div>
  )
}
