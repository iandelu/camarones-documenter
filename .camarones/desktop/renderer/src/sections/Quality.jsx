import { Fragment, useEffect, useMemo, useState } from 'react'
import { Aviso, Button, Card, Chip, Skeleton } from '@camaron/ui'
import { applyFilter, facets, matrix } from '@camaron/ui/libs.js'
import { severities } from '@camaron/ui/result.js'
import { ago } from '../jobs.js'
import { doctorRows, seconds } from '../quality.js'
import { useAgents, useCmd, useJob } from '../hooks.js'
import { AgentPicker, Failed, Fold, JobOutput, Page, ResultView, UnitRow } from '../parts.jsx'
import Commands from './Commands.jsx'
import { lang, t } from '../i18n.js'

// Quality by task: is this machine ready (the doctor, kept between visits), how much an agent session loads, the
// golden questions and the same question with and without the docs; then what the code says without AI — known
// libraries and their known vulnerabilities, pages out of date, the generated blocks. KPIs are the portal's.
export default function Quality({ srv, jobs }) {
  const [user, setUser] = useState('')
  useEffect(() => { srv.get('app/info').then((i) => setUser(i.user), () => {}) }, [])
  const p = { srv, jobs, user }
  return (
    <Page title={t('nav.quality')}>
      <Doctor {...p} />
      <Context {...p} />
      <Evals {...p} />
      <Ab {...p} />
      <h2 className="eyebrow dk-group">{t('q.analyze')}</h2>
      <Libs {...p} />
      <Fresh {...p} />
      <Blocks {...p} />
      <div className="row"><Button size="sm" variant="ghost" href="../#/kpis">{t('q.kpis')}</Button></div>
      <Commands srv={srv} jobs={jobs} section="quality" />
    </Page>
  )
}

const now = () => Date.now() / 1000

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
    <Card className="dk-run">
      <div className="row"><span className="eyebrow">{t('q.doctor')}</span><span className="dk-grow"></span>
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
    </Card>
  )
}

// What an agent session reads before the first page (doctor --context): the total against the budget, the items folded.
function Context({ srv, jobs }) {
  const c = useCmd(srv, jobs, { quiet: true })
  useEffect(() => { c.run('doctor', { context: true, json: true }) }, [])
  const r = c.job?.result
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('q.context')}</span>
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
    </Card>
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
      await srv.post('app/agent', { unit: DRAFT, agent: a.agent, lang: lang(), mode: 'new' })
      setNote({ ok: t('q.proposing', { agent: a.label(a.agent) }), error: '' })
    } catch (e) { setNote({ ok: '', error: e.message }) }
    loadPlan()
  }
  const noAgent = a.agents && !a.agents.length
  return (
    <Card className="dk-run">
      <div className="row"><span className="eyebrow">{t('q.evals')}</span><span className="cu-chip cu-chip--info">{t('cmds.ai')}</span></div>
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
    </Card>
  )
}

// The same question with and without cam-docs (ab --qa), side by side.
function Ab({ srv, jobs }) {
  const c = useCmd(srv, jobs)
  const [q, setQ] = useState('')
  const clean = q.trim()
  return (
    <Card className="dk-run">
      <div className="row"><span className="eyebrow">{t('q.ab')}</span><span className="cu-chip cu-chip--info">{t('cmds.ai')}</span></div>
      <div className="row">
        <input className="cu-input dk-grow" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('q.abAsk')} aria-label={t('q.abAsk')} />
        {c.running ? <Button size="sm" variant="danger" onClick={c.stop}>{t('job.stop')}</Button>
          : <Button size="sm" disabled={!clean || clean.startsWith('-')} onClick={() => c.run('ab', { qa: clean, json: true })}>{t('q.compare')}</Button>}
      </div>
      <JobOutput c={c} />
      {c.job?.result ? <ResultView result={c.job.result} /> : null}
    </Card>
  )
}

// The libraries every repo declares, read from the code without AI (inventory), as a library x service table like
// the portal's: reread them any time, and look their known vulnerabilities up (OSV, inventory --cves); the worst
// first, and a vulnerable row opens on its advisories.
const SEV = { critical: 'bad', high: 'bad', medium: 'warn', moderate: 'warn' }
const sevWord = (s) => { const k = `sev.${s}`; const w = t(k); return w === k ? s : w }
function Libs({ srv, jobs }) {
  const c = useCmd(srv, jobs)
  const [inv, setInv] = useState(null)
  const [error, setError] = useState('')
  const [f, setF] = useState({})
  const [open, setOpen] = useState(null)
  const load = () => srv.get('inventory').then((x) => { setInv(x); setError('') }, (e) => setError(e.message))
  useEffect(() => { load() }, [])
  const rows = inv?.libraries || []
  const shown = useMemo(() => applyFilter(rows, f), [rows, f])
  const m = useMemo(() => matrix(shown), [shown])
  const fc = useMemo(() => facets(rows), [rows])
  const sev = severities(rows)
  const run = async (args) => { await c.run('inventory', args); load() }
  const set = (k) => (v) => setF((cur) => ({ ...cur, [k]: v }))
  const count = new Set(rows.map((r) => r.ecosystem + r.name)).size
  return (
    <Card className="dk-run">
      <div className="row"><span className="eyebrow">{t('q.libs')}</span><span className="dk-grow"></span>
        <Button size="sm" variant="ghost" href="../#/libs">{t('q.inPortal')}</Button></div>
      {error ? <Failed title={t('q.cvFailed')} detail={error} onRetry={load} /> : null}
      {inv ? (
        <div className="row">
          <b>{t('q.libsCount', { n: count })}</b>
          {inv.vulns ? (sev.length ? sev.map(([s, n]) => <Chip key={s} state={SEV[s]}>{n} {sevWord(s)}</Chip>) : <Chip state="ok">{t('q.cvClean')}</Chip>)
            : <span className="muted small">{t('q.cvNever')}</span>}
          {inv.vulns ? <span className="muted small">{t('q.cvAt', { day: inv.vulns.at?.slice(0, 10) })}</span> : null}
        </div>
      ) : !error ? <Skeleton lines={2} /> : null}
      <div className="row">
        <Button size="sm" variant="primary" disabled={c.running} onClick={() => run({})}>{t('q.libsRead')}</Button>
        <Button size="sm" disabled={c.running} onClick={() => run({ cves: true, json: true })}>{t('q.cvScan')}</Button>
        <span className="muted small">{t('q.libsNoAi')}</span>
      </div>
      <JobOutput c={c} />
      {rows.length ? (<>
        <div className="row">
          <input type="search" className="cu-input dk-grow" placeholder={t('q.libsSearch')} aria-label={t('q.libsSearch')} value={f.q || ''} onChange={(e) => set('q')(e.target.value)} />
          <FacetSelect label={t('q.libsCategory')} value={f.category} onChange={set('category')} options={fc.category} />
          <FacetSelect label={t('q.libsRepo')} value={f.repo} onChange={set('repo')} options={fc.repo} />
          <label className="dk-check"><input type="checkbox" checked={!!f.vulnerable} onChange={(e) => set('vulnerable')(e.target.checked)} />{t('q.libsOnlyVuln')}</label>
        </div>
        {m.items.length ? (
          <div className="dk-scroll"><table className="dk-table dk-libs">
            <thead><tr><th>{t('q.libsLibrary')}</th><th>{t('q.libsCategory')}</th>{m.repos.map((r) => <th key={r}>{r}</th>)}</tr></thead>
            <tbody>{m.items.map((x) => (
              <Fragment key={x.key}>
                <tr className={x.worst ? `vuln sev-${SEV[x.worst] || 'low'}` : ''}>
                  <td>{x.vulns.length ? <button type="button" className="dk-linkish" aria-expanded={open === x.key} onClick={() => setOpen(open === x.key ? null : x.key)}>
                      <code>{x.name}</code></button> : <code>{x.name}</code>} <span className="muted small">{x.ecosystem}</span>
                    {x.worst ? <> <Chip state={SEV[x.worst]}>{sevWord(x.worst)}</Chip></> : null}
                    {x.drift ? <> <Chip state="warn">{t('q.libsVersions')}</Chip></> : null}</td>
                  <td className="muted small">{x.category}</td>
                  {m.repos.map((r) => { const v = x.cells[r]; return <td key={r} className={v?.vulns.length ? 'cell-vuln' : ''}>{v ? v.version || '—' : ''}</td> })}
                </tr>
                {open === x.key ? (
                  <tr><td colSpan={2 + m.repos.length}><ul className="dk-advisories">{[...new Map(x.vulns.map((v) => [v.id, v])).values()].map((v) => (
                    <li key={v.id}><a href={`https://osv.dev/vulnerability/${encodeURIComponent(v.id)}`} target="_blank" rel="noreferrer">{v.cve || v.id}</a>{' '}
                      <Chip state={SEV[v.severity]}>{sevWord(v.severity)}{v.score ? ` ${v.score}` : ''}</Chip>{' '}
                      <span className="small">{v.summary}</span> {v.fixed ? <b className="small">{t('q.libsFixed', { v: v.fixed })}</b> : null}</li>))}</ul></td></tr>
                ) : null}
              </Fragment>
            ))}</tbody>
          </table></div>
        ) : <p className="muted small">{t('nothing')}</p>}
      </>) : inv ? <p className="muted small">{t('q.libsNone')}</p> : null}
    </Card>
  )
}

function FacetSelect({ label, value, onChange, options }) {
  return (
    <select className="cu-input dk-select" value={value || ''} aria-label={label} onChange={(e) => onChange(e.target.value)}>
      <option value="">{label}: {t('q.libsAll')}</option>
      {options.map(([k, n]) => <option key={k} value={k}>{k} ({n})</option>)}
    </select>
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
    <Card className="dk-run">
      <span className="eyebrow">{t('q.fresh')}</span>
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
    </Card>
  )
}

// The facts read from the code without AI in every generated block (blocks).
function Blocks({ srv, jobs }) {
  const c = useCmd(srv, jobs)
  const r = c.job?.result
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('q.blocks')}</span>
      <div className="row">
        <Button size="sm" disabled={c.running} onClick={() => c.run('blocks', { json: true })}>{t('q.blocksGo')}</Button>
        {r ? ['created', 'updated', 'edited', 'human'].map((k) => <Chip key={k} state={k === 'edited' && r[k].length ? 'warn' : undefined}>{t(`bl.${k}`)}: {r[k].length}</Chip>) : null}
      </div>
      {r?.edited.length ? <p className="muted small">{t('q.blocksEdited')}</p> : null}
      <JobOutput c={c} />
    </Card>
  )
}
