import { Fragment, useEffect, useMemo, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import { t } from './i18n.js'
import { Skeleton } from '@camaron/ui'
import Failed from './Failed.jsx'
import AppOnly from './AppOnly.jsx'
import { applyFilter, facets, matrix, placesOf, repoFilter } from './libs.js'

const SEV = { critical: 'bad', high: 'bad', medium: 'warn', low: 'muted', unknown: 'muted' }

function Select({ label, value, onChange, options }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}>
      <option value="">{label}: {t('all')}</option>
      {options.map(([k, n]) => <option key={k} value={k}>{k} ({n})</option>)}
    </select>
  )
}

// Which repos have this library, the flagged ones first: with many services their columns sit off screen.
export function Where({ item }) {
  const { shown, more } = placesOf(item)
  return (
    <span className="libs-where muted small">{t('libsIn')} {shown.map((p, i) => (
      <Fragment key={p.repo}>{i ? ' · ' : ''}{p.flagged ? <b className="libs-where-bad">{p.repo}</b> : p.repo}</Fragment>
    ))}{more ? ` ${t('libsMore', { n: more })}` : ''}</span>
  )
}

// Every repo's direct dependencies (lib/inventory.py) as a library × service matrix, with known vulnerabilities in red.
export default function Libs({ arg = '' }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [f, setF] = useState({})
  const [open, setOpen] = useState(null)
  const load = () => getJSON('inventory').then((x) => { setData(x); setError('') }, (e) => setError(e.message))
  useEffect(() => { load() }, [])
  // #/libs/<repo> opens filtered to that repo, once the inventory says which repos there are
  useEffect(() => { if (arg && data) setF((cur) => ({ ...cur, repo: repoFilter(arg, data.libraries) })) }, [arg, !!data])
  async function refresh(cves) {
    setBusy(cves ? t('libsScanning') : t('libsRefreshing'))
    try {
      const job = await postJSON('inventory', { cves })
      for (;;) {
        const j = await getJSON(`jobs/${job.id}?since=0`)
        if (j.status !== 'running') { if (j.status !== 'done') setError(j.log.slice(-1)[0] || j.status); break }
        await new Promise((r) => setTimeout(r, 1500))
      }
      await load()
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  const rows = data?.libraries || []
  const shown = useMemo(() => applyFilter(rows, f), [rows, f])
  const m = useMemo(() => matrix(shown), [shown])
  const fc = useMemo(() => facets(rows), [rows])
  if (!data) return <section className="view"><h1>{t('libsTitle')}</h1>{error ? <Failed title={t('libsFailed')} detail={error} onRetry={() => { setError(''); load() }} /> : <Skeleton lines={4} />}</section>
  const vulnerable = rows.filter((r) => (r.vulns || []).length).length
  const drift = new Set(rows.filter((r) => r.drift).map((r) => r.name)).size
  const set = (k) => (v) => setF((cur) => ({ ...cur, [k]: v }))
  return (
    <section className="view libs">
      <h1>{t('libsTitle')}</h1>
      <p className="lede">{t('libsLead')}</p>
      <div className="libs-summary">
        <span className="pill">{t('libsCount').replace('{n}', new Set(rows.map((r) => r.ecosystem + r.name)).size)}</span>
        {data.vulns ? <span className={`pill ${vulnerable ? 'bad' : 'ok'}`}>{t('libsVulnerable').replace('{n}', vulnerable)}</span>
          : <span className="muted small">{t('libsNoScan')}</span>}
        {drift ? <span className="pill warn">{t('libsDrift').replace('{n}', drift)}</span> : null}
        {data.vulns ? <span className="muted small">{t(data.vulns.online ? 'libsOnline' : 'libsOffline')} · {data.vulns.at?.slice(0, 10)}</span> : null}
        <span className="libs-actions"><AppOnly>
          <button type="button" disabled={!!busy} onClick={() => refresh(true)}>{t('libsScan')}</button>
          <button type="button" className="ghost small" disabled={!!busy} onClick={() => refresh(false)}>{t('libsRefresh')}</button>
        </AppOnly></span>
      </div>
      {busy ? <p className="muted small" role="status">{busy}</p> : null}
      {error ? <p className="error" role="alert">{error}</p> : null}
      <div className="libs-filters">
        <input type="search" placeholder={t('libsSearch')} aria-label={t('libsSearch')} value={f.q || ''} onChange={(e) => set('q')(e.target.value)} />
        <Select label={t('libsCategory')} value={f.category || ''} onChange={set('category')} options={fc.category} />
        <Select label={t('libsLanguage')} value={f.language || ''} onChange={set('language')} options={fc.language} />
        <Select label={t('libsRepo')} value={f.repo || ''} onChange={set('repo')} options={fc.repo} />
        <Select label={t('libsScope')} value={f.scope || ''} onChange={set('scope')} options={fc.scope} />
        <label className="small"><input type="checkbox" checked={!!f.vulnerable} onChange={(e) => set('vulnerable')(e.target.checked)} /> {t('libsOnlyVulnerable')}</label>
      </div>
      {m.items.length ? (
        <div className="libs-scroll">
          <table className="kpi-table libs-table">
            <thead><tr><th>{t('libsLibrary')}</th><th>{t('libsCategory')}</th>{m.repos.map((r) => <th key={r}>{r}</th>)}</tr></thead>
            <tbody>{m.items.map((x) => (
              <Fragment key={x.key}>
                <tr className={x.worst ? `vuln sev-${SEV[x.worst]}` : ''} onClick={() => setOpen(open === x.key ? null : x.key)}>
                  <td><code>{x.name}</code> <span className="muted small">{x.ecosystem}</span>
                    {x.worst ? <span className={`pill ${SEV[x.worst]}`}>⚠ {t(`sev.${x.worst}`)}</span> : null}
                    {x.drift ? <span className="pill warn">{t('libsVersions')}</span> : null}
                    <br /><Where item={x} /></td>
                  <td><span className="chip">{x.category}</span></td>
                  {m.repos.map((r) => {
                    const c = x.cells[r]
                    return <td key={r} className={c?.vulns.length ? 'cell-vuln' : ''}>{c ? <>{c.version || '—'} {c.scope !== 'runtime' ? <span className="muted small">{c.scope}</span> : null}</> : ''}</td>
                  })}
                </tr>
                {open === x.key && x.vulns.length ? (
                  <tr className="vuln-detail"><td colSpan={2 + m.repos.length}>
                    <ul className="plain">{[...new Map(x.vulns.map((v) => [v.id, v])).values()].map((v) => (
                      <li key={v.id}><a href={`https://osv.dev/vulnerability/${encodeURIComponent(v.id)}`} target="_blank" rel="noreferrer">{v.cve || v.id}</a>{' '}
                        <span className={`pill ${SEV[v.severity]}`}>{t(`sev.${v.severity}`)}{v.score ? ` ${v.score}` : ''}</span>{' '}
                        {v.summary} {v.fixed ? <b>{t('libsFixed').replace('{v}', v.fixed)}</b> : null}</li>))}</ul>
                  </td></tr>
                ) : null}
              </Fragment>
            ))}</tbody>
          </table>
        </div>
      ) : <p className="muted">{t('libsNone')}</p>}
      <p className="muted small">{t('libsCli')}</p>
    </section>
  )
}
