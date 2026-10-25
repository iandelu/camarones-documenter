import { useEffect, useRef, useState } from 'react'
import { Button, Card } from '@camaron/ui'
import { fields, toArgs } from '@camaron/ui/cmdform.js'
import { others } from '../catalog.js'
import { useCmd, useHash } from '../hooks.js'
import { Failed, Fold, JobOutput } from '../parts.jsx'
import { lang, t } from '../i18n.js'

// A section's "All commands", folded: the catalog commands of its zones that its panels do not already run, each with
// a form read from the CLI's parser. The server checks the arguments again and runs the real CLI. An address that
// names one of them (#/quality/radar, from the ⌘K palette) opens the fold on it.
let CATALOG = null
export const catalog = (srv) => (CATALOG ||= srv.get('app/catalog').catch((e) => { CATALOG = null; throw e }))

export default function Commands({ srv, jobs, section }) {
  const [cmds, setCmds] = useState(null)
  const [error, setError] = useState('')
  const want = (useHash().match(/^#\/[\w-]+\/([\w-]+)/) || [])[1]
  const load = () => catalog(srv).then((c) => { setCmds(c.commands); setError('') }, (e) => setError(e.message))
  useEffect(() => { load() }, [])
  const { safe, careful } = others(cmds, section)
  const named = [...safe, ...careful].some((c) => c.name === want)
  useEffect(() => {
    const card = named && document.getElementById(`cmd-${want}`)
    if (!card) return
    card.scrollIntoView({ block: 'center' })
    card.querySelector('input, select, button')?.focus({ preventScroll: true })
  }, [want, named])
  if (error) return <Failed title={t('cmds.failed')} detail={error} onRetry={load} />
  if (!safe.length && !careful.length) return null
  return (
    <Fold label={`${t('cmds.all')} (${safe.length + careful.length})`} open={named}>
      <div className="dk-cmds">{safe.map((c) => <Command key={c.name} entry={c} srv={srv} jobs={jobs} />)}</div>
      {careful.length ? (<>
        <h2 className="eyebrow dk-group">{t('cmds.careful')}</h2>
        <div className="dk-cmds">{careful.map((c) => <Command key={c.name} entry={c} srv={srv} jobs={jobs} />)}</div>
      </>) : null}
    </Fold>
  )
}

// The label of an argument in words, the flag beside it as a hint.
const argLabel = (f) => { const k = `arg.${f.dest}`; const l = t(k); return l === k ? f.label : l }

function Command({ entry, srv, jobs }) {
  const fs = fields(entry)
  const [values, setValues] = useState(() => Object.fromEntries(fs.map((f) => [f.dest, f.initial])))
  const c = useCmd(srv, jobs)
  const dialog = useRef(null)
  const asks = !!(entry.confirm || entry.destructive) && !(entry.reads && values[entry.reads])     // a dry run only reads
  const start = (confirmed) => c.run(entry.name, toArgs(entry, values), confirmed)
  return (
    <Card id={`cmd-${entry.name}`} className={'dk-cmd' + (entry.destructive ? ' careful' : '')}>
      <div className="row">
        <b>{entry[lang()] || entry.en}</b>
        <code className="muted small">camaron {entry.name}</code>
        {entry.ai ? <span className="cu-chip cu-chip--info">{t('cmds.ai')}</span> : null}
      </div>
      {fs.length ? (
        <div className="dk-fields">{fs.map((f) => (
          <ArgField key={f.dest + f.label} f={f} value={values[f.dest]} disabled={c.running}
                    onChange={(v) => setValues((cur) => ({ ...cur, [f.dest]: v }))} />))}</div>
      ) : null}
      <div className="row">
        <Button size="sm" variant={entry.destructive ? 'danger' : 'secondary'} disabled={c.running}
                onClick={() => (asks ? dialog.current.showModal() : start(false))}>{t('cmds.run')}</Button>
      </div>
      <JobOutput c={c} />
      {asks ? (
        <dialog ref={dialog} className="dk-dialog">
          <h2>{t('cmds.confirmTitle', { cmd: `camaron ${entry.name}` })}</h2>
          <p>{t('cmds.confirmText')}</p>
          <div className="row">
            <Button variant="ghost" onClick={() => dialog.current.close()}>{t('cancel')}</Button>
            <Button variant={entry.destructive ? 'danger' : 'primary'} onClick={() => { dialog.current.close(); start(true) }}>{t('cmds.confirmGo')}</Button>
          </div>
        </dialog>
      ) : null}
    </Card>
  )
}

function ArgField({ f, value, onChange, disabled }) {
  const id = `a-${f.dest}-${f.label}`
  const hint = <code className="cu-flag">{f.label}</code>
  if (f.widget === 'check') return (
    <label className="dk-check" htmlFor={id}>
      <input id={id} type="checkbox" checked={!!value} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      {argLabel(f)} {hint}
    </label>
  )
  return (
    <div className="cu-field">
      <label className="cu-field-label" htmlFor={id}>{argLabel(f)} {hint}{f.required ? <span className="muted"> · {t('cmds.required')}</span> : null}</label>
      {f.widget === 'select' ? (
        <select id={id} className="cu-input" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
          {f.options.map((o) => <option key={o} value={o}>{o === '' ? '—' : o}</option>)}
        </select>
      ) : (
        <input id={id} className="cu-input" type={f.widget === 'number' ? 'number' : 'text'} value={value}
               required={f.required} disabled={disabled} onChange={(e) => onChange(e.target.value)} />
      )}
    </div>
  )
}
