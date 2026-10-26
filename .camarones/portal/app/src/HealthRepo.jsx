import { t } from './i18n.js'
import { Aviso, fmtAgo, gateState, gateWord, safeUrl, sourceWord, stateWord, uiText } from '@camaron/ui'
import { evidenceHref, repoPage } from './healthRepo.js'

const DASH = '—'
const SEV = { critical: 'bad', high: 'bad', medium: 'warn', moderate: 'warn', low: 'muted', unknown: 'muted' }
const docHref = (path) => `#/docs/${path.split('/').map(encodeURIComponent).join('/')}`
const text = (v) => (typeof v === 'string' && v.trim() ? v : typeof v === 'number' ? String(v) : DASH)
const day = (iso) => (typeof iso === 'string' && iso ? iso.slice(0, 10) : '')

// A colour never stands alone: the dot always comes with the state's word.
const State = ({ state }) => (
  <span className="hr-state">
    <span className={`cu-hb-dot cu-hb-dot--${state ?? 'none'}`} aria-hidden="true">●</span> <b>{stateWord('code', state, uiText)}</b>
  </span>
)

// A block that could not be read says why, in the block, instead of a dash.
const Unread = ({ message }) => <Aviso tone="warn" title={t('hrBlockError')} detail={message} />

function Block({ title, children }) {
  return <section className="hr-block"><h2>{title}</h2>{children}</section>
}

const FIGURE_LABEL = { coverage: 'hrCoverage', bugs: 'hrFigBugs', vulnerabilities: 'hrFigVulnerabilities', security_hotspots: 'hrFigHotspots',
  code_smells: 'hrFigSmells', debt_minutes: 'hrFigDebt', maintainability: 'hrFigMaintainability', reliability: 'hrFigReliability', security: 'hrFigSecurity' }

// What the SonarQube server said: the gate as a word beside its dot, then the nine figures. After a failed read these are the
// last ones it gave, so they say how old they are.
function SonarFigures({ page, now }) {
  const { gate, sonarFigures, sonarAt, sonarError } = page
  if (!sonarFigures.length) return null
  return (
    <>
      <p>{t('hrGate')}: <span className={`cu-hb-dot cu-hb-dot--${gateState(gate) ?? 'none'}`} aria-hidden="true">●</span> <b>{gateWord(gate, uiText)}</b></p>
      <dl className="hr-facts">
        {sonarFigures.filter((f) => f.key !== 'coverage').map((f) => <div key={f.key}><dt>{t(FIGURE_LABEL[f.key])}</dt><dd>{text(f.value)}</dd></div>)}
      </dl>
      {sonarError ? <p className="muted small">{t('hrSonarOld').replace('{ago}', fmtAgo(sonarAt, now, uiText))}</p> : null}
    </>
  )
}

function Quality({ page, now }) {
  const { sonar, coverage, reports, errors } = page
  return (
    <Block title={t('hrCode')}>
      <h3>{t('hrSonar')}</h3>
      {errors.sonar ? <Unread message={errors.sonar} />
        : sonar?.used ? (
          <>
            <dl className="hr-facts">
              <div><dt>{t('hrSonarProject')}</dt><dd><code>{text(sonar.project)}</code></dd></div>
              {sonar.organization ? <div><dt>{t('hrSonarOrg')}</dt><dd>{sonar.organization}</dd></div> : null}
              {sonar.host ? <div><dt>{t('hrSonarHost')}</dt><dd>{sonar.host}</dd></div> : null}
            </dl>
            {page.sonarError ? <Aviso tone="warn" title={t('hrSonarError')} detail={page.sonarError} /> : null}
            {page.connect ? <p className="muted">{t('hrSonarNoToken')}</p> : null}
            <SonarFigures page={page} now={now} />
          </>
        ) : (
          <div><p><b>{t('hrNoSonar')}</b></p><p className="muted">{t('hrNoSonarHow')}</p></div>
        )}
      <h3>{t('hrCoverage')}</h3>
      {errors.coverage ? <Unread message={errors.coverage} />
        : coverage ? (
          <p><b>{typeof coverage.percent === 'number' ? `${coverage.percent}%` : DASH}</b>{' '}
            <span className="muted small">{[sourceWord(coverage.source, uiText), day(coverage.at), coverage.path].filter(Boolean).join(' · ')}</span></p>
        ) : !reports.length && !errors.reports ? <p className="muted">{t('hrNoCoverage')}</p> : null}
      {errors.reports ? <Unread message={errors.reports} />
        : reports.length ? (
          <>
            <h3>{t('hrReports')}</h3>
            <ul className="list">{reports.map((r, i) => (
              <li key={`${r.path}${i}`}><span className="chip">{text(r.type)}</span> <code>{text(r.path)}</code>{' '}
                {r.error ? <span className="muted">{r.error}</span>
                  : <b>{typeof r.percent === 'number' ? `${r.percent}%` : DASH}</b>}{' '}
                {day(r.at) ? <span className="muted small">{day(r.at)}</span> : null}</li>))}</ul>
          </>
        ) : null}
    </Block>
  )
}

function Vulnerabilities({ page }) {
  const { vulnerable, errors, scanned } = page
  return (
    <Block title={t('hrVulns')}>
      {errors.vulnerable ? <Unread message={errors.vulnerable} />
        : vulnerable.length ? (
          <div className="libs-scroll">
            <table className="kpi-table">
              <thead><tr><th>{t('hrLibrary')}</th><th>{t('hrVersion')}</th><th>{t('hrSeverity')}</th><th>{t('hrAdvisory')}</th><th>{t('hrFixedIn')}</th></tr></thead>
              <tbody>{vulnerable.map((v, i) => (
                <tr key={`${v.name}${v.id}${i}`}>
                  <td><code>{text(v.name)}</code></td>
                  <td>{text(v.version)}</td>
                  <td><span className={`pill ${SEV[v.severity] ?? 'muted'}`}>{uiText(`hb.sev.${v.severity}`) === `hb.sev.${v.severity}` ? text(v.severity) : uiText(`hb.sev.${v.severity}`)}</span></td>
                  <td>{v.id
                    ? <a href={`https://osv.dev/vulnerability/${encodeURIComponent(v.id)}`} target="_blank" rel="noopener noreferrer">{v.cve || v.id}</a>
                    : text(v.cve)}</td>
                  <td>{text(v.fixed)}</td>
                </tr>))}</tbody>
            </table>
          </div>
        ) : <p className="muted">{t(scanned ? 'hrNoVulns' : 'hrNotScanned')}</p>}
    </Block>
  )
}

function Evidence({ refs }) {
  const list = Array.isArray(refs) ? refs : []
  if (!list.length) return DASH
  return list.map((ev, i) => {
    const href = evidenceHref(ev)
    return <span key={`${ev}${i}`}>{i ? ', ' : ''}{href ? <a href={href}><code>{ev}</code></a> : <code>{String(ev)}</code>}</span>
  })
}

function Debt({ page }) {
  const sources = Object.entries(page.debt)
  return (
    <Block title={t('hrDebt')}>
      {page.errors.debt ? <Unread message={page.errors.debt} />
        : sources.length ? sources.map(([source, items]) => {
          const trust = items[0]?.trust
          return (
            <div key={source} className="hr-source">
              <h3>{source ? <a href={docHref(source)}>{source}</a> : DASH}
                {trust ? <> <span className={`pill trust ${trust}`}>{uiText(`hb.trust.${trust}`) === `hb.trust.${trust}` ? trust : uiText(`hb.trust.${trust}`)}</span></> : null}</h3>
              <ul className="list">{items.map((d, i) => (
                <li key={`${d.item}${i}`}>
                  <b>{text(d.item)}</b>
                  <div className="muted small">
                    {t('hrImpact')}: {uiText(`hb.impact.${d.impact}`) === `hb.impact.${d.impact}` ? text(d.impact) : uiText(`hb.impact.${d.impact}`)}
                    {' · '}{t('hrEffort')}: {text(d.effort)}
                    {' · '}{t('hrOwner')}: {text(d.owner)}
                  </div>
                  {d.recommendation ? <div>{t('hrRecommendation')}: {d.recommendation}</div> : null}
                  <div className="small">{t('hrEvidence')}: <Evidence refs={d.evidence} /></div>
                </li>))}</ul>
            </div>
          )
        }) : <p className="muted">{t('hrNoDebt')}</p>}
    </Block>
  )
}

function Docs({ page }) {
  const { pages, errors } = page
  return (
    <Block title={t('hrDocs')}>
      {errors.pages ? <Unread message={errors.pages} /> : null}
      {pages.length ? (
        <ul className="list">{pages.map((p) => (
          <li key={`${p.state}${p.path}`}><a href={docHref(p.path)}>{p.path}</a>{' '}
            <span className={`pill ${p.state === 'stale' ? 'bad' : 'warn'}`}>{t(p.state === 'stale' ? 'hrStale' : 'hrSuspect')}</span></li>))}</ul>
      ) : errors.pages ? null : <p className="muted">{t('hrNoDocs')}</p>}
    </Block>
  )
}

// #/health/<repo>: one repo of the snapshot GET /api/health reads. Read-only, like the whole of Salud.
export default function HealthRepo({ snapshot, name, now = Date.now() }) {
  const page = repoPage(snapshot, name)
  const back = <a href="#/health">{t('hrBack')}</a>
  if (!page) return <><h1>{name}</h1><Aviso tone="info" title={t('hrUnknown')}>{back}</Aviso></>
  const sonarLink = page.sonar?.used ? safeUrl(page.sonar.link) : null
  const e = encodeURIComponent(name)
  return (
    <>
      <p className="small">{back}</p>
      <h1>{name}</h1>
      <p><State state={page.state} /></p>
      <p className="hr-links">
        {sonarLink ? <><a href={sonarLink} target="_blank" rel="noopener noreferrer">{t('hrSonarLink')} <span aria-hidden="true">↗</span></a>{' · '}</> : null}
        <a href={`#/docs/repos/${e}/index.md`}>{t('hrBrief')}</a>{' · '}
        <a href={`#/libs/${e}`}>{t('hrLibs')}</a>
      </p>
      {page.error ? <Aviso tone="warn" title={t('hrUnreadable')} detail={page.error} />
        : page.cloned === false ? <Aviso tone="info" title={uiText('hb.notCloned')} />
        : (
          <>
            <Quality page={page} now={now} />
            <Vulnerabilities page={page} />
            <Debt page={page} />
            <Docs page={page} />
          </>
        )}
    </>
  )
}
