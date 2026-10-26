import { useRef, useState } from 'react'
import { t } from '../i18n/index.js'
import { Aviso, Button } from './components.jsx'
import { AREAS, fmtAgo, nextReason, repoRow, rowsFor, safeUrl, stateWord, tileTarget, verdictText } from './health.js'

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
// The dot is colour; `word` is what it says, for readers who do not see the colour (screen readers). Where the word is
// already drawn next to the dot, it is left out.
const Dot = ({ state, word }) => (
  <>
    <span className={dotClass(state)} aria-hidden="true">●</span>
    {word && <span className="sr-only">{word}</span>}
  </>
)

// The app's actions are stateful (they run commands when they mount), so one is drawn only inside its own row, and only
// while that row is open: the tile's button opens the row instead of drawing a second copy.
function Tile({ area, snapshot, actions, links, onOpen }) {
  const a = snapshot.areas?.[area] ?? { figures: [], next: null }
  const next = a.next
  const target = tileTarget(next, actions, links)
  const control = target?.kind === 'open'
    ? <Button variant="ghost" size="sm" onClick={() => onOpen(area, target.row)}>{t('hb.open')}</Button>
    : target?.kind === 'link' ? <Button variant="ghost" size="sm" href={target.href}>{t('hb.open')} →</Button> : null
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
      {next && <p className="cu-hb-next-why">{nextReason(next, snapshot.verdict, t)}</p>}
      {control && <span className="cu-hb-next-act">{control}</span>}
    </li>
  )
}

function RepoTable({ snapshot, repoHref, connectHref }) {
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
              <td>
                {r.gateState && <><Dot state={r.gateState} /> </>}
                {r.sonarLink && safeUrl(r.sonarLink)
                  ? <a href={safeUrl(r.sonarLink)} target="_blank" rel="noopener noreferrer">{r.sonar}</a> : r.sonar}
                {r.sonarNote && <span className="cu-hb-sub">{r.sonarNote}</span>}
                {r.connect !== undefined && connectHref && <a className="cu-hb-sub" href={connectHref(r.connect)}>{t('hb.connect')}</a>}
              </td>
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

function Row({ area, row, snapshot, actions, links, repoHref, connectHref, open, onToggle }) {
  const action = actions?.[row.id]
  const control = action
    ? <Button variant="ghost" size="sm" aria-expanded={open} aria-controls={`cu-hb-open-${row.id}`} onClick={() => onToggle(row.id)}>{t('hb.open')}</Button>
    : links?.[row.id] ? <Button variant="ghost" size="sm" href={links[row.id]}>{t('hb.open')} →</Button> : null
  return (
    <li className="cu-hb-row" data-row={row.id}>
      <Dot state={row.state} word={stateWord(area, row.state, t)} />
      <div className="cu-hb-row-main">
        <strong>{t(`hb.row.${row.id}`)}</strong>
        <span className="cu-hb-row-what">{t(`hb.rowWhat.${row.id}`)}</span>
      </div>
      <span className="cu-hb-row-fig">{row.figure ?? '—'}</span>
      <span className="cu-hb-row-slot">{control}</span>
      {row.error && <div className="cu-hb-row-error"><Aviso tone="warn" title={t('hb.rowUnread')} detail={row.error} /></div>}
      {action && open && <div className="cu-hb-row-body" id={`cu-hb-open-${row.id}`}>{action()}</div>}
      {row.id === 'repos' && <div className="cu-hb-row-body"><RepoTable snapshot={snapshot} repoHref={repoHref} connectHref={connectHref} /></div>}
    </li>
  )
}

export function HealthBoard({ snapshot, actions, links, repoHref, connectHref, onRefresh, refreshing, initialTab, initialOpen = [] }) {
  const [open, setOpen] = useState(() => new Set(initialOpen))          // row ids whose action is showing
  const toggle = (id) => setOpen((s) => { const n = new Set(s); if (!n.delete(id)) n.add(id); return n })
  const [tab, setTab] = useState(() => initialTab ?? savedTab()
    ?? AREAS.find((a) => snapshot?.areas?.[a]?.state && snapshot.areas[a].state !== 'ok') ?? 'machine')
  const tabs = useRef({})
  const pick = (a) => { setTab(a); saveTab(a) }
  const openRow = (area, id) => { pick(area); setOpen((s) => new Set(s).add(id)) }

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
        <p className={`cu-hb-verdict cu-hb-verdict--${overall}`}><Dot state={overall} word={overall === 'ok' ? '' : t(`hb.state.${overall}`)} /> {verdictText(snapshot, t)}</p>
        <p className="cu-hb-checked">{t('hb.checked')} {fmtAgo(snapshot.at, Date.now(), t)}</p>
        {refresh}
      </header>
      <ul className="cu-hb-tiles">
        {AREAS.map((a) => <Tile key={a} area={a} snapshot={snapshot} actions={actions} links={links} onOpen={openRow} />)}
      </ul>
      <div role="tablist" aria-label={t('hb.areas')} className="cu-hb-tabs" onKeyDown={onKey}>
        {AREAS.map((a) => (
          <button key={a} type="button" role="tab" id={`cu-hb-tab-${a}`} aria-selected={tab === a} aria-controls="cu-hb-panel"
                  tabIndex={tab === a ? 0 : -1} ref={(el) => { tabs.current[a] = el }} className="cu-hb-tab" onClick={() => pick(a)}>
            <Dot state={snapshot.areas?.[a]?.state} word={stateWord(a, snapshot.areas?.[a]?.state, t)} /> {t(`hb.area.${a}`)}
          </button>
        ))}
      </div>
      <ul className="cu-hb-rows" role="tabpanel" id="cu-hb-panel" aria-labelledby={`cu-hb-tab-${tab}`}>
        {rows.map((r) => <Row key={r.id} area={tab} row={r} snapshot={snapshot} actions={actions} links={links} repoHref={repoHref} connectHref={connectHref}
                                   open={open.has(r.id)} onToggle={toggle} />)}
      </ul>
    </div>
  )
}
