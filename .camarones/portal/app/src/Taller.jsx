import { useEffect, useRef, useState } from 'react'
import { getJSON, postJSON, streamEvents } from './api.js'
import { fields, toArgs } from './cmdform.js'
import { lang, t } from './i18n.js'

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

function Command({ entry }) {
  const fs = fields(entry)
  const [values, setValues] = useState(() => Object.fromEntries(fs.map((f) => [f.dest, f.initial])))
  const [job, setJob] = useState(null)          // {id, status, rc, lines[]}
  const [error, setError] = useState('')
  const dialog = useRef(null)
  const abort = useRef(null)
  useEffect(() => () => abort.current?.abort(), [])
  const running = job?.status === 'running'
  const asks = !!(entry.confirm || entry.destructive)

  async function start(confirmed) {
    setError('')
    try {
      const j = await postJSON('app/cmd', { cmd: entry.name, args: toArgs(entry, values), confirmed })
      setJob({ id: j.id, status: 'running', lines: [] })
      abort.current = new AbortController()
      await streamEvents(`app/jobs/${j.id}/events`, (ev) => {
        if (ev.type === 'line') setJob((cur) => ({ ...cur, lines: [...cur.lines, ev.text] }))
        else if (ev.type === 'end') setJob((cur) => ({ ...cur, status: ev.status, rc: ev.rc }))
      }, abort.current.signal)
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message)
    }
  }
  async function stop() {
    try { await postJSON(`app/jobs/${job.id}/cancel`, {}) } catch (e) { setError(e.message) }
  }
  const title = entry[lang()] || entry.en
  const status = !job ? null : running ? t('twRunning') : job.status === 'done' ? t('twDone')
    : job.rc == null ? t('twStopped') : t('twFailed').replace('{rc}', job.rc)
  return (
    <div className={`co-card tw-cmd ${entry.destructive ? 'destructive' : ''}`}>
      <div className="tw-head">
        <b>{title}</b> <code className="muted">camaron {entry.name}</code>
        {entry.ai ? <span className="co-chip">{t('twAi')}</span> : null}
        {entry.destructive ? <span className="co-chip warn">{t('twDestructive')}</span> : null}
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
