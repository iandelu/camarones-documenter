import { useEffect, useState } from 'react'
import AgentLaunch from './AgentLaunch.jsx'
import { APP, getJSON } from './api.js'
import { lang, t } from './i18n.js'
import { severities, shape } from './result.js'
import { useJob } from './useJob.js'

// The Taller's views over --json (desktop app): what the generic forms would print, laid out with the action that
// follows from it — install what is missing, confirm a question, acknowledge a page, look at the CVEs in Libraries.
// Every action is a catalog command run by the app's server (lib/appapi.py), never logic of its own.
export default function TallerPanels({ zone }) {
  if (zone === 'check') return <div className="tw-list"><Doctor /><Context /><Evals /><Ab /></div>
  if (zone === 'analyze') return <div className="tw-list"><Cves /><Fresh /><Blocks /></div>
  if (zone === 'interviews') return <div className="tw-list"><Interviews /></div>
  return null
}

let INFO = null
const info = () => (INFO ||= getJSON('app/info').catch((e) => { INFO = null; throw e }))

function Card({ title, cmd, ai, lead, children }) {
  return (
    <div className="co-card tw-cmd">
      <div className="tw-head"><b>{title}</b> {cmd ? <code className="muted">camaron {cmd}</code> : null}
        {ai ? <span className="pill">{t('twAi')}</span> : null}</div>
      {lead ? <p className="muted small">{lead}</p> : null}
      {children}
    </div>
  )
}

// Status, error and (folded) output of a job; the output opens by itself when the command failed. A gate that exits
// 1 with its --json result (inventory --cves, check) found something: that is a finding, not a failure.
function JobLine({ j }) {
  if (!j.job && !j.error) return null
  const found = j.job && j.job.rc === 1 && j.job.result != null
  const failed = j.job && !j.running && j.job.status !== 'done' && !found
  return (
    <>
      {found ? <span className="tw-status warn" role="status">{t('twFound')}</span>
        : j.status ? <span className={`tw-status ${j.job.status}`} role="status">{j.status}</span> : null}
      {j.error ? <p className="error" role="alert">{j.error}</p> : null}
      {j.job?.lines.length ? (
        <details className="tw-out" open={failed}>
          <summary className="muted small">{t('twLog')}</summary>
          <pre className="joblog tw-log">{j.job.lines.join('\n')}</pre>
        </details>
      ) : null}
    </>
  )
}

const cell = (v) => (v === true ? t('yes') : v === false ? t('no') : v == null || v === '' ? '—' : String(v))

function ResultView({ result }) {
  const s = shape(result)
  if (s.kind === 'empty') return <p className="muted small">{t('twNothing')}</p>
  if (s.kind === 'text') return <pre className="joblog">{s.text}</pre>
  if (s.kind === 'pairs') return (
    <table className="kpi-table tw-table"><tbody>{s.rows.map(([k, v]) => <tr key={k}><th>{k}</th><td>{cell(v)}</td></tr>)}</tbody></table>
  )
  return (
    <div className="tw-scroll"><table className="kpi-table tw-table">
      <thead><tr>{s.cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>{s.rows.map((r, i) => <tr key={i}>{r.map((v, k) => <td key={k}>{cell(v)}</td>)}</tr>)}</tbody>
    </table></div>
  )
}

// ---------- Comprobar ----------

function Doctor() {
  const check = useJob()
  const fix = useJob()
  useEffect(() => { check.start('doctor', { json: true }) }, [])
  const r = check.job?.result
  async function run(f) {
    const end = await fix.start(f.cmd, f.args)
    if (end) check.start('doctor', { json: true })
  }
  const state = (x) => (x.ok ? <span className="ok">{t('drOk')}</span>
    : x.need === false ? <span className="muted">{t('drOptional')}</span> : <span className="bad">{t('drMissing')}</span>)
  const fixBtn = (x) => (x.fix ? <button type="button" className="ghost small" disabled={fix.running || check.running}
    onClick={() => run(x.fix)}>{x.fix.cmd === 'setup' ? t('drSetup') : t('drInstall')}</button> : null)
  return (
    <Card title={t('drTitle')} cmd="doctor" lead={t('drLead')}>
      {!r && check.running ? <div className="co-esqueleto skeleton" aria-busy="true" /> : null}
      {r ? (
        <div className="tw-scroll"><table className="kpi-table tw-table"><tbody>
          {r.prerequisites.map((p) => (
            <tr key={p.name}><th>{p.name}</th><td>{p.found || ''}{p.note ? <span className="muted small"> · {p.note}</span> : null}</td>
              <td>{state(p)}</td><td>{p.ok ? null : fixBtn(p) || <span className="muted small">{p.hint}</span>}</td></tr>))}
          {r.tools.map((x) => (
            <tr key={x.name}><th>{x.name}</th><td>{x.found || '—'} <span className="muted small">({t('drPinned')} {x.pinned})</span></td>
              <td>{state({ ...x, need: true })}</td><td>{fixBtn(x)}</td></tr>))}
        </tbody></table></div>
      ) : null}
      {r?.drift.length ? (
        <div className="tw-drift">
          <p className="aviso small">{t('drDrift').replace('{n}', r.drift.length)}</p>
          <ul className="small">{r.drift.map((d) => <li key={d.path}><code>{d.path}</code> <span className="muted">{d.state} · {d.what}</span></li>)}</ul>
          <button type="button" className="ghost small" disabled={fix.running} onClick={() => run(r.fix_drift)}>{t('drRepair')}</button>
        </div>
      ) : r ? <p className="muted small">{t('drNoDrift')}</p> : null}
      <div className="row tw-actions"><JobLine j={fix.job ? fix : check} /></div>
    </Card>
  )
}

function Context() {
  const j = useJob()
  useEffect(() => { j.start('doctor', { context: true, json: true }) }, [])
  const r = j.job?.result
  return (
    <Card title={t('cxTitle')} cmd="doctor --context" lead={t('cxLead')}>
      {r ? (<>
        <p><b>{r.total}</b> / {r.budget} {t('cxTokens')} · <span className={r.over ? 'bad' : 'ok'}>{r.over ? t('cxOver') : t('cxUnder')}</span>
          {r.on_use ? <span className="muted small"> · {t('cxOnUse').replace('{n}', r.on_use)}</span> : null}</p>
        <div className="tw-scroll"><table className="kpi-table tw-table"><tbody>
          {r.items.map((x) => <tr key={x.path}><th>{x.kind}</th><td><code>{x.path}</code></td><td>{x.tokens}</td>
            <td className="muted small">{x.kit ? t('cxKit') : t('cxProject')}</td></tr>)}
        </tbody></table></div>
      </>) : <JobLine j={j} />}
    </Card>
  )
}

function Evals() {
  const list = useJob()
  const act = useJob()
  const [user, setUser] = useState('')
  useEffect(() => { list.start('eval', { action: 'list', json: true }); info().then((i) => setUser(i.user), () => {}) }, [])
  const qs = list.job?.result || []
  async function run(args) {
    const end = await act.start('eval', args)
    if (end) list.start('eval', { action: 'list', json: true })
  }
  const confirmed = qs.filter((q) => q['x-confirmed']).length
  return (
    <Card title={t('evTitle')} cmd="eval" ai lead={t('evLead')}>
      {list.job?.result ? (qs.length ? (
        <div className="tw-scroll"><table className="kpi-table tw-table"><tbody>
          {qs.map((q) => <tr key={q.id}><th><code>{q.id}</code></th><td>{q.q}</td>
            <td>{q['x-confirmed'] ? <span className="ok">{t('evConfirmed')}</span>
              : <button type="button" className="ghost small" disabled={act.running || !user}
                        onClick={() => run({ action: 'confirm', ids: [q.id], by: user })}>{t('evConfirm')}</button>}</td></tr>)}
        </tbody></table></div>
      ) : <p className="muted small">{t('evNone')}</p>) : <JobLine j={list} />}
      <div className="row tw-actions">
        {confirmed ? <button type="button" className="small" disabled={act.running} onClick={() => run({ action: 'run', json: true })}>
          {t('evRun').replace('{n}', confirmed)}</button> : null}
        <button type="button" className="ghost small" disabled={act.running} onClick={() => run({ action: 'draft' })}>{t('evDraft')}</button>
        <JobLine j={act} />
      </div>
      {!confirmed && qs.length ? <p className="muted small">{t('evNeedConfirm')}</p> : null}
      {act.job?.result ? <ResultView result={act.job.result} /> : null}
    </Card>
  )
}

function Ab() {
  const j = useJob()
  const [q, setQ] = useState('')
  return (
    <Card title={t('abTitle')} cmd="ab --qa" ai lead={t('abLead')}>
      <div className="row tw-actions">
        <input className="co-input tw-grow" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('abPh')} aria-label={t('abPh')} />
        <button type="button" className="small" disabled={j.running || !q.trim() || q.trim().startsWith('-')}
                onClick={() => j.start('ab', { qa: q.trim(), json: true })}>{t('abGo')}</button>
        {j.running ? <button type="button" className="ghost small" onClick={j.stop}>{t('twStop')}</button> : null}
      </div>
      <JobLine j={j} />
      {j.job?.result ? <ResultView result={j.job.result} /> : null}
    </Card>
  )
}

// ---------- Analizar ----------

function Cves() {
  const scan = useJob()
  const [inv, setInv] = useState(null)
  const load = () => getJSON('inventory').then(setInv, () => {})
  useEffect(() => { load() }, [])
  async function go() {
    const end = await scan.start('inventory', { cves: true, json: true })
    if (end) load()
  }
  const sev = severities(inv?.libraries)
  return (
    <Card title={t('cvTitle')} cmd="inventory --cves" lead={t('cvLead')}>
      {inv ? (inv.vulns ? (
        <p>{sev.length ? sev.map(([s, n]) => <span key={s} className={`pill ${['critical', 'high'].includes(s) ? 'bad' : 'warn'}`}>{n} {t(`sev.${s}`).startsWith('sev.') ? s : t(`sev.${s}`)}</span>)
          : <span className="ok">{t('cvClean')}</span>}
          <span className="muted small"> · {t('cvAt')} {inv.vulns.at?.slice(0, 10)}</span></p>
      ) : <p className="muted small">{t('cvNever')}</p>) : null}
      <div className="row tw-actions">
        <button type="button" className="small" disabled={scan.running} onClick={go}>{t('cvScan')}</button>
        <a className="button ghost small" href="#/libs">{t('cvLibs')} →</a>
        <JobLine j={scan} />
      </div>
    </Card>
  )
}

function Fresh() {
  const list = useJob()
  const act = useJob()
  const [user, setUser] = useState('')
  useEffect(() => { list.start('fresh', { json: true }); info().then((i) => setUser(i.user), () => {}) }, [])
  const rows = (list.job?.result || []).filter((p) => p.state === 'suspect' || p.state === 'stale')
  async function run(args) {
    const end = await act.start('fresh', args)
    if (end) list.start('fresh', { json: true })
  }
  return (
    <Card title={t('frTitle')} cmd="fresh" lead={t('frLead')}>
      {list.job?.result ? (rows.length ? (
        <div className="tw-scroll"><table className="kpi-table tw-table"><tbody>
          {rows.map((p) => <tr key={p.path}><th><a href={`#/docs/${p.path}`}>{p.path}</a></th>
            <td><span className={p.state === 'stale' ? 'bad' : 'warn'}>{t(`fr.${p.state}`)}</span></td>
            <td className="small"><code>{[...p.changed, ...p.missing].slice(0, 3).join(', ')}</code></td>
            <td>{p.state === 'suspect' ? <button type="button" className="ghost small" disabled={act.running || !user}
              onClick={() => run({ ack: [p.path], by: user })}>{t('frAck')}</button> : null}</td></tr>)}
        </tbody></table></div>
      ) : <p className="ok small">{t('frAllFresh')}</p>) : <JobLine j={list} />}
      {rows.length ? (
        <div className="row tw-actions">
          <button type="button" className="small" disabled={act.running} onClick={() => run({ plan: true })}>{t('frPlan')}</button>
          <JobLine j={act} />
        </div>
      ) : null}
    </Card>
  )
}

function Blocks() {
  const j = useJob()
  const r = j.job?.result
  return (
    <Card title={t('blTitle')} cmd="blocks" lead={t('blLead')}>
      <div className="row tw-actions">
        <button type="button" className="small" disabled={j.running} onClick={() => j.start('blocks', { json: true })}>{t('blGo')}</button>
        <JobLine j={j} />
      </div>
      {r ? (
        <p className="small">{['created', 'updated', 'edited', 'human'].map((k) => <span key={k} className="pill">{t(`bl.${k}`)}: {r[k].length}</span>)}</p>
      ) : null}
      {r?.edited.length ? <p className="aviso small">{t('blEdited')}</p> : null}
    </Card>
  )
}

// ---------- Entrevistas ----------

const INTERVIEW_UNITS = ['questionnaire', 'answers', 'interview-context', 'interview-language', 'interview-history']

// How the interviews run, and everything around them on this machine: the questionnaire exported to share, the
// answers that come back imported, the round of answers closed, and each interview unit opened with an agent.
function Interviews() {
  const [d, setD] = useState(null)
  const [units, setUnits] = useState([])
  const [root, setRoot] = useState('')
  const job = useJob()
  const load = () => {
    getJSON('interview').then(setD, () => {})
    getJSON('pipeline').then((p) => setUnits(p.units.filter((u) => INTERVIEW_UNITS.includes(u.id))), () => {})
  }
  useEffect(() => { load(); info().then((i) => setRoot(i.root), () => {}) }, [])
  async function step(args) {
    const end = await job.start('interview', args)
    if (end) load()
    return end
  }
  async function exportIt() {
    const end = await step({ action: 'export', lang: lang() })
    if (end?.status === 'done' && root) {
      const sep = root.includes('\\') ? '\\' : '/'
      APP?.reveal([root, 'docs', 'interview', 'questionnaire', 'questionnaire.html'].join(sep))
    }
  }
  async function importIt() {
    const files = await APP?.pickFiles('answers')
    if (files?.length) step({ action: 'import', args: files })
  }
  async function closeRound() {
    const end = await job.start('plan', { action: 'done', unit: 'answers' })
    if (end) load()
  }
  const team = d?.mode === 'team'
  const s = d?.status
  const answersUnit = units.find((u) => u.id === 'answers')
  return (
    <Card title={t('inTitle')} cmd="interview" lead={t('inLead')}>
      {d ? (
        <div className="row tw-actions">
          <span>{t('inMode')}: <b>{team ? t('inTeam') : t('inLive')}</b></span>
          <button type="button" className="ghost small" disabled={job.running}
                  onClick={() => step({ action: 'mode', args: [team ? 'live' : 'team'] })}>{team ? t('inToLive') : t('inToTeam')}</button>
        </div>
      ) : <div className="co-esqueleto skeleton" aria-busy="true" />}
      {team ? (
        <div className="tw-block">
          {d.available ? (<>
            <p className="small">{t('ivQuestions').replace('{n}', s.questions)} · {t('ivPeople').replace('{n}', s.respondents.length)}
              {s.respondents.length ? <span className="muted"> ({s.respondents.map((r) => r.name).join(', ')})</span> : null}
              {s.conflicts.length ? <span className="warn"> · {t('ivConflicts').replace('{n}', s.conflicts.length)}</span> : null}</p>
            <div className="row tw-actions">
              <a className="button small" href="#/interview">{t('inAnswer')} →</a>
              <button type="button" className="ghost small" disabled={job.running} onClick={exportIt}>{t('inExport')}</button>
              <button type="button" className="ghost small" disabled={job.running} onClick={importIt}>{t('inImport')}</button>
              {answersUnit && answersUnit.status !== 'done' && s.respondents.length
                ? <button type="button" className="ghost small" disabled={job.running} onClick={closeRound}>{t('inClose')}</button> : null}
            </div>
          </>) : <p className="aviso small">{t('inNoForm')}</p>}
        </div>
      ) : null}
      <div className="row tw-actions"><JobLine j={job} /></div>
      {units.filter((u) => u.runner === 'agent').length ? (
        <div className="tw-block">
          <h3 className="small">{t('inUnits')}</h3>
          {units.filter((u) => u.runner === 'agent').map((u) => (
            <div key={u.id} className="in-unit">
              <span><code>{u.id}</code> <span className="muted small">{u.status}</span></span>
              <AgentLaunch unit={u} title={false} />
            </div>
          ))}
        </div>
      ) : null}
    </Card>
  )
}
