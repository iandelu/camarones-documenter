import { useEffect, useRef, useState } from 'react'
import { APP, getJSON, postJSON } from './api.js'
import { lang, t } from './i18n.js'
import { STEP_KEYS, canContinue, defaultPicks, errorKey, hostOf, manualHints, nextStep, prevStep, progress, repoBody,
  repoFromUrl, repoRows, setupChoice, stepIndex, urlName } from './onboarding.js'
import { portalUrl } from './zones.js'
import { Tokens } from './TallerPanels.jsx'
import { useJob } from './useJob.js'

// The first run in the desktop app's project window (#/start): one step per screen, Back / Continue, the position
// saved on the server (firstrun.json, shared with the CLI wizard) so closing the window never loses it. The work is
// lib/onboard.py's, through /api/app/onboard; the step model is onboarding.js.

// A server rejection said in the person's language: a known code by its own sentence, anything else as it came.
const say = (e) => (errorKey(e.message) ? t(errorKey(e.message)) : `${t('obErrServer')} ${e.message}`)
const fill = (s, vars) => Object.entries(vars).reduce((acc, [k, v]) => acc.replaceAll(`{${k}}`, v), s)
// The job's own POST in place of useJob's catalog command.
const onboardJob = (path, body) => () => postJSON(`app/onboard/${path}`, body?.() ?? {})

export default function Onboarding() {
  const [st, setSt] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [error, setError] = useState('')
  const [moving, setMoving] = useState(false)
  const [rows, setRows] = useState([])                 // repos step
  const [tools, setTools] = useState(null)             // GET tools: {rows, required_ok}
  const [picked, setPicked] = useState(null)           // tools step → setup
  const [setup, setSetup] = useState({ result: null, running: false })
  const [scanned, setScanned] = useState(false)
  const [arch, setArch] = useState({ result: null, saved: false })

  const load = () => getJSON('app/onboard/state').then((s) => { setSt(s); setRows(repoRows(s)) }, (e) => setLoadError(e.message))
  useEffect(() => { load() }, [])
  const loadTools = () => getJSON('app/onboard/tools').then((x) => {
    setTools(x)
    setPicked((p) => p ?? defaultPicks(x.rows))
    return x
  }, (e) => setError(say(e)))
  useEffect(() => { if (st && !tools && ['tools', 'setup'].includes(st.step)) loadTools() }, [st?.step])

  if (loadError) return (
    <section className="view ob"><p className="error" role="alert">{t('obLoadFailed')} {loadError}</p>
      <button type="button" className="small" onClick={() => { setLoadError(''); load() }}>{t('obRetry')}</button></section>
  )
  if (!st) return <section className="view ob"><div className="co-esqueleto skeleton" aria-busy="true" /></section>

  const step = st.done ? 'intro' : st.steps[stepIndex(st)]
  const go = async (id, before) => {
    setMoving(true)
    setError('')
    try {
      if (before) await before()
      setSt(await postJSON('app/onboard/step', { id }))
      window.scrollTo?.(0, 0)
    } catch (e) { setError(say(e)) } finally { setMoving(false) }
  }
  const next = nextStep({ ...st, step })
  const prev = step === 'intro' ? null : prevStep({ ...st, step })      // Ready closes the first run: no way back into it
  const saveRepos = async () => setSt(await postJSON('app/onboard/repos', { repos: repoBody(rows) }))
  // new picks make a finished setup stale: entering the step again installs them
  const pickTools = (p) => { setPicked(p); setSetup({ result: null, running: false }) }
  const data = { repos: { kind: st.kind, rows }, tools: { rows: tools?.rows, picked },
    setup: { result: setup.result, requiredOk: tools?.required_ok }, arch: { saved: arch.saved } }[step]
  const check = canContinue(step, data)
  const waiting = moving || (step === 'tools' && !tools) || (step === 'setup' && (setup.running || !setup.result))
  const skip = () => go(next)

  const panel = {
    repos: <Repos rows={rows} setRows={setRows} />,
    tools: <Tools tools={tools} picked={picked || []} setPicked={pickTools} />,
    setup: <Setup tools={tools} picked={picked} repos={st.repos} state={setup} setState={setSetup} reloadTools={loadTools} />,
    stack: <Stack scanned={scanned} setScanned={setScanned} />,
    arch: <Arch state={arch} setState={setArch} onSkip={skip} />,
    intro: <Intro closed={st.done} />,
  }[step]

  return (
    <section className="view ob">
      <div className="ob-head"><span className="ob-brand">camarón · {st.name}</span>
        <span className="muted small">{t('obPreparing')}</span></div>
      <ol className="ob-steps" aria-label={t('obPreparing')}>
        {st.steps.map((s, i) => {
          const at = st.steps.indexOf(step)
          const cls = st.done || i < at ? 'done' : i === at ? 'current' : 'future'
          return <li key={s} className={cls} aria-current={cls === 'current' ? 'step' : undefined}>
            {cls === 'done' ? '✔' : `${i + 1}.`} {t(STEP_KEYS[s])}</li>
        })}
      </ol>
      <div className="ob-panel" key={step}>{panel}</div>
      {error ? <p className="error" role="alert">{error}</p> : null}
      {step === 'intro' ? null : <div className="ob-foot">
        {prev ? <button type="button" className="ghost" disabled={moving || setup.running} onClick={() => go(prev)}>{t('obBack')}</button> : <span />}
        <div className="ob-next">
          {!check.ok && !waiting ? <span className="muted small" role="status">{t(check.reason)}</span> : null}
          <button type="button" disabled={!check.ok || waiting}
                  onClick={() => go(next, step === 'repos' ? saveRepos : null)}>{t('obContinue')}</button>
        </div>
      </div>}
    </section>
  )
}

// ---------- 1. Repos: the detected ones ticked, code repos added by URL, name and branch (as add_url does) ----------
function Repos({ rows, setRows }) {
  const [url, setUrl] = useState('')
  const [name, setName] = useState(null)              // null: the URL's, until the person types one
  const [branch, setBranch] = useState('main')
  const [error, setError] = useState('')
  const add = (e) => {
    e.preventDefault()
    const r = repoFromUrl(url, name ?? '', branch)
    if (!r) return setError(t('obErrUrl'))
    if (rows.some((x) => x.name === r.name)) return setError(t('obErrDuplicate'))
    setRows([...rows, r])
    setUrl('')
    setName(null)
    setBranch('main')
    setError('')
  }
  const edit = (n, patch) => setRows(rows.map((r) => (r.name === n ? { ...r, ...patch } : r)))
  return (
    <>
      <h2>{t('obReposTitle')}</h2>
      <p className="lede">{t('obReposLead')}</p>
      <ul className="ob-rows">
        {rows.map((r) => (
          <li key={r.name}><div className="ob-row">
            <input type="checkbox" id={`ob-repo-${r.name}`} checked={r.checked} onChange={() => edit(r.name, { checked: !r.checked })} />
            <label htmlFor={`ob-repo-${r.name}`}><b>{r.name}</b>
              <code className="muted small">{r.kind} · {r.branch || 'main'} · {r.url || t('obLocal')}</code></label>
            {r.added ? <input className="co-input ob-branch" value={r.branch} aria-label={fill(t('obBranchOf'), { repo: r.name })}
                              placeholder="main" onChange={(e) => edit(r.name, { branch: e.target.value })} /> : null}
          </div></li>))}
      </ul>
      <form className="ob-add" onSubmit={add}>
        <input className="co-input" value={url} aria-label={t('obAddLabel')} placeholder="https://gitlab.com/shop/payments.git"
               onChange={(e) => { setUrl(e.target.value); setError('') }} />
        {url.trim() ? <>
          <input className="co-input ob-short" value={name ?? urlName(url)} aria-label={t('obAddName')} placeholder={t('obAddName')}
                 onChange={(e) => setName(e.target.value)} />
          <input className="co-input ob-short" value={branch} aria-label={t('obAddBranch')} placeholder="main"
                 onChange={(e) => setBranch(e.target.value)} />
        </> : null}
        <button type="submit" className="ghost small" disabled={!url.trim()}>{t('obAddRepo')}</button>
      </form>
      {error ? <p className="error" role="alert">{error}</p> : null}
    </>
  )
}

// ---------- 2. Tools: what this machine has; required ones ticked and locked ----------
const KIND = { t_required: 'obKindRequired', t_optional: 'obKindOptional', t_kit: 'obKindKit' }

function Tools({ tools, picked, setPicked }) {
  const toggle = (id) => setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id])
  return (
    <>
      <h2>{t('obToolsTitle')}</h2>
      <p className="lede">{t('obToolsLead')}</p>
      {!tools ? <div className="co-esqueleto skeleton" aria-busy="true" /> : (
        <ul className="ob-rows">
          {tools.rows.map((r) => {
            const locked = r.kind === 't_required'
            return (
              <li key={r.id} className="ob-row">
                <span className={r.ok ? 'ok' : 'warn'} aria-label={t(r.ok ? 'obInstalled' : 'obMissing')}>{r.ok ? '✔' : '⚠'}</span>
                <span><b>{r.id}</b><code className="muted small">{t(KIND[r.kind])} · {r.label}{r.found ? ` · ${r.found}` : ''}</code>
                  {r.note ? <span className="muted small">{r.note}</span> : null}</span>
                {r.ok ? null : <input type="checkbox" className="ob-pick" checked={locked || picked.includes(r.id)} disabled={locked}
                                      aria-label={fill(t('obInstallIt'), { id: r.id })} onChange={() => toggle(r.id)} />}
              </li>
            )
          })}
        </ul>
      )}
    </>
  )
}

// ---------- 3. Install: one job (install the picked tools, then setup), its bar, its log, Cancel ----------
function Setup({ tools, picked, repos, state, setState, reloadTools }) {
  const j = useJob(onboardJob('setup', () => setupChoice(tools.rows, picked || defaultPicks(tools.rows))))
  async function run() {
    setState({ result: null, running: true })
    const end = await j.start()
    await reloadTools()                                      // what is installed now, and whether required ones are
    setState({ result: end?.result || { ok: false }, running: false })
  }
  useEffect(() => { if (tools && !state.result && !state.running) run() }, [!!tools])
  const lines = j.job?.lines || []
  const bar = progress(lines)
  const r = state.result
  const missing = r?.missing || []
  const firstUrl = (repos || []).find((x) => x.name === missing[0])?.url
  return (
    <>
      <h2>{t('obSetupTitle')}</h2>
      <p className="lede" role="status">
        {[bar.total ? fill(t('obSetupStep'), bar) : '', j.running ? bar.current || t('obStarting') : r?.ok ? t('obSetupOk') : '']
          .filter(Boolean).join(' · ')}</p>
      <div className="mc-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={r?.ok ? 100 : bar.pct}>
        <span style={{ transform: `scaleX(${(r?.ok ? 100 : bar.pct) / 100})` }} />
      </div>
      {lines.length ? <pre className="joblog tw-log ob-log" aria-label={t('twLog')}>
        {lines.map((l) => l.replace(/^\[\d+\/\d+\]\s*/, '')).join('\n')}</pre> : null}
      {j.running ? <p className="muted small">{t('obJoke')}</p> : null}
      {j.error ? <p className="error" role="alert">{say({ message: j.error })}</p> : null}
      {r && !j.running ? (
        <>
          {r.cancelled ? <p className="aviso small">{t('obCancelled')}</p> : null}
          {r.failed?.length ? <div className="aviso small"><p>{t('obFailedTools')}</p>
            <ul>{manualHints(tools?.rows, r.failed).map((x) => <li key={x.id}><b>{x.id}</b>{x.hint ? ` · ${x.hint}` : ''}</li>)}</ul></div> : null}
          {missing.length ? <>
            <p className="aviso small">{fill(t('obMissingRepos'), { repos: missing.join(', ') })}</p>
            <div className="tw-list"><Tokens host={hostOf(firstUrl)} /></div>
          </> : null}
        </>
      ) : null}
      <div className="row ob-actions">
        {j.running ? <button type="button" className="ghost small" onClick={j.stop}>{t('obCancel')}</button> : null}
        {r && !j.running && (!r.ok || missing.length || r.failed?.length)
          ? <button type="button" className="small" onClick={run}>{t('obRetry')}</button> : null}
      </div>
    </>
  )
}

// ---------- 4. Stack: what the manifests say per repo, editable ----------
function Stack({ scanned, setScanned }) {
  const scan = useJob(onboardJob('scan'))
  const [rows, setRows] = useState(null)
  const [edit, setEdit] = useState(null)               // {repo, text}
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => getJSON('app/onboard/stack').then(setRows, (e) => setError(say(e)))
  useEffect(() => {
    if (scanned) { load(); return }
    scan.start().then((end) => { setScanned(true); load(); if (end?.status !== 'done') setError(t('obScanFailed')) })
  }, [])
  async function save() {
    setBusy(true)
    setError('')
    try { setRows(await postJSON('app/onboard/stack', { repo: edit.repo, text: edit.text.trim() })); setEdit(null) }
    catch (e) { setError(say(e)) } finally { setBusy(false) }
  }
  const names = Object.keys(rows || {})
  return (
    <>
      <h2>{t('obStackTitle')}</h2>
      <p className="lede">{t('obStackLead')}</p>
      {scan.running ? <p className="muted small" role="status">{t('obScanning')}</p> : null}
      {!rows ? <div className="co-esqueleto skeleton" aria-busy="true" /> : !names.length ? <p className="muted">{t('obNoRepos')}</p> : (
        <ul className="ob-rows">
          {names.map((n) => (
            <li key={n} className="ob-row">
              <b>{n}</b>
              {edit?.repo === n ? (
                <form className="ob-add" onSubmit={(e) => { e.preventDefault(); save() }}>
                  <input className="co-input" value={edit.text} autoFocus aria-label={fill(t('obEdit'), { repo: n })}
                         placeholder={rows[n].detected_stack} onChange={(e) => setEdit({ repo: n, text: e.target.value })} />
                  <button type="submit" className="small" disabled={busy}>{t('obSave')}</button>
                  <button type="button" className="ghost small" disabled={busy} onClick={() => setEdit(null)}>{t('obCancelEdit')}</button>
                </form>
              ) : (
                <>
                  <span>{rows[n].stack || '—'}{rows[n].stack !== rows[n].detected_stack && rows[n].detected_stack
                    ? <span className="muted small">{fill(t('obDetected'), { s: rows[n].detected_stack })}</span> : null}</span>
                  <button type="button" className="ghost icon small" aria-label={fill(t('obEdit'), { repo: n })} title={fill(t('obEdit'), { repo: n })}
                          onClick={() => setEdit({ repo: n, text: rows[n].stack || '' })}>✎</button>
                </>
              )}
            </li>))}
        </ul>
      )}
      {error ? <p className="error" role="alert">{error}</p> : null}
      {scan.job?.lines.length ? (
        <details className="tw-out"><summary className="muted small">{t('twLog')}</summary>
          <pre className="joblog tw-log">{scan.job.lines.join('\n')}</pre></details>
      ) : null}
    </>
  )
}

// ---------- 5. Architecture: the static C4 draft (R4: repos, datastores + brokers, relations) ----------
function Arch({ state, setState, onSkip }) {
  const draft = useJob(onboardJob('arch', () => ({ action: 'draft' })))
  const [agents, setAgents] = useState(null)
  const [agent, setAgent] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const [warn, setWarn] = useState('')
  const asked = useRef(null)                           // the save waiting for "replace it?"
  const dialog = useRef(null)
  async function make() {
    setError('')
    const end = await draft.start()
    if (end?.status === 'done') setState((s) => ({ ...s, result: end.result }))
  }
  useEffect(() => {
    if (!state.result) make()
    getJSON('app/agents').then((a) => {
      setAgents(a.agents)
      setAgent(a.last && a.agents.some((x) => x.id === a.last) ? a.last : a.agents[0]?.id || '')
    }, () => setAgents([]))
  }, [])
  async function save(action, overwrite = false) {
    setBusy(true)
    setError('')
    try {
      const res = await postJSON('app/onboard/arch', { action, overwrite, ...(action === 'save-ai' ? { agent, lang: lang() } : {}) })
      if (res.exists) { asked.current = action; dialog.current.showModal(); return }
      // the agent could not open (no terminal here, or that CLI is gone): the draft is saved all the same
      if (res.launched === false) setWarn(res.error === 'terminal' ? fill(t('obNoTerminal'), { prompt: res.prompt || '' }) : t('obAgentMissing'))
      setDone(action === 'save-ai' && res.launched !== false ? t('obAiOpened') : t('obSaved'))
      setState((s) => ({ ...s, saved: true }))
    } catch (e) { setError(say(e)) } finally { setBusy(false) }
  }
  const r = state.result
  const off = busy || draft.running || !r
  const tile = (n, label) => <div className="tile"><b>{n}</b><span className="tile-label">{label}</span></div>
  return (
    <>
      <h2>{t('obArchTitle')}</h2>
      <p className="lede">{t('obArchLead')}</p>
      {draft.running ? <p className="muted small" role="status">{t('obDrafting')}</p> : null}
      {draft.error ? (
        <p className="error" role="alert">{say({ message: draft.error })} <button type="button" className="ghost small" onClick={make}>{t('obRetry')}</button></p>
      ) : null}
      {!r && !draft.running && draft.job ? (
        <p className="error" role="alert">{t('obDraftFailed')} <button type="button" className="ghost small" onClick={make}>{t('obRetry')}</button></p>
      ) : null}
      {r ? (
        <>
          <div className="tiles">
            {tile(r.repos.length, t('obTileRepos'))}
            {tile(r.datastores.length + r.brokers.length, t('obTileData'))}
            {tile(r.relations.length, t('obTileRelations'))}
          </div>
          {r.valid === false ? <p className="aviso small">{t('obInvalid')}</p> : null}
        </>
      ) : null}
      <div className="row ob-actions">
        <button type="button" disabled={off || state.saved} onClick={() => save('save')}>{t('obSaveDraft')}</button>
        <button type="button" className="ghost" disabled={!r?.html || draft.running}
                onClick={() => APP?.openExternal(location.origin + '/firstlook')}>{t('obViewDiagram')}</button>
        {agents?.length ? (
          <>
            <select className="co-input" value={agent} onChange={(e) => setAgent(e.target.value)} aria-label={t('pAgent')}>
              {agents.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            </select>
            <button type="button" className="ghost" disabled={off || state.saved || !agent} onClick={() => save('save-ai')}>{t('obSaveAi')}</button>
          </>
        ) : null}
        {!state.saved ? <button type="button" className="ghost" disabled={busy} onClick={onSkip}>{t('obSkip')}</button> : null}
      </div>
      {agents && !agents.length ? <p className="muted small">{t('pNoAgent')}</p> : null}
      {done ? <p className="ok small" role="status">{done}</p> : null}
      {warn ? <p className="aviso small">{warn}</p> : null}
      {error ? <p className="error" role="alert">{error}</p> : null}
      {draft.job?.lines.length ? (
        <details className="tw-out" open={!r && !draft.running}><summary className="muted small">{t('twLog')}</summary>
          <pre className="joblog tw-log">{draft.job.lines.join('\n')}</pre></details>
      ) : null}
      <dialog ref={dialog} className="tw-dialog">
        <h2>{t('obOverwriteTitle')}</h2>
        <p>{t('obOverwriteText')}</p>
        <div className="row">
          <button type="button" className="ghost small" onClick={() => dialog.current.close()}>{t('obOverwriteNo')}</button>
          <button type="button" className="small" onClick={() => { dialog.current.close(); save(asked.current, true) }}>{t('obOverwriteGo')}</button>
        </div>
      </dialog>
    </>
  )
}

// ---------- 6. Ready: the first run closes (firstrun.json done, a checkpoint commit) ----------
function Intro({ closed: already }) {
  const [error, setError] = useState('')
  const closed = useRef(already)                      // a first run finished earlier is not closed (and committed) again
  useEffect(() => {
    if (closed.current) return
    closed.current = true
    postJSON('app/onboard/done', {}).catch((e) => setError(say(e)))
  }, [])
  return (
    <div className="ob-done">
      <span className="ob-check ok" aria-hidden="true">✔</span>
      <h2>{t('obDoneTitle')}</h2>
      <p className="lede">{t('obDoneLead')}</p>
      <div className="row ob-actions">
        <button type="button" onClick={() => { location.hash = '#/next' }}>{t('obGoNext')}</button>
        <button type="button" className="ghost" onClick={() => APP?.openExternal(portalUrl(location.origin, location.hash))}>{t('obViewPortal')}</button>
      </div>
      {error ? <p className="error" role="alert">{error}</p> : null}
    </div>
  )
}
