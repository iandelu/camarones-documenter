import { useEffect, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import { t } from './i18n.js'
import { Skeleton } from '@camaron/ui'
import Failed from './Failed.jsx'

// Sync with the team (env.sync_status / env.share): where this cam-docs stands against the team's repo and sharing
// as the team action it is — checkpoint, bring in the team's work, push. A clash is undone and reported, never forced.
const when = (iso) => { try { return new Date(iso).toLocaleString(document.documentElement.lang || 'en', { dateStyle: 'medium', timeStyle: 'short' }) } catch { return iso } }

export default function Sync() {
  const [s, setS] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [result, setResult] = useState(null)
  const load = (fetch) => getJSON(`sync${fetch ? '?fetch=1' : ''}`).then((x) => { setS(x); setError('') }, (e) => setError(e.message))
  useEffect(() => { load(false) }, [])
  async function check() {
    setBusy('check')
    try { await load(true) } finally { setBusy('') }
  }
  async function share() {
    setBusy('share')
    setResult(null)
    try {
      const r = await postJSON('sync/share', {})
      setResult(r.result)
      setS(r.sync)
    } catch (e) { setResult({ status: 'error', detail: e.message }) } finally { setBusy('') }
  }
  if (error) return <section className="view"><h1>{t('syTitle')}</h1><Failed title={t('syFailed')} detail={error} onRetry={() => { setError(''); load(false) }} /></section>
  if (!s) return <section className="view"><h1>{t('syTitle')}</h1><Skeleton lines={3} /></section>
  const r = result
  const message = r && (t(`sy.${r.status}`).startsWith('sy.') ? r.status : t(`sy.${r.status}`)).replace('{detail}', r.detail || '')
  const ok = r && ['pushed', 'up-to-date', 'nothing'].includes(r.status)
  return (
    <section className="view sync">
      <h1>{t('syTitle')}</h1>
      <p className="lede">{t('syLead')}</p>
      {!s.remote ? <p className="aviso">{t('syNoRemote')}</p> : (
        <div className="sy-grid">
          <div className="sy-tile wide"><span className="eyebrow">{t('syRemote')}</span><code>{s.remote}</code>
            <small className="muted">{t('syBranch')} {s.branch || '—'}</small></div>
          <div className={`sy-tile ${s.ahead ? 'warn' : ''}`}><span className="eyebrow">{t('syAhead')}</span>
            <b>{s.ahead ?? '—'}</b><small className="muted">{s.ahead == null ? t('syNever') : s.ahead ? t('syAheadSub') : t('syAheadNone')}</small></div>
          <div className={`sy-tile ${s.behind ? 'warn' : ''}`}><span className="eyebrow">{t('syBehind')}</span>
            <b>{s.behind ?? '—'}</b><small className="muted">{s.behind ? t('syBehindSub') : t('syBehindNone')}</small></div>
          <div className="sy-tile"><span className="eyebrow">{t('syLast')}</span>
            <b className="sy-when">{s.last_share ? when(s.last_share) : '—'}</b>
            <small className="muted">{s.auto ? t('syAutoOn') : t('syAutoOff')}</small></div>
        </div>
      )}
      {s.fetched && !s.fetched.ok ? <p className="error" role="alert">{t('syFetchFailed')} {s.fetched.reason}</p> : null}
      <div className="row sy-actions">
        {s.remote ? <button type="button" className="small" disabled={!!busy} onClick={share}>{busy === 'share' ? t('syBusy') : t('syShare')}</button> : null}
        {s.remote ? <button type="button" className="ghost small" disabled={!!busy} onClick={check}>{t('syCheck')}</button> : null}
        {r ? <span className={ok ? 'ok' : 'error'} role={ok ? 'status' : 'alert'}>{message}</span> : null}
      </div>
      <h2>{t('syPending').replace('{n}', s.pending.length)}</h2>
      {s.pending.length ? (
        <ul className="sy-files">{s.pending.slice(0, 30).map((f) => <li key={f}><code>{f}</code></li>)}
          {s.pending.length > 30 ? <li className="muted">… {s.pending.length - 30}</li> : null}</ul>
      ) : <p className="muted">{t('syClean')}</p>}
      {s.head ? <p className="muted small">{t('syHead')} <code>{s.head.hash}</code> {s.head.subject} · {when(s.head.date)}</p> : null}
    </section>
  )
}
