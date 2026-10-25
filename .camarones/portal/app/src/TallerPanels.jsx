import { useEffect, useRef, useState } from 'react'
import AgentLaunch from './AgentLaunch.jsx'
import { APP, getJSON, postJSON } from './api.js'
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
  if (zone === 'team') return <div className="tw-list"><Remote /><Trust /><Plugins /></div>
  if (zone === 'kitdev') return <div className="tw-list"><KitSandbox /><KitTests /><KitPortal /></div>
  if (zone === 'machine') return <div className="tw-list"><Setup /><Settings /><Tokens /><Repos /><Kit /></div>
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

// ---------- Equipo ----------

// The team's cam-docs repo on this machine: where it points, whether every checkpoint is shared, and the way to the
// portal's Sync view, which shares on demand.
function Remote() {
  const [s, setS] = useState(null)
  const [url, setUrl] = useState('')
  const j = useJob()
  const load = () => getJSON('sync').then((x) => { setS(x); setUrl(x.remote || '') }, () => {})
  useEffect(() => { load() }, [])
  async function run(cmd, args) {
    const end = await j.start(cmd, args)
    if (end) load()
  }
  return (
    <Card title={t('tmRemote')} cmd="remote · share" lead={t('tmRemoteLead')}>
      <div className="row tw-actions">
        <input className="co-input tw-grow" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="git@github.com:equipo/cam-docs.git"
               aria-label={t('tmRemote')} />
        <button type="button" className="small" disabled={j.running || !url.trim() || url.trim() === s?.remote || url.trim().startsWith('-')}
                onClick={() => run('remote', { url: url.trim() })}>{t('tmSaveRemote')}</button>
      </div>
      {s ? (
        <div className="row tw-actions">
          <span>{t('tmAuto')}: <b>{s.auto ? t('tmOn') : t('tmOff')}</b></span>
          <button type="button" className="ghost small" disabled={j.running || !s.remote}
                  onClick={() => run('share', { auto: s.auto ? 'off' : 'on' })}>{s.auto ? t('tmAutoOff') : t('tmAutoOn')}</button>
          <a className="button ghost small" href="#/sync">{t('tmSync')} →</a>
        </div>
      ) : null}
      <div className="row tw-actions"><JobLine j={j} /></div>
    </Card>
  )
}

// Agent config and plugins that came with the team's repo and this machine has not approved: nothing of it is loaded
// until it is. Approving runs `trust --yes` after the app asked.
function Trust() {
  const list = useJob()
  const act = useJob()
  const hooks = useJob()
  const load = () => { list.start('trust', { json: true }); hooks.start('hooks', { json: true }) }
  useEffect(() => { load() }, [])
  const rows = list.job?.result?.pending
  const on = hooks.job?.result?.enabled
  async function approve() {
    const end = await act.start('trust', {}, true)
    if (end) load()
  }
  async function toggleHooks() {
    const end = await act.start('hooks', { state: on ? 'off' : 'on' })
    if (end) load()
  }
  return (
    <Card title={t('tmTrust')} cmd="trust · hooks" lead={t('tmTrustLead')}>
      {rows ? (rows.length ? (<>
        <div className="tw-scroll"><table className="kpi-table tw-table"><tbody>
          {rows.map((r) => <tr key={r.kind + r.label}><th>{r.kind}</th><td><code>{r.label}</code></td>
            <td className="muted small">{r.detail}</td><td className="warn">{r.status}</td></tr>)}
        </tbody></table></div>
        <div className="row tw-actions">
          <button type="button" className="small" disabled={act.running} onClick={approve}>{t('tmApprove').replace('{n}', rows.length)}</button>
        </div>
      </>) : <p className="ok small">{t('tmTrusted')}</p>) : <JobLine j={list} />}
      {on != null ? (
        <div className="row tw-actions">
          <span>{t('tmHooks')}: <b>{on ? t('tmOn') : t('tmOff')}</b></span>
          <button type="button" className="ghost small" disabled={act.running} onClick={toggleHooks}>{on ? t('tmHooksOff') : t('tmHooksOn')}</button>
        </div>
      ) : null}
      <p className="muted small">{t('tmHooksLead')}</p>
      <div className="row tw-actions"><JobLine j={act} /></div>
    </Card>
  )
}

function Plugins() {
  const list = useJob()
  const act = useJob()
  useEffect(() => { list.start('plugins', { json: true }) }, [])
  const rows = list.job?.result || null
  async function run(action, name) {
    const end = await act.start('plugins', { action, target: name })
    if (end) list.start('plugins', { json: true })
  }
  return (
    <Card title={t('tmPlugins')} cmd="plugins" lead={t('tmPluginsLead')}>
      {rows ? (rows.length ? (
        <div className="tw-scroll"><table className="kpi-table tw-table"><tbody>
          {rows.map((p) => <tr key={p.name}><th>{p.name} <span className="muted small">{p.version}</span></th>
            <td className="small">{(p.provides || []).join(', ')}{p.runs_code ? <span className="pill warn">{t('tmRunsCode')}</span> : null}</td>
            <td className={p.status === 'active' ? 'ok small' : 'muted small'}>{p.status}</td>
            <td>{p.status === 'active'
              ? <button type="button" className="ghost small" disabled={act.running} onClick={() => run('disable', p.name)}>{t('tmDisable')}</button>
              : <button type="button" className="ghost small" disabled={act.running} onClick={() => run('enable', p.name)}>{t('tmEnable')}</button>}</td></tr>)}
        </tbody></table></div>
      ) : <p className="muted small">{t('twNothing')}</p>) : <JobLine j={list} />}
      <div className="row tw-actions">
        <a className="button ghost small" href="#/ci">{t('tmCi')} →</a>
        <JobLine j={act} />
      </div>
    </Card>
  )
}

// ---------- Esta máquina ----------

let MACHINE = null
const machine = (fresh) => { if (fresh) MACHINE = null; return (MACHINE ||= getJSON('app/machine').catch((e) => { MACHINE = null; throw e })) }

// `setup` with a progress bar: the steps it reports done (✔) against the steps it will take on this machine.
function Setup() {
  const j = useJob()
  const [steps, setSteps] = useState(0)
  useEffect(() => { machine().then((m) => setSteps(m.setup_steps), () => {}) }, [])
  const done = (j.job?.lines || []).filter((l) => l.trim().startsWith('✔')).length
  const pct = steps ? Math.min(100, Math.round((done / steps) * 100)) : 0
  return (
    <Card title={t('mcSetup')} cmd="setup" lead={t('mcSetupLead')}>
      {j.job ? (
        <div className="mc-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={j.running ? pct : 100}>
          <span style={{ transform: `scaleX(${(j.running ? pct : 100) / 100})` }} />
        </div>
      ) : null}
      <div className="row tw-actions">
        <button type="button" className="small" disabled={j.running} onClick={() => j.start('setup', {})}>{t('mcSetupGo')}</button>
        {j.running ? <span className="muted small">{done}/{steps}</span> : null}
        <JobLine j={j} />
      </div>
    </Card>
  )
}

function Settings() {
  const [m, setM] = useState(null)
  const [codex, setCodex] = useState('')
  const j = useJob()
  const load = (fresh) => machine(fresh).then((x) => { setM(x); setCodex(x.settings.codex_model) }, () => {})
  useEffect(() => { load(false) }, [])
  async function set(key, value) {
    const end = await j.start('config', { action: 'set', key, value })
    if (end) load(true)
  }
  if (!m) return null
  const s = m.settings
  return (
    <Card title={t('mcSettings')} cmd="config" lead={t('mcSettingsLead')}>
      <div className="tw-fields">
        <div className="tw-field"><label htmlFor="mc-lang">{t('mcLang')}</label>
          <select id="mc-lang" className="co-input" value={s.lang} disabled={j.running} onChange={(e) => set('lang', e.target.value)}>
            <option value="es">Español</option><option value="en">English</option></select></div>
        <div className="tw-field"><label htmlFor="mc-model">{t('mcModel')}</label>
          <select id="mc-model" className="co-input" value={s.model} disabled={j.running} onChange={(e) => set('model', e.target.value)}>
            {m.models.map((x) => <option key={x} value={x}>{x}</option>)}</select></div>
        <div className="tw-field"><label htmlFor="mc-codex">{t('mcCodex')}</label>
          <input id="mc-codex" className="co-input" value={codex} disabled={j.running} onChange={(e) => setCodex(e.target.value)}
                 onBlur={() => codex.trim() && codex.trim() !== s.codex_model && set('codex_model', codex.trim())} /></div>
      </div>
      <p className="muted small">{t('mcAgents')}: {m.agents.length ? m.agents.map((a) => a.label).join(', ') : t('mcNoAgents')}</p>
      <div className="row tw-actions"><JobLine j={j} /></div>
    </Card>
  )
}

// GitLab / GitHub tokens, kept in the OS keychain. They go to the app's server in the request body only (never on a
// command line) and never come back. The first-run wizard shows it too, with the host of a repo that failed to clone.
export function Tokens({ host = '' }) {
  const [d, setD] = useState(null)
  const [form, setForm] = useState({ host, kind: /github/i.test(host) ? 'github' : 'gitlab', token: '' })
  const [state, setState] = useState(null)
  const [busy, setBusy] = useState(false)
  const load = () => getJSON('app/creds').then(setD, (e) => setState({ error: e.message }))
  useEffect(() => { load() }, [])
  async function act(path, body, okMsg) {
    setBusy(true)
    setState(null)
    try { const r = await postJSON(path, body); setState({ ok: okMsg(r) }); await load(); return true } catch (e) { setState({ error: e.message }); return false } finally { setBusy(false) }
  }
  async function save(anyway) {
    if (await act('app/creds', { ...form, anyway }, (r) => t('mcTokSaved').replace('{host}', r.host).replace('{user}', r.user || '—')))
      setForm((f) => ({ ...f, token: '' }))
  }
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  return (
    <Card title={t('mcTokens')} lead={t('mcTokensLead')}>
      {d?.hosts.length ? (
        <div className="tw-scroll"><table className="kpi-table tw-table"><tbody>
          {d.hosts.map((h) => <tr key={h.host}><th>{h.host}</th><td className="small">{h.kind}{h.user ? ` · ${h.user}` : ''}</td>
            <td className={h.saved ? 'ok small' : 'warn small'}>{h.saved ? t('mcTokOk') : t('mcTokMissing')}</td>
            <td><button type="button" className="ghost small" disabled={busy}
                        onClick={() => act('app/creds/test', { host: h.host }, (r) => (r.ok ? t('mcTokWorks').replace('{user}', r.info) : t('mcTokFails').replace('{err}', r.info)))}>{t('mcTokTest')}</button>
              <button type="button" className="ghost small" disabled={busy}
                      onClick={() => act('app/creds/delete', { host: h.host }, () => t('mcTokDeleted'))}>{t('mcTokDelete')}</button></td></tr>)}
        </tbody></table></div>
      ) : d ? <p className="muted small">{t('mcTokNone')}</p> : null}
      <form className="tw-fields" onSubmit={(e) => { e.preventDefault(); save(false) }}>
        <div className="tw-field"><label htmlFor="tk-host">{t('mcTokHost')}</label>
          <input id="tk-host" className="co-input" value={form.host} onChange={set('host')} placeholder="gitlab.example.com" required /></div>
        <div className="tw-field"><label htmlFor="tk-kind">{t('mcTokKind')}</label>
          <select id="tk-kind" className="co-input" value={form.kind} onChange={set('kind')}><option value="gitlab">GitLab</option><option value="github">GitHub</option></select></div>
        <div className="tw-field"><label htmlFor="tk-token">{t('mcTokToken')}</label>
          <input id="tk-token" className="co-input" type="password" autoComplete="off" value={form.token} onChange={set('token')} required /></div>
        <div className="tw-field"><button type="submit" className="small" disabled={busy || !form.host.trim() || !form.token.trim()}>{t('mcTokSave')}</button></div>
      </form>
      {state?.ok ? <p className="ok small" role="status">{state.ok}</p> : null}
      {state?.error ? (
        <p className="error small" role="alert">{state.error}{form.token ? <> <button type="button" className="ghost small" disabled={busy} onClick={() => save(true)}>{t('mcTokAnyway')}</button></> : null}</p>
      ) : null}
      <p className="muted small">{t('mcTokWhere').replace('{where}', d?.backend || '…')}</p>
    </Card>
  )
}

function Repos() {
  const [m, setM] = useState(null)
  const [stacks, setStacks] = useState({})
  const j = useJob()
  const load = (fresh) => machine(fresh).then((x) => { setM(x); setStacks(Object.fromEntries(x.repos.map((r) => [r.name, r.stack]))) }, () => {})
  useEffect(() => { load(false) }, [])
  async function run(cmd, args) {
    const end = await j.start(cmd, args)
    if (end) load(true)
  }
  if (!m) return null
  return (
    <Card title={t('mcRepos')} cmd="sync · detect · stack · profile" lead={t('mcReposLead')}>
      {m.repos.length ? (
        <div className="tw-scroll"><table className="kpi-table tw-table"><tbody>
          {m.repos.map((r) => <tr key={r.name}><th>{r.name}</th>
            <td className={r.cloned ? 'ok small' : 'warn small'}>{r.cloned ? t('mcCloned') : t('mcNotCloned')}</td>
            <td><input className="co-input" value={stacks[r.name] || ''} placeholder={t('mcStackDetected')} aria-label={`stack ${r.name}`}
                       onChange={(e) => setStacks((s) => ({ ...s, [r.name]: e.target.value }))} /></td>
            <td>{(stacks[r.name] || '') !== (r.stack || '') ? (
              <button type="button" className="ghost small" disabled={j.running}
                      onClick={() => run('stack', stacks[r.name]?.trim() ? { repo: r.name, text: stacks[r.name].trim() } : { repo: r.name, reset: true })}>{t('mcSave')}</button>
            ) : r.stack ? <button type="button" className="ghost small" disabled={j.running} onClick={() => run('stack', { repo: r.name, reset: true })}>{t('mcReset')}</button> : null}</td></tr>)}
        </tbody></table></div>
      ) : <p className="muted small">{t('mcNoRepos')}</p>}
      <div className="row tw-actions">
        <button type="button" className="small" disabled={j.running} onClick={() => run('sync', {})}>{t('mcSync')}</button>
        <button type="button" className="ghost small" disabled={j.running} onClick={() => run('detect', {})}>{t('mcDetect')}</button>
        <label className="muted small">{t('mcProfile')}{' '}
          <select className="co-input" value={m.profile || ''} disabled={j.running} onChange={(e) => e.target.value && run('profile', { name: e.target.value })}>
            {!m.profile ? <option value="">—</option> : null}<option value="quick">{t('mcQuick')}</option><option value="full">{t('mcFull')}</option></select></label>
        <JobLine j={j} />
      </div>
    </Card>
  )
}

function Kit() {
  const [m, setM] = useState(null)
  const j = useJob()
  const [updated, setUpdated] = useState(false)
  useEffect(() => { machine().then(setM, () => {}) }, [])
  async function update() {
    const end = await j.start('self-update', {})
    if (end?.status === 'done') setUpdated(true)
  }
  if (!m) return null
  return (
    <Card title={t('mcKit')} cmd="self-update · repair" lead={t('mcKitLead').replace('{v}', m.kit.version)}>
      <div className="row tw-actions">
        {m.kit.global ? <button type="button" className="small" disabled={j.running} onClick={update}>{t('mcUpdate')}</button>
          : <span className="muted small">{t('mcLocalKit')}</span>}
        <button type="button" className="ghost small" disabled={j.running} onClick={() => j.start('repair', {})}>{t('mcRepair')}</button>
        {updated && APP?.relaunch ? <button type="button" className="small" onClick={() => APP.relaunch()}>{t('mcRelaunch')}</button> : null}
        <JobLine j={j} />
      </div>
    </Card>
  )
}

// Uninstall, previewed first: `uninstall --dry-run` lists what goes (it only reads, so it runs without asking), and only
// then the real one, behind a dialog that repeats that list. No jokes here.
export function Uninstall() {
  const preview = useJob()
  const go = useJob()
  const [opts, setOpts] = useState({ user_level: false, no_backup: false })
  const dialog = useRef(null)
  const lines = preview.job?.status === 'done' ? preview.job.lines : null
  const args = (dry) => ({ ...(opts.user_level ? { user_level: true } : {}), ...(opts.no_backup && !dry ? { no_backup: true } : {}), ...(dry ? { dry_run: true } : {}) })
  const set = (k) => (e) => setOpts((o) => ({ ...o, [k]: e.target.checked }))
  return (
    <div className="co-card tw-cmd destructive">
      <div className="tw-head"><b>{t('unTitle')}</b> <code className="muted">camaron uninstall</code><span className="pill warn">{t('twDestructive')}</span></div>
      <p className="muted small">{t('unLead')}</p>
      <div className="tw-fields">
        <div className="tw-field check"><input id="un-global" type="checkbox" checked={opts.user_level} onChange={set('user_level')} disabled={go.running} />
          <label htmlFor="un-global">{t('unGlobal')}</label></div>
        <div className="tw-field check"><input id="un-nobackup" type="checkbox" checked={opts.no_backup} onChange={set('no_backup')} disabled={go.running} />
          <label htmlFor="un-nobackup">{t('unNoBackup')}</label></div>
      </div>
      <div className="row tw-actions">
        <button type="button" className="ghost small" disabled={preview.running || go.running} onClick={() => preview.start('uninstall', args(true))}>{t('unPreview')}</button>
        {lines ? <button type="button" className="ghost small" disabled={go.running} onClick={() => dialog.current.showModal()}>{t('unGo')}</button> : null}
        <JobLine j={go.job ? go : preview} />
      </div>
      {lines && !go.job ? <pre className="joblog tw-log">{lines.join('\n')}</pre> : null}
      {go.job?.status === 'done' ? (
        <p className="small">{t('unDone')} {APP?.hub ? <button type="button" className="small" onClick={() => APP.hub()}>{t('unHub')}</button> : null}</p>
      ) : null}
      <dialog ref={dialog} className="tw-dialog">
        <h2>{t('unConfirmTitle')}</h2>
        <p>{opts.no_backup ? t('unConfirmNoBackup') : t('unConfirmBackup')}</p>
        {lines ? <pre className="joblog tw-log">{lines.filter((l) => l.trim().startsWith('•')).join('\n')}</pre> : null}
        <div className="row">
          <button type="button" className="ghost small" onClick={() => dialog.current.close()}>{t('twConfirmNo')}</button>
          <button type="button" className="small" onClick={() => { dialog.current.close(); go.start('uninstall', args(false), true) }}>{t('unGo')}</button>
        </div>
      </dialog>
    </div>
  )
}

// ---------- Kit dev (a checkout of the kit only) ----------

const kitTask = (task, body) => postJSON('app/kitdev', { task, ...(body || {}) })
const useKit = () => useJob(kitTask)

function KitSandbox() {
  const [info, setInfo] = useState(null)
  const [line, setLine] = useState('status')
  const [opened, setOpened] = useState(null)
  const j = useKit()
  const dialog = useRef(null)
  const load = () => getJSON('app/kitdev').then(setInfo, () => {})
  useEffect(() => { load() }, [])
  const lastTraces = j.job?.argv?.includes?.('traces')
  async function run(task, body) {
    const end = await j.start(task, body)
    if (end) load()
  }
  async function openWizard() {
    try { const r = await kitTask('sandbox-open'); setOpened(r.opened ? 'ok' : 'none') } catch (e) { setOpened(e.message) }
  }
  return (
    <Card title={t('kdSandbox')} cmd="scripts/sandbox.py" lead={t('kdSandboxLead')}>
      {info ? <p className="small"><code>{info.sandbox}</code> · {info.sandbox_exists ? <span className="ok">{t('kdExists')}</span>
        : <span className="warn">{t('kdMissing')}</span>}</p> : null}
      <div className="row tw-actions">
        <button type="button" className="small" disabled={j.running} onClick={() => run('sandbox-traces')}>{t('kdTraces')}</button>
        <button type="button" className="ghost small" disabled={j.running} onClick={openWizard}>{t('kdOpen')}</button>
        <button type="button" className="ghost small" disabled={j.running} onClick={() => dialog.current.showModal()}>{t('kdReset')}</button>
      </div>
      <div className="row tw-actions">
        <code className="muted">camaron</code>
        <input className="co-input tw-grow" value={line} onChange={(e) => setLine(e.target.value)} aria-label={t('kdCli')} />
        <button type="button" className="ghost small" disabled={j.running || !line.trim()} onClick={() => run('sandbox-cli', { line })}>{t('kdRunCli')}</button>
      </div>
      {opened ? <p className={opened === 'ok' ? 'ok small' : 'error small'}>{opened === 'ok' ? t('kdOpened') : opened === 'none' ? t('kdNoTerminal') : opened}</p> : null}
      <div className="row tw-actions">
        {j.job && !j.running && j.job.lines.some((l) => l.includes('pristine')) ? <span className="ok">{t('kdPristine')}</span> : null}
        {/* traces exits 1 when the kit left something: with the project installed that is expected, not a failure */}
        {lastTraces && !j.running && j.job.rc === 1 ? <span className="warn" role="status">{t('kdTraced')}</span> : <JobLine j={j} />}
      </div>
      {j.job?.lines.length ? <pre className="joblog tw-log">{j.job.lines.join('\n')}</pre> : null}
      <dialog ref={dialog} className="tw-dialog">
        <h2>{t('kdResetTitle')}</h2>
        <p>{t('kdResetText')}</p>
        <div className="row">
          <button type="button" className="ghost small" onClick={() => dialog.current.close()}>{t('twConfirmNo')}</button>
          <button type="button" className="small" onClick={() => { dialog.current.close(); run('sandbox-reset') }}>{t('kdReset')}</button>
        </div>
      </dialog>
    </Card>
  )
}

// The last "N passed, M failed …" line pytest prints, as pills.
const pytestSummary = (lines) => {
  const last = [...(lines || [])].reverse().find((l) => /\d+ (passed|failed|error)/.test(l))
  return last ? [...last.matchAll(/(\d+) (passed|failed|errors?|skipped|deselected)/g)].map((m) => [m[2], m[1]]) : []
}

function KitTests() {
  const [k, setK] = useState('')
  const [paths, setPaths] = useState('')
  const j = useKit()
  const sum = pytestSummary(j.job?.lines)
  return (
    <Card title={t('kdTests')} cmd="uv run pytest" lead={t('kdTestsLead')}>
      <div className="tw-fields">
        <div className="tw-field"><label htmlFor="kd-k"><code>-k</code></label>
          <input id="kd-k" className="co-input" value={k} onChange={(e) => setK(e.target.value)} placeholder="catalog and not drift" /></div>
        <div className="tw-field"><label htmlFor="kd-paths">{t('kdPaths')}</label>
          <input id="kd-paths" className="co-input" value={paths} onChange={(e) => setPaths(e.target.value)} placeholder="tests/test_catalog.py" /></div>
      </div>
      <div className="row tw-actions">
        {j.running ? <button type="button" className="ghost small" onClick={j.stop}>{t('twStop')}</button>
          : <button type="button" className="small" onClick={() => j.start('pytest', { k: k.trim(), paths: paths.split(/\s+/).filter(Boolean) })}>{t('kdRunTests')}</button>}
        {sum.map(([w, n]) => <span key={w} className={`pill ${w === 'passed' ? 'ok' : w === 'skipped' || w === 'deselected' ? '' : 'bad'}`}>{n} {w}</span>)}
        <JobLine j={j} />
      </div>
      {j.job?.lines.length ? <pre className="joblog tw-log">{j.job.lines.slice(-200).join('\n')}</pre> : null}
    </Card>
  )
}

function KitPortal() {
  const [info, setInfo] = useState(null)
  const j = useKit()
  const [diff, setDiff] = useState(null)
  useEffect(() => { getJSON('app/kitdev').then(setInfo, () => {}) }, [])
  async function check() {
    setDiff(null)
    const end = await j.start('build-diff')
    // `git status --porcelain` prints nothing when app-build is as committed
    if (end) setDiff(end.status === 'done' ? 'pending' : null)
  }
  useEffect(() => { if (diff === 'pending' && j.job && !j.running) setDiff(j.job.lines.every((l) => !l.trim())) }, [diff, j.job?.status])
  return (
    <Card title={t('kdPortal')} cmd="npm · node --test" lead={t('kdPortalLead')}>
      {info && !info.has_node_modules ? <p className="aviso small">{t('kdNoModules')}</p> : null}
      <div className="row tw-actions">
        <button type="button" className="ghost small" disabled={j.running} onClick={() => j.start('portal-ci')}>npm ci</button>
        <button type="button" className="small" disabled={j.running} onClick={() => j.start('portal-test')}>npm test</button>
        <button type="button" className="ghost small" disabled={j.running} onClick={() => j.start('portal-build')}>npm run build</button>
        <button type="button" className="ghost small" disabled={j.running} onClick={check}>{t('kdDiff')}</button>
        <button type="button" className="ghost small" disabled={j.running} onClick={() => j.start('desktop-test')}>{t('kdDesktop')}</button>
        {typeof diff === 'boolean' && !j.running ? <span className={diff ? 'ok' : 'warn'}>{diff ? t('kdBuildSame') : t('kdBuildDiff')}</span> : null}
        <JobLine j={j} />
      </div>
      {j.job?.lines.length ? <pre className="joblog tw-log">{j.job.lines.slice(-200).join('\n')}</pre> : null}
    </Card>
  )
}
