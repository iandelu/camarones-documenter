import { useRef, useState } from 'react'
import { t } from '../i18n/index.js'
import { Aviso, Button } from './components.jsx'
import { AREAS, fmtAgo, reasonText, repoRow, rowsFor, stateWord, verdictText } from './health.js'

// The project's health screen, shared by the portal (read-only: `links`) and the desktop app (`actions`, `onRefresh`).
// The numbers and states come from the snapshot of lib/health.py; the rules that turn them into rows are in health.js.
// A colour never stands alone: every dot has its word next to it.

const TAB_KEY = 'cu.health.tab'

function savedTab() {
  try {
    const v = localStorage.getItem(TAB_KEY)
    return AREAS.includes(v) ? v : null
  } catch { return null }                                   // private mode, or no browser
}

function saveTab(tab) {
  try { localStorage.setItem(TAB_KEY, tab) } catch { /* not remembered */ }
}

const dotClass = (state) => `cu-hb-dot cu-hb-dot--${state ?? 'none'}`
const Dot = ({ state }) => <span className={dotClass(state)} aria-hidden="true">●</span>
const safeUrl = (u) => (/^https?:\/\//i.test(u) ? u : null)

// What a row or a tile offers: the app's control, else the portal's link, else nothing.
function slot(id, actions, links) {
  const act = actions?.[id]
  if (act) return act()
  return links?.[id] ? <Button variant="ghost" size="sm" href={links[id]}>{t('hb.open')} →</Button> : null
}

function Tile({ area, snapshot, actions, links }) {
  const a = snapshot.areas?.[area] ?? { figures: [], next: null }
  const next = a.next
  const control = next ? slot(next.row, actions, links) : null
  return (
    <li className={`cu-hb-tile cu-hb-tile--${a.state ?? 'none'}`}>
      <div className="cu-hb-tile-head">
        <Dot state={a.state} />
        <h3 className="cu-hb-tile-name">{t(`hb.area.${area}`)}</h3>
        <strong className="cu-hb-word">{stateWord(area, a.state, t)}</strong>
      </div>
      <dl className="cu-hb-figs">
        {a.figures.map((f) => (
          <div key={f.key} className="cu-hb-fig">
            <dt>{t(`hb.fig.${f.key}`)}</dt>
            <dd>{f.n ?? '—'}</dd>
          </div>
        ))}
      </dl>
      {next && <p className="cu-hb-next-why">{reasonText(next, t)}</p>}
      {control && <span className="cu-hb-next-act">{control}</span>}
    </li>
  )
}

function RepoTable({ snapshot, repoHref }) {
  const repos = snapshot.repos
  if (!repos || typeof repos !== 'object' || typeof repos.error === 'string') return null
  const scanned = snapshot.inventory?.scanned === true
  const rows = Object.keys(repos).map((n) => repoRow(n, repos[n], snapshot.repo_state?.[n] ?? null, t, scanned))
  return (
    <div className="cu-hb-table-wrap">
      <table className="cu-hb-table">
        <thead>
          <tr>
            {['repo', 'sonar', 'coverage', 'vulns', 'debt'].map((c) => <th key={c} scope="col">{t(`hb.col.${c}`)}</th>)}
            <td />
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name}>
              <th scope="row" className="cu-hb-repo">
                <Dot state={r.state} /> {r.name}
                <span className="cu-hb-sub">{stateWord('code', r.state, t)}{r.note && ` · ${r.note}`}</span>
                {r.error && <span className="cu-hb-sub cu-hb-sub--error">{r.error}</span>}
              </th>
              <td>{r.sonarLink && safeUrl(r.sonarLink)
                ? <a href={safeUrl(r.sonarLink)} target="_blank" rel="noopener noreferrer">{r.sonar}</a> : r.sonar}</td>
              <td>{r.coverage}{r.coverageNote && <span className="cu-hb-sub">{r.coverageNote}</span>}</td>
              <td>{r.vulns}</td>
              <td>{r.debt}</td>
              <td className="cu-hb-full">{repoHref && <a href={repoHref(r.name)}>{t('hb.full')}</a>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Row({ row, snapshot, actions, links, repoHref }) {
  const control = slot(row.id, actions, links)
  return (
    <li className="cu-hb-row" data-row={row.id}>
      <Dot state={row.state} />
      <div className="cu-hb-row-main">
        <strong>{t(`hb.row.${row.id}`)}</strong>
        <span className="cu-hb-row-what">{t(`hb.rowWhat.${row.id}`)}</span>
      </div>
      <span className="cu-hb-row-fig">{row.figure ?? '—'}</span>
      <span className="cu-hb-row-slot">{control}</span>
      {row.error && <div className="cu-hb-row-error"><Aviso tone="warn" title={t('hb.rowUnread')} detail={row.error} /></div>}
      {row.id === 'repos' && <div className="cu-hb-row-body"><RepoTable snapshot={snapshot} repoHref={repoHref} /></div>}
    </li>
  )
}

export function HealthBoard({ snapshot, actions, links, repoHref, onRefresh, refreshing, initialTab }) {
  const [tab, setTab] = useState(() => initialTab ?? savedTab()
    ?? AREAS.find((a) => snapshot?.areas?.[a]?.state && snapshot.areas[a].state !== 'ok') ?? 'machine')
  const tabs = useRef({})
  const pick = (a) => { setTab(a); saveTab(a) }

  const refresh = onRefresh && (
    <Button size="sm" onClick={onRefresh} disabled={!!refreshing}>{refreshing ? t('hb.refreshing') : t('hb.refresh')}</Button>
  )
  if (!snapshot) return <div className="cu-hb"><Aviso tone="info" title={t('hb.never')} action={refresh} /></div>

  const overall = AREAS.reduce((w, a) => {
    const s = snapshot.areas?.[a]?.state
    return s === 'bad' || (s === 'warn' && w !== 'bad') ? s : w
  }, 'ok')
  const rows = rowsFor(tab, snapshot).filter((r) => r.id === 'repos' || actions?.[r.id] || links?.[r.id])

  // Arrow keys move between the tabs, like any tab list.
  const onKey = (e) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key]
    if (!step) return
    const next = AREAS[(AREAS.indexOf(tab) + step + AREAS.length) % AREAS.length]
    pick(next)
    tabs.current[next]?.focus()
    e.preventDefault()
  }

  return (
    <div className="cu-hb">
      <header className="cu-hb-top">
        <p className={`cu-hb-verdict cu-hb-verdict--${overall}`}><Dot state={overall} /> {verdictText(snapshot, t)}</p>
        <p className="cu-hb-checked">{t('hb.checked')} {fmtAgo(snapshot.at, Date.now(), t)}</p>
        {refresh}
      </header>
      <ul className="cu-hb-tiles">
        {AREAS.map((a) => <Tile key={a} area={a} snapshot={snapshot} actions={actions} links={links} />)}
      </ul>
      <div role="tablist" aria-label={t('hb.areas')} className="cu-hb-tabs" onKeyDown={onKey}>
        {AREAS.map((a) => (
          <button key={a} type="button" role="tab" id={`cu-hb-tab-${a}`} aria-selected={tab === a} aria-controls="cu-hb-panel"
                  tabIndex={tab === a ? 0 : -1} ref={(el) => { tabs.current[a] = el }} className="cu-hb-tab" onClick={() => pick(a)}>
            <Dot state={snapshot.areas?.[a]?.state} /> {t(`hb.area.${a}`)}
          </button>
        ))}
      </div>
      <ul className="cu-hb-rows" role="tabpanel" id="cu-hb-panel" aria-labelledby={`cu-hb-tab-${tab}`}>
        {rows.map((r) => <Row key={r.id} row={r} snapshot={snapshot} actions={actions} links={links} repoHref={repoHref} />)}
      </ul>
    </div>
  )
}
