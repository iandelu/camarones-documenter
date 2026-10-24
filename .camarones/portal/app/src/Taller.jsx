import { useEffect, useRef, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import { fields, toArgs } from './cmdform.js'
import { lang, t } from './i18n.js'
import TallerPanels from './TallerPanels.jsx'
import { useJob } from './useJob.js'

// The Taller (desktop app only): every catalog command of one zone (lib/catalog.py), with a form read from the CLI's
// parser, its output live and its exit code. The server checks the arguments again and runs the real CLI.
let CATALOG = null
const catalog = () => (CATALOG ||= getJSON('app/catalog').catch((e) => { CATALOG = null; throw e }))

export default function Taller({ zone }) {
  const [cmds, setCmds] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    catalog().then((c) => setCmds(c.commands.filter((x) => x.zone === zone && x.verdict !== 'portal')),
      (e) => setError(e.message))
  }, [zone])
  const safe = (cmds || []).filter((c) => !c.destructive)
  const careful = (cmds || []).filter((c) => c.destructive)
  return (
    <section className="view taller">
      <h1>{t(`tw.${zone}`)}</h1>
      <p className="lede">{t(`twd.${zone}`)}</p>
      {error ? <p className="error" role="alert">{t('twCatalogFailed')} {error}</p> : null}
      {!cmds && !error ? <div className="co-esqueleto skeleton" aria-busy="true" /> : null}
      {zone === 'generate' && cmds ? <div className="tw-list"><UpdateSession /><PrPropose /></div> : null}
      {cmds ? <TallerPanels zone={zone} /> : null}
      <div className="tw-list">{safe.map((c) => <Command key={c.name} entry={c} />)}</div>
      {careful.length ? (
        <div className="tw-careful">
          <h2>{t('twCareful')}</h2>
          <p className="muted">{t('twCarefulLead')}</p>
          <div className="tw-list">{careful.map((c) => <Command key={c.name} entry={c} />)}</div>
        </div>
      ) : null}
    </section>
  )
}

function Field({ f, value, onChange, disabled }) {
  const id = `f-${f.dest}-${f.label}`
  const label = <label htmlFor={id}><code>{f.label}</code>{f.required ? <span className="muted"> · {t('twRequired')}</span> : null}</label>
  if (f.widget === 'check')
    return <div className="tw-field check"><input id={id} type="checkbox" checked={!!value} disabled={disabled}
      onChange={(e) => onChange(e.target.checked)} />{label}</div>
  return (
    <div className="tw-field">{label}
      {f.widget === 'select' ? (
        <select id={id} className="co-input" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          {f.options.map((o) => <option key={o} value={o}>{o === '' ? '—' : o}</option>)}
        </select>
      ) : (
        <input id={id} className="co-input" type={f.widget === 'number' ? 'number' : 'text'} value={value}
               required={f.required} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
      )}
    </div>
  )
}

// The docs update (what changed in the code since the docs were written) as an interactive agent session in its own
// terminal window, like the wizard's "update" (lib/agents.py).
function UpdateSession() {
  const [agents, setAgents] = useState(null)
  const [agent, setAgent] = useState('')
  const [state, setState] = useState(null)
  useEffect(() => {
    getJSON('app/agents').then((a) => {
      setAgents(a.agents)
      setAgent(a.last && a.agents.some((x) => x.id === a.last) ? a.last : a.agents[0]?.id || '')
    }, (e) => setState({ error: e.message }))
  }, [])
  async function open() {
    setState(null)
    try { await postJSON('app/agent', { unit: 'update', agent, lang: lang() }); setState({ ok: true }) } catch (e) { setState({ error: e.message }) }
  }
  return (
    <div className="co-card tw-cmd">
      <div className="tw-head"><b>{t('upTitle')}</b><span className="pill">{t('twAi')}</span></div>
      <p className="muted small">{t('upLead')}</p>
      {agents && !agents.length ? <p className="aviso small">{t('pNoAgent')}</p> : (
        <div className="row tw-actions">
          <select className="co-input" value={agent} onChange={(e) => setAgent(e.target.value)} aria-label={t('pAgent')}>
            {(agents || []).map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
          </select>
          <button type="button" className="small" disabled={!agent} onClick={open}>{t('pOpenTerminal')}</button>
        </div>
      )}
      {state?.ok ? <p className="muted small" role="status">{t('pOpened')}</p> : null}
      {state?.error ? <p className="error" role="alert">{state.error}</p> : null}
    </div>
  )
}

// `pr propose`: first what it would do (--dry-run), then, once the person agrees, the agent's docs branch and PR.
function PrPropose() {
  const [url, setUrl] = useState('')
  const [comment, setComment] = useState(false)
  const [planned, setPlanned] = useState('')
  const plan = useJob()
  const go = useJob()
  const dialog = useRef(null)
  const busy = plan.running || go.running
  useEffect(() => { if (plan.job?.status === 'done') setPlanned(url) }, [plan.job?.status])
  const args = (dry) => ({ action: 'propose', repo: url.trim(), lang: lang(), ...(dry ? { dry_run: true } : { comment }) })
  return (
    <div className="co-card tw-cmd">
      <div className="tw-head"><b>{t('prTitle')}</b> <code className="muted">camaron pr propose</code><span className="pill">{t('twAi')}</span></div>
      <p className="muted small">{t('prLead')}</p>
      <div className="tw-fields">
        <div className="tw-field"><label htmlFor="pr-url">{t('prUrl')}</label>
          <input id="pr-url" className="co-input" value={url} disabled={busy} placeholder="https://…/pull/123"
                 onChange={(e) => { setUrl(e.target.value); setPlanned('') }} /></div>
        <div className="tw-field check"><input id="pr-comment" type="checkbox" checked={comment} disabled={busy}
          onChange={(e) => setComment(e.target.checked)} /><label htmlFor="pr-comment">{t('prComment')}</label></div>
      </div>
      <div className="row tw-actions">
        {planned && planned === url
          ? <button type="button" className="small" disabled={busy} onClick={() => dialog.current.showModal()}>{t('prGo')}</button>
          : <button type="button" className="small" disabled={busy || !url.trim() || url.trim().startsWith('-')}
                    onClick={() => plan.start('pr', args(true))}>{t('prPlan')}</button>}
        {busy ? <button type="button" className="ghost small" onClick={() => (go.running ? go : plan).stop()}>{t('twStop')}</button> : null}
        {(go.status || plan.status) ? <span className={`tw-status ${(go.job || plan.job).status}`} role="status">{go.status || plan.status}</span> : null}
      </div>
      {plan.error || go.error ? <p className="error" role="alert">{go.error || plan.error}</p> : null}
      {(go.job || plan.job)?.lines.length ? <pre className="joblog tw-log">{(go.job || plan.job).lines.join('\n')}</pre> : null}
      <dialog ref={dialog} className="tw-dialog">
        <h2>{t('prConfirmTitle')}</h2>
        <p>{t('prConfirm')}</p>
        <div className="row">
          <button type="button" className="ghost small" onClick={() => dialog.current.close()}>{t('twConfirmNo')}</button>
          <button type="button" className="small" onClick={() => { dialog.current.close(); go.start('pr', args(false)) }}>{t('prGo')}</button>
        </div>
      </dialog>
    </div>
  )
}

function Command({ entry }) {
  const fs = fields(entry)
  const [values, setValues] = useState(() => Object.fromEntries(fs.map((f) => [f.dest, f.initial])))
  const { job, error, start: run, stop, running, status } = useJob()
  const dialog = useRef(null)
  const asks = !!(entry.confirm || entry.destructive)
  const start = (confirmed) => run(entry.name, toArgs(entry, values), confirmed)
  const title = entry[lang()] || entry.en
  return (
    <div className={`co-card tw-cmd ${entry.destructive ? 'destructive' : ''}`}>
      <div className="tw-head">
        <b>{title}</b> <code className="muted">camaron {entry.name}</code>
        {entry.ai ? <span className="pill">{t('twAi')}</span> : null}
        {entry.destructive ? <span className="pill warn">{t('twDestructive')}</span> : null}
      </div>
      {fs.length ? (
        <div className="tw-fields">{fs.map((f) => (
          <Field key={f.dest + f.label} f={f} value={values[f.dest]} disabled={running}
                 onChange={(v) => setValues((cur) => ({ ...cur, [f.dest]: v }))} />))}</div>
      ) : null}
      <div className="row tw-actions">
        {running
          ? <button type="button" className="ghost small" onClick={stop}>{t('twStop')}</button>
          : <button type="button" className={entry.destructive ? 'ghost small' : 'small'}
                    onClick={() => (asks ? dialog.current.showModal() : start(false))}>
              {t('twRun')} <code>{entry.name}</code></button>}
        {status ? <span className={`tw-status ${job.status}`} role="status">{status}</span> : null}
      </div>
      {error ? <p className="error" role="alert">{error}</p> : null}
      {job?.lines.length ? <pre className="joblog tw-log" aria-label={t('twLog')}>{job.lines.join('\n')}</pre> : null}
      {asks ? (
        <dialog ref={dialog} className="tw-dialog">
          <h2>{t('twConfirmTitle').replace('{cmd}', `camaron ${entry.name}`)}</h2>
          <p>{t('twConfirmText')}</p>
          <div className="row">
            <button type="button" className="ghost small" onClick={() => dialog.current.close()}>{t('twConfirmNo')}</button>
            <button type="button" className="small" onClick={() => { dialog.current.close(); start(true) }}>{t('twConfirmGo')}</button>
          </div>
        </dialog>
      ) : null}
    </div>
  )
}
