import { useEffect, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import { t } from './i18n.js'
import { Skeleton } from '@camaron/ui'
import Failed from './Failed.jsx'
import { core } from './core.js'
import AppOnly from './AppOnly.jsx'
import { pipelineState, rows } from './ci.js'

const link = (path) => core.hrefFor(path)

function Copy({ text }) {
  const [done, setDone] = useState(false)
  async function copy() {
    try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 2000) } catch { /* no clipboard */ }
  }
  return <button type="button" className="ghost small" onClick={copy}>{done ? t('copied') : t('copy')}</button>
}

// The docs repo's pipeline and the checks for each service repo, generated from one definition (lib/ci.py).
export default function Ci() {
  const [s, setS] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => getJSON('ci').then((x) => { setS(x); setError('') }, (e) => setError(e.message))
  useEffect(() => { load() }, [])
  async function generate(forge) {
    setBusy(true)
    try { setS(await postJSON('ci', { forge })); setError('') } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  if (!s) return <section className="view"><h1>{t('ciTitle')}</h1>{error ? <Failed title={t('ciFailed')} detail={error} onRetry={() => { setError(''); load() }} /> : <Skeleton lines={4} />}</section>
  const p = pipelineState(s.pipeline)
  const other = s.forge === 'github' ? 'gitlab' : 'github'
  const anyMissing = rows(s).some((r) => r.state !== 'current')
  return (
    <section className="view ci">
      <h1>{t('ciTitle')}</h1>
      <p className="lede">{t('ciLead')}</p>
      <div className="ci-facts">
        <span className="pill">{s.forge === 'github' ? 'GitHub Actions' : 'GitLab CI'}</span>
        <span className="pill">{t(s.target === 'self-hosted' ? 'ciSelfHosted' : 'ciHosted')}</span>
        {p ? <a className={`pill run ${p.state}`} href={s.pipeline.url} target="_blank" rel="noreferrer">
          {t('ciLast')}: {t(`ci.${p.word}`)} · {s.pipeline.title} ↗</a>
          : <span className="muted small">{t('ciNoRun')}</span>}
      </div>
      {error ? <p className="error" role="alert">{error}</p> : null}

      <h2>{t('ciFiles')}</h2>
      <table className="kpi-table">
        <tbody>{rows(s).map((r) => (
          <tr key={r.key}><td>{t(`ciFile.${r.key}`)}</td><td><code>{r.path || '—'}</code></td>
            <td className={`ci-state ${r.state}`}>{t(`ciState.${r.state}`)}</td></tr>))}</tbody>
      </table>
      <div className="row ci-gen"><AppOnly>
        <button type="button" disabled={busy} onClick={() => generate(s.forge)}>
          {anyMissing ? t('ciGenerate') : t('ciRegenerate')} ({s.forge === 'github' ? 'GitHub' : 'GitLab'})</button>
        <button type="button" className="ghost small" disabled={busy} onClick={() => generate(other)}>
          {t('ciOther')} {other === 'github' ? 'GitHub' : 'GitLab'}</button>
        <span className="muted small">{t('ciNoPush')}</span>
      </AppOnly></div>

      <h2>{t('ciChecks')}</h2>
      <p>
        <span className={`pill ${s.check.errors ? 'bad' : 'ok'}`}>{t('ciErrors').replace('{n}', s.check.errors)}</span>{' '}
        <span className="pill">{t('ciWarnings').replace('{n}', s.check.warnings)}</span>{' '}
        <span className={`pill ${s.freshness.suspect + s.freshness.stale ? 'warn' : ''}`}>
          {t('ciOutOfDate').replace('{n}', s.freshness.suspect + s.freshness.stale)}</span>{' '}
        <a className="more" href="#/review">{t('ciReview')} →</a>
      </p>
      {s.check.first.length ? <ul className="plain small">{s.check.first.map((e) => <li key={e}><code>{e}</code></li>)}</ul> : null}

      <h2>{t('ciRepos')}</h2>
      <p className="muted small">{t('ciReposLead')}</p>
      {[['repo', s.snippets.repo], ['fresh', s.snippets.fresh], ['propose', s.snippets.propose]].filter(([, x]) => x).map(([k, text]) => (
        <details key={k} className="ci-snippet">
          <summary>{t(`ciFile.${k === 'repo' ? 'snippet' : k}`)} <Copy text={text} /></summary>
          <pre className="log">{text}</pre>
        </details>
      ))}
      <p className="small"><a className="more" href={link(s.guide)}>{t('ciGuide')} →</a></p>
    </section>
  )
}
