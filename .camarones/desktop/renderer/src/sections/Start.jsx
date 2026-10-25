import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Skeleton } from '@camaron/ui'
import { portalUrl } from '../docs.js'
import { useAgents, useJob } from '../hooks.js'
import { STEP_KEYS, alreadyDone, canContinue, continueVariant, defaultPicks, errorText, hostOf, manualHints, nextStep, prevStep,
  progressOf, repoBody, repoFromUrl, repoRows, reposChanged, setupChoice, stepIndex, urlName } from '../onboarding.js'
import { AgentPicker, Failed } from '../parts.jsx'
import { Tokens } from './Machine.jsx'
import { lang, t } from '../i18n.js'

// The first run in the project window (#/start, sketch C): one step per screen, Back / Continue, the position saved
// on the server (firstrun.json, shared with the CLI wizard) so closing the window never loses it. The work is
// lib/onboard.py's, through /api/app/onboard; the step model is onboarding.js. App.jsx draws it full width.

// A rejection said in the person's language: a known code or an unreachable server by its own sentence, anything else
// as the server said it.
const say = (e) => {
  const x = errorText(e)
  return x.detail ? `${t(x.key)} ${x.detail}` : t(x.key)
}
const toTop = () => document.getElementById('main')?.scrollTo?.(0, 0)

const icon = { className: 'ob-icon', viewBox: '0 0 24 24', 'aria-hidden': true, fill: 'none', stroke: 'currentColor',
  strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }
const ExternalIcon = () => (
  <svg {...icon}><path d="M15 3h6v6" /><path d="M10 14 21 3" /><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /></svg>
)
const PencilIcon = () => (
  <svg {...icon}><path d="M21.17 6.81a2.83 2.83 0 0 0-4-4L3.84 16.17a2 2 0 0 0-.5.83l-1.32 4.35a.5.5 0 0 0 .62.62l4.35-1.32a2 2 0 0 0 .83-.5Z" /></svg>
)

// The row of steps: the finished ones ticked, the current one marked, the rest numbered.
export function Steps({ steps, at, done }) {
  return (
    <ol className="ob-steps" aria-label={t('obPreparing')}>
      {steps.map((s, i) => {
        const cls = done || i < at ? 'done' : i === at ? 'current' : 'future'
        return <li key={s} className={cls} aria-current={cls === 'current' ? 'step' : undefined}>
          {`${cls === 'done' ? '✔' : `${i + 1}.`} ${t(STEP_KEYS[s])}`}</li>
      })}
    </ol>
  )
}

export default function Start({ srv, jobs, app }) {
  const [st, setSt] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [error, setError] = useState('')
  const [moving, setMoving] = useState(false)
  const [rows, setRows] = useState([])                 // repos step
  const [tools, setTools] = useState(null)             // GET tools: {rows, required_ok}
  const [toolsError, setToolsError] = useState('')     // that read failed: the tools and install steps offer it again
  const [picked, setPicked] = useState(null)           // tools step → setup
  const [setup, setSetup] = useState({ result: null, running: false })
  const [scanned, setScanned] = useState(false)
  const [arch, setArch] = useState({ result: null, saved: false })

  const load = () => srv.get('app/onboard/state').then((s) => { setSt(s); setRows(repoRows(s)) }, (e) => setLoadError(e.message))
  useEffect(() => { load() }, [])
  const loadTools = () => srv.get('app/onboard/tools').then((x) => {
    setToolsError('')
    setTools(x)
    setPicked((p) => p ?? defaultPicks(x.rows))
    return x
  }, (e) => setToolsError(say(e)))
  useEffect(() => { if (st && !tools && ['tools', 'setup'].includes(st.step)) loadTools() }, [st?.step])

  if (loadError) return (
    <div className="dk-page ob"><Failed title={t('obLoadFailed')} detail={loadError} onRetry={() => { setLoadError(''); load() }} /></div>
  )
  if (!st) return <div className="dk-page ob"><Skeleton lines={5} /></div>

  const step = st.done ? 'intro' : st.steps[stepIndex(st)]
  const go = async (id, before) => {
    setMoving(true)
    setError('')
    try {
      if (before) await before()
      setSt(await srv.post('app/onboard/step', { id }))
      toTop()
    } catch (e) { setError(say(e)) } finally { setMoving(false) }
  }
  const next = nextStep({ ...st, step })
  const prev = step === 'intro' ? null : prevStep({ ...st, step })      // Ready closes the first run: no way back into it
  // a changed list makes a finished setup (its clones) and the stack scan stale: the next visit runs them again
  const saveRepos = async () => {
    const body = repoBody(rows)
    const changed = reposChanged(st.repos, body)
    setSt(await srv.post('app/onboard/repos', { repos: body }))
    if (changed) { setSetup({ result: null, running: false }); setScanned(false) }
  }
  // new picks make a finished setup stale: entering the step again installs them
  const pickTools = (p) => { setPicked(p); setSetup({ result: null, running: false }) }
  const data = { repos: { kind: st.kind, rows }, tools: { rows: tools?.rows, picked },
    setup: { result: setup.result, requiredOk: tools?.required_ok }, arch: { saved: arch.saved } }[step]
  const check = canContinue(step, data)
  const waiting = moving || (step === 'tools' && !tools) || (step === 'setup' && (setup.running || !setup.result))
  const p = { srv, jobs, app }

  const panel = {
    repos: <Repos rows={rows} setRows={setRows} />,
    tools: <Tools tools={tools} picked={picked || []} setPicked={pickTools} error={toolsError} onRetry={loadTools} />,
    setup: <Setup {...p} tools={tools} picked={picked} repos={st.repos} state={setup} setState={setSetup} error={toolsError}
      reloadTools={loadTools} />,
    stack: <Stack {...p} scanned={scanned} setScanned={setScanned} />,
    arch: <Arch {...p} state={arch} setState={setArch} onSkip={() => go(next)} />,
    intro: <Intro {...p} closed={st.done} />,
  }[step]

  return (
    <div className="dk-page ob">
      <Steps steps={st.steps} at={st.steps.indexOf(step)} done={st.done} />
      <div className="ob-panel" key={step}>{panel}</div>
      {error ? <Aviso tone="error" title={error} /> : null}
      {step === 'intro' ? null : (
        <div className="ob-foot">
          {prev ? <Button variant="ghost" disabled={moving || setup.running} onClick={() => go(prev)}>{t('obBack')}</Button> : <span />}
          <div className="ob-next">
            {!check.ok && !waiting ? <span className="muted small" role="status">{t(check.reason)}</span> : null}
            <Button variant={continueVariant(step, data)} disabled={!check.ok || waiting}
              onClick={() => go(next, step === 'repos' ? saveRepos : null)}>{t('obContinue')}</Button>
          </div>
        </div>
      )}
    </div>
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
      <p className="dk-lede">{t('obReposLead')}</p>
      {rows.length ? (
        <ul className="dk-units">
          {rows.map((r) => (
            <li key={r.name} className="dk-unit">
              <label className="dk-check dk-unit-main ob-row">
                <input type="checkbox" checked={r.checked} onChange={() => edit(r.name, { checked: !r.checked })} />
                <span className="ob-row-text"><b>{r.name}</b>
                  <code className="muted small dk-mono">{r.kind} · {r.branch || 'main'} · {r.url || t('obLocal')}</code></span>
              </label>
              {r.added ? <input className="cu-input ob-short" value={r.branch} aria-label={t('obBranchOf', { repo: r.name })}
                                placeholder="main" onChange={(e) => edit(r.name, { branch: e.target.value })} /> : null}
            </li>))}
        </ul>
      ) : null}
      <form className="ob-add" onSubmit={add}>
        <input className="cu-input" value={url} aria-label={t('obAddLabel')} placeholder="https://gitlab.com/shop/payments.git"
               onChange={(e) => { setUrl(e.target.value); setError('') }} />
        {url.trim() ? <>
          <input className="cu-input ob-short" value={name ?? urlName(url)} aria-label={t('obAddName')} placeholder={t('obAddName')}
                 onChange={(e) => setName(e.target.value)} />
          <input className="cu-input ob-short" value={branch} aria-label={t('obAddBranch')} placeholder="main"
                 onChange={(e) => setBranch(e.target.value)} />
        </> : null}
        <Button type="submit" disabled={!url.trim()}>{t('obAddRepo')}</Button>
      </form>
      {error ? <Aviso tone="error" title={error} /> : null}
    </>
  )
}

// ---------- 2. Tools: what this machine has; required ones ticked and locked ----------
const KIND = { t_required: 'obKindRequired', t_optional: 'obKindOptional', t_kit: 'obKindKit' }

// A failed tools read: what, the server's message, and the read again (join starts here, with no Back).
const ToolsFailed = ({ error, onRetry }) => (
  <Aviso tone="error" title={t('obToolsFailed')} detail={error}
    action={<Button size="sm" onClick={() => onRetry?.()}>{t('obRetry')}</Button>} />
)

export function Tools({ tools, picked, setPicked, error, onRetry }) {
  const toggle = (id) => setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id])
  return (
    <>
      <h2>{t('obToolsTitle')}</h2>
      <p className="dk-lede">{t('obToolsLead')}</p>
      {!tools ? (error ? <ToolsFailed error={error} onRetry={onRetry} /> : <Skeleton lines={6} />) : (
        <ul className="dk-units">
          {tools.rows.map((r) => {
            const locked = r.kind === 't_required'
            return (
              <li key={r.id} className="dk-unit">
                <span className={'ob-glyph ' + (r.ok ? 'ob-ok' : 'ob-warn')} role="img" aria-label={t(r.ok ? 'obInstalled' : 'obMissing')}>{r.ok ? '✔' : '⚠'}</span>
                <span className="dk-unit-main"><b>{r.id}</b>
                  <code className="muted small dk-mono">{t(KIND[r.kind])} · {r.label}{r.found ? ` · ${r.found}` : ''}</code>
                  {r.note ? <span className="muted small">{r.note}</span> : null}</span>
                {r.ok ? null : (
                  <label className="dk-check"><input type="checkbox" checked={locked || picked.includes(r.id)} disabled={locked}
                    aria-label={t('obInstallIt', { id: r.id })} onChange={() => toggle(r.id)} /></label>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </>
  )
}

// ---------- 3. Install: one job (install the picked tools, then setup), its bar, its log, Cancel ----------
export function Setup({ srv, jobs, tools, picked, repos, state, setState, error, reloadTools }) {
  const j = useJob(srv, jobs, (body) => srv.post('app/onboard/setup', body))
  async function run() {
    setState({ result: null, running: true })
    const end = await j.run(setupChoice(tools.rows, picked || defaultPicks(tools.rows)))
    await reloadTools()                                      // what is installed now, and whether required ones are
    setState({ result: end?.result || { ok: false }, running: false })
  }
  useEffect(() => { if (tools && !state.result && !state.running) run() }, [!!tools])
  const lines = j.job?.lines || []
  const bar = progressOf(lines)
  const r = state.result
  const missing = r?.missing || []
  const firstUrl = (repos || []).find((x) => x.name === missing[0])?.url
  const pct = r?.ok ? 100 : bar.pct
  return (
    <>
      <h2>{t('obSetupTitle')}</h2>
      <p className="dk-lede" role="status">
        {[bar.total ? t('obSetupStep', bar) : '', j.running ? bar.current || t('obStarting') : r?.ok ? t('obSetupOk') : '']
          .filter(Boolean).join(' · ')}</p>
      {!tools && error ? <ToolsFailed error={error} onRetry={reloadTools} /> : null}
      <progress className="dk-progress" value={pct} max={100} aria-label={t('obSetupTitle')} />
      {lines.length ? <pre className="dk-log ob-log" aria-label={t('cmds.output')}>
        {lines.map((l) => l.replace(/^\[\d+\/\d+\]\s*/, '')).join('\n')}</pre> : null}
      {j.running ? <p className="muted small">{t('obJoke')}</p> : null}
      {j.error ? <Aviso tone="error" title={say({ message: j.error })} /> : null}
      {r && !j.running ? (
        <>
          {r.cancelled ? <Aviso tone="warn" title={t('obCancelled')} /> : null}
          {r.failed?.length ? (
            <Aviso tone="warn" title={t('obFailedTools')}>
              <ul className="ob-hints">{manualHints(tools?.rows, r.failed).map((x) => <li key={x.id}><b>{x.id}</b>{x.hint ? ` · ${x.hint}` : ''}</li>)}</ul>
            </Aviso>
          ) : null}
          {missing.length ? <>
            <Aviso tone="warn" title={t('obMissingRepos', { repos: missing.join(', ') })} />
            <Tokens srv={srv} host={hostOf(firstUrl)} />
          </> : null}
        </>
      ) : null}
      <div className="row">
        {j.running ? <Button size="sm" variant="ghost" onClick={j.stop}>{t('obCancel')}</Button> : null}
        {r && !j.running && (!r.ok || missing.length || r.failed?.length)
          ? <Button size="sm" onClick={run}>{t('obRetry')}</Button> : null}
      </div>
    </>
  )
}

// ---------- 4. Stack: what the manifests say per repo, editable ----------
function Stack({ srv, jobs, scanned, setScanned }) {
  const scan = useJob(srv, jobs, () => srv.post('app/onboard/scan', {}))
  const [rows, setRows] = useState(null)
  const [edit, setEdit] = useState(null)               // {repo, text}
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => srv.get('app/onboard/stack').then(setRows, (e) => setError(say(e)))
  useEffect(() => {
    if (scanned) { load(); return }
    scan.run().then((end) => { setScanned(true); load(); if (end?.status !== 'done') setError(t('obScanFailed')) })
  }, [])
  async function save() {
    setBusy(true)
    setError('')
    try { setRows(await srv.post('app/onboard/stack', { repo: edit.repo, text: edit.text.trim() })); setEdit(null) }
    catch (e) { setError(say(e)) } finally { setBusy(false) }
  }
  const names = Object.keys(rows || {})
  return (
    <>
      <h2>{t('obStackTitle')}</h2>
      <p className="dk-lede">{t('obStackLead')}</p>
      {scan.running ? <p className="muted small" role="status">{t('obScanning')}</p> : null}
      {!rows ? <Skeleton lines={3} /> : !names.length ? <p className="muted">{t('obNoRepos')}</p> : (
        <ul className="dk-units">
          {names.map((n) => (
            <li key={n} className="dk-unit">
              <b className="ob-repo">{n}</b>
              {edit?.repo === n ? (
                <form className="ob-add" onSubmit={(e) => { e.preventDefault(); save() }}>
                  <input className="cu-input" value={edit.text} autoFocus aria-label={t('obEdit', { repo: n })}
                         placeholder={rows[n].detected_stack} onChange={(e) => setEdit({ repo: n, text: e.target.value })} />
                  <Button type="submit" size="sm" disabled={busy}>{t('obSave')}</Button>
                  <Button size="sm" variant="ghost" disabled={busy} onClick={() => setEdit(null)}>{t('obCancelEdit')}</Button>
                </form>
              ) : (
                <>
                  <span className="dk-unit-main">{rows[n].stack || '—'}{rows[n].stack !== rows[n].detected_stack && rows[n].detected_stack
                    ? <span className="muted small">{t('obDetected', { s: rows[n].detected_stack })}</span> : null}</span>
                  <button type="button" className="dk-icon" aria-label={t('obEdit', { repo: n })} title={t('obEdit', { repo: n })}
                          onClick={() => setEdit({ repo: n, text: rows[n].stack || '' })}><PencilIcon /></button>
                </>
              )}
            </li>))}
        </ul>
      )}
      {error ? <Aviso tone="warn" title={error} /> : null}
      {scan.job?.lines.length ? (
        <details className="dk-out"><summary className="muted small">{t('cmds.output')}</summary>
          <pre className="dk-log ob-log">{scan.job.lines.join('\n')}</pre></details>
      ) : null}
    </>
  )
}

// ---------- 5. Architecture: the static C4 draft (R4: repos, datastores + brokers, relations) ----------
function Arch({ srv, jobs, app, state, setState, onSkip }) {
  const draft = useJob(srv, jobs, () => srv.post('app/onboard/arch', { action: 'draft' }))
  const a = useAgents(srv)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState('')
  const [warn, setWarn] = useState('')
  const asked = useRef(null)                           // the save waiting for "replace it?"
  const dialog = useRef(null)
  async function make() {
    setError('')
    const end = await draft.run()
    if (end?.status === 'done') setState((s) => ({ ...s, result: end.result }))
  }
  useEffect(() => { if (!state.result) make() }, [])
  async function save(action, overwrite = false) {
    setBusy(true)
    setError('')
    try {
      const res = await srv.post('app/onboard/arch', { action, overwrite, ...(action === 'save-ai' ? { agent: a.agent, lang: lang() } : {}) })
      if (res.exists) { asked.current = action; dialog.current.showModal(); return }
      // the agent could not open (no terminal here, or that CLI is gone): the draft is saved all the same
      if (res.launched === false) setWarn(res.error === 'terminal' ? t('obNoTerminal', { prompt: res.prompt || '' }) : t('obAgentMissing'))
      setDone(action === 'save-ai' && res.launched !== false ? t('obAiOpened') : t('obSaved'))
      setState((s) => ({ ...s, saved: true }))
    } catch (e) { setError(say(e)) } finally { setBusy(false) }
  }
  const r = state.result
  const off = busy || draft.running || !r
  const tile = (n, label) => (
    <Card className="dk-stat"><span className="eyebrow">{label}</span><b className="t-impact dk-stat-n">{n}</b></Card>
  )
  return (
    <>
      <h2>{t('obArchTitle')}</h2>
      <p className="dk-lede">{t('obArchLead')}</p>
      {draft.running ? <p className="muted small" role="status">{t('obDrafting')}</p> : null}
      {draft.error ? (
        <Aviso tone="error" title={say({ message: draft.error })} action={<Button size="sm" onClick={make}>{t('obRetry')}</Button>} />
      ) : null}
      {!r && !draft.running && draft.job ? (
        <Aviso tone="error" title={t('obDraftFailed')} action={<Button size="sm" onClick={make}>{t('obRetry')}</Button>} />
      ) : null}
      {r ? (
        <>
          <div className="dk-stats">
            {tile(r.repos.length, t('obTileRepos'))}
            {tile(r.datastores.length + r.brokers.length, t('obTileData'))}
            {tile(r.relations.length, t('obTileRelations'))}
          </div>
          {r.valid === false ? <Aviso tone="warn" title={t('obInvalid')} /> : null}
        </>
      ) : null}
      <div className="row">
        <Button variant="primary" disabled={off || state.saved} onClick={() => save('save')}>{t('obSaveDraft')}</Button>
        <Button disabled={!r?.html || draft.running} onClick={() => app.openExternal?.(location.origin + '/firstlook')}>
          {t('obViewDiagram')} <ExternalIcon /></Button>
        {a.agents?.length ? (
          <>
            <AgentPicker a={a} />
            <Button disabled={off || state.saved || !a.agent} onClick={() => save('save-ai')}>{t('obSaveAi')}</Button>
          </>
        ) : null}
        {!state.saved ? <Button variant="ghost" disabled={busy} onClick={onSkip}>{t('obSkip')}</Button> : null}
      </div>
      {a.agents && !a.agents.length ? <p className="muted small">{t('obNoAgents')}</p> : null}
      {done ? <p className="small ob-ok" role="status">{done}</p> : null}
      {warn ? <Aviso tone="warn" title={warn} /> : null}
      {error ? <Aviso tone="error" title={error} /> : null}
      {draft.job?.lines.length ? (
        <details className="dk-out" open={!r && !draft.running}><summary className="muted small">{t('cmds.output')}</summary>
          <pre className="dk-log ob-log">{draft.job.lines.join('\n')}</pre></details>
      ) : null}
      <dialog ref={dialog} className="dk-dialog">
        <h2>{t('obOverwriteTitle')}</h2>
        <p>{t('obOverwriteText')}</p>
        <div className="row">
          <Button variant="ghost" onClick={() => dialog.current.close()}>{t('obOverwriteNo')}</Button>
          <Button variant="primary" onClick={() => { dialog.current.close(); save(asked.current, true) }}>{t('obOverwriteGo')}</Button>
        </div>
      </dialog>
    </>
  )
}

// ---------- 6. Ready: the first run closes (firstrun.json done, a checkpoint commit); the window goes to the Summary ----------
function Intro({ srv, app, closed: already }) {
  const [error, setError] = useState('')
  const closed = useRef(already)                      // a first run finished earlier is not closed (and committed) again
  const close = () => {
    closed.current = true
    setError('')
    // refused with `done`: the CLI closed it meanwhile, which is what was asked
    srv.post('app/onboard/done', {}).catch((e) => { if (alreadyDone(e)) return; closed.current = false; setError(say(e)) })
  }
  useEffect(() => { if (!closed.current) close() }, [])
  return (
    <div className="ob-done">
      <svg {...icon} className="ob-check"><circle cx="12" cy="12" r="10" /><path d="m8 12 3 3 5-6" /></svg>
      <h2>{t('obDoneTitle')}</h2>
      <p className="dk-lede">{t('obDoneLead')}</p>
      <div className="row">
        <Button variant="primary" onClick={() => { location.hash = '#/summary' }}>{t('obGoNext')}</Button>
        <Button onClick={() => app.openExternal?.(portalUrl(location.origin, '#/'))}>{t('obViewPortal')} <ExternalIcon /></Button>
      </div>
      {error ? <Failed title={t('obDoneFailed')} detail={error} onRetry={close} /> : null}
    </div>
  )
}
