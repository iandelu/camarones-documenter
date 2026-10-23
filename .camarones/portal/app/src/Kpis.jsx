import { useEffect, useState } from 'react'
import { getJSON, postJSON } from './api.js'
import { t } from './i18n.js'
import { money, segments, tiles } from './kpis.js'

const link = (path) => (window.hrefFor ? window.hrefFor(path) : `#/docs/${path}`)

// Is the documentation working? The same numbers as `camaron kpis` and `camaron stats`, plus what nobody found.
export default function Kpis() {
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { getJSON('kpis').then(setD, (e) => setError(e.message)) }, [])
  async function miss(q, action) {
    try {
      const r = await postJSON('kpis/miss', { q, action })
      setD((cur) => ({ ...cur, misses: r.misses }))
    } catch (e) { setError(e.message) }
  }
  if (error) return <section className="view"><h1>{t('kpisTitle')}</h1><p className="error" role="alert">{error}</p></section>
  if (!d) return <section className="view"><h1>{t('kpisTitle')}</h1><p className="muted">{t('loading')}</p></section>
  return (
    <section className="view kpis">
      <h1>{t('kpisTitle')}</h1>
      <p className="lede">{t('kpisLead')}</p>
      <div className="tiles">
        {tiles(d).map((x) => (
          <div className={`tile ${x.state || ''}`} key={x.key} title={t(`tip.${x.key}`)}>
            <span className="tile-label">{t(`tile.${x.key}`)}</span>
            <b>{x.value}</b>
            {x.sub ? <span className="tile-sub">{t(`sub.${x.key}`).replace('{n}', x.sub)}</span> : null}
          </div>
        ))}
      </div>

      <h2>{t('kpisRepos')}</h2>
      <p className="legend">
        <span><i className="sw confirmed" /> {t('confirmedPages')}</span>
        <span><i className="sw draft" /> {t('draftPages')}</span>
        <span><i className="sw needsReconfirm" /> {t('reconfirmPages')}</span>
      </p>
      <table className="kpi-table">
        <thead><tr><th>{t('repo')}</th><th>{t('pagesCol')}</th><th>{t('confirmedPages')}</th><th>{t('draftPages')}</th>
          <th>{t('reconfirmPages')}</th><th className="barcol" aria-hidden="true" /></tr></thead>
        <tbody>{d.coverage.byRepo.map((r) => (
          <tr key={r.repo}>
            <td>{r.repo === '(project)' ? t('wholeProject') : r.repo}</td><td>{r.pages}</td><td>{r.confirmed}</td>
            <td>{r.draft}</td><td>{r.needsReconfirm}</td>
            <td className="barcol"><div className="bar">{segments(r).map((s) => (
              <span key={s.key} className={`seg ${s.key}`} style={{ width: `${s.share}%` }}
                title={`${t(s.key === 'needsReconfirm' ? 'reconfirmPages' : `${s.key}Pages`)}: ${s.n} (${s.share} %)`} />
            ))}</div></td>
          </tr>))}</tbody>
      </table>

      <h2>{t('kpisMisses')}</h2>
      <p className="muted small">{t('kpisMissesLead')}</p>
      {d.misses.length ? (
        <ul className="misses">{d.misses.map((m) => (
          <li key={m.q}>
            <span className="q">{m.q}</span><span className="muted small">×{m.n} · {m.last}</span>
            <span className="acts">
              <button type="button" className="small" onClick={() => miss(m.q, 'question')}>{t('toQuestion')}</button>
              <button type="button" className="ghost small" onClick={() => miss(m.q, 'dismiss')}>{t('dismiss')}</button>
            </span>
          </li>))}</ul>
      ) : <p className="muted">{t('noMisses')}</p>}

      {d.freshness.outOfDate.length ? (<>
        <h2>{t('kpisStale')}</h2>
        <ul className="plain">{d.freshness.outOfDate.map((p) => <li key={p}><a href={link(p)}>{p}</a></li>)}</ul>
      </>) : null}

      <h2>{t('kpisRuns')}</h2>
      {d.runs.some((r) => r.runs) ? (
        <table className="kpi-table">
          <thead><tr><th>{t('month')}</th><th>{t('runsCol')}</th><th>{t('unitsDone')}</th><th>{t('hours')}</th>
            <th>{t('tokens')}</th><th>{t('cost')}</th><th>{t('costPerUnit')}</th></tr></thead>
          <tbody>{d.runs.filter((r) => r.runs).map((r) => (
            <tr key={r.month}><td>{r.month}</td><td>{r.runs}</td><td>{r.done} / {r.units}</td><td>{r.hours}</td>
              <td>{(r.tokens_in + r.tokens_cache + r.tokens_out).toLocaleString()}</td><td>{money(r.cost_usd)}</td>
              <td>{money(r.cost_per_unit)}</td></tr>))}</tbody>
        </table>
      ) : <p className="muted">{t('noRuns')}</p>}

      {d.topPages.length ? (<>
        <h2>{t('kpisTop')}</h2>
        <table className="kpi-table">
          <thead><tr><th>{t('page')}</th><th>{t('reads')}</th><th>{t('byAgents')}</th><th>{t('byPeople')}</th></tr></thead>
          <tbody>{d.topPages.map((p) => (
            <tr key={p.path}><td><a href={link(p.path)}>{p.path}</a></td><td>{p.reads}</td><td>{p.agent}</td><td>{p.human}</td></tr>))}</tbody>
        </table>
      </>) : null}
      <p className="muted small">{t(d.recording ? 'recordingOn' : 'recordingOff')} {t('kpisCli')}</p>
    </section>
  )
}
