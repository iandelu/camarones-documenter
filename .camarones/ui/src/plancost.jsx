import { t } from '../i18n/index.js'
import { Button, Card } from './components.jsx'
import { fmtDuration, money, phaseRows, summary, topUnits } from './plancost.js'

const fill = (s, vars) => s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m))

// What the plan took from zero (`camaron plan cost`), shared by the desktop app's Plan (`onRefresh`) and the portal's
// KPIs (read-only). The dollars are API-equivalent; what has no price or could not be measured is said in words.
export function PlanCost({ bill, onRefresh, busy, lang }) {
  const tt = (k, vars = {}) => fill(t(k, lang), vars)
  const s = summary(bill)
  const people = s.people === 1 ? tt('pc.person') : tt('pc.people', { n: s.people })
  const head = [s.since && tt('pc.since', { date: s.since }), s.people && people].filter(Boolean).join(' · ')
  const gaps = [['pc.unpriced', s.gaps.unpriced], ['pc.unmeasured', s.gaps.unmeasured], ['pc.unrecorded', s.gaps.unrecorded]]
    .filter(([, n]) => n).map(([k, n]) => tt(k, { n }))
  const figs = [['pc.cost', s.cost], ['pc.unattended', s.unattended], ['pc.withPerson', s.withPerson], ['pc.calendar', s.calendar]]
  return (
    <Card className="cu-pc" aria-labelledby="cu-pc-title">
      <div className="cu-pc-head">
        <h2 id="cu-pc-title" className="cu-pc-title">{tt('pc.title')}</h2>
        {head && <span className="cu-pc-note">{head}</span>}
        {onRefresh && <Button size="sm" onClick={onRefresh} disabled={busy}>{tt('pc.refresh')}</Button>}
      </div>
      {!(bill.units || []).length ? <p className="cu-pc-note">{tt('pc.empty')}</p> : (
        <>
          <dl className="cu-hb-figs cu-pc-figs">
            {figs.map(([k, v]) => <div className="cu-hb-fig" key={k}><dt>{tt(k)}</dt><dd>{v}</dd></div>)}
          </dl>
          <p className="cu-pc-note">{tt('pc.apiEq', { date: s.revised || '—' })} · {tt('pc.tokens', s.tokens)}</p>
          <h3 className="cu-pc-sub">{tt('pc.top')}</h3>
          <ol className="cu-pc-top">
            {topUnits(bill).map((u, i) => <li key={i}><code>{u.unit}</code><span>{u.cost}</span></li>)}
          </ol>
          <details className="cu-pc-fold">
            <summary>{tt('pc.byPhase')}</summary>
            <table className="cu-pc-phases">
              <thead><tr><th scope="col">{tt('pc.phaseCol')}</th><th scope="col">{tt('pc.cost')}</th><th scope="col">{tt('pc.time')}</th></tr></thead>
              <tbody>{phaseRows(bill).map((p) => (
                <tr key={p.phase}><td>{p.phase === 'other' ? tt('pc.other') : p.phase}</td><td>{p.cost}</td><td>{p.time}</td></tr>
              ))}</tbody>
            </table>
          </details>
        </>
      )}
      {s.incomplete && <p className="cu-pc-note cu-pc-gaps"><strong>{tt('pc.incomplete')}</strong> · {gaps.join(' · ')} · {tt('pc.more')}</p>}
      {bill.before && <p className="cu-pc-note">{tt('pc.before', { cost: money(bill.before.cost_usd), time: fmtDuration(bill.before.seconds) })}</p>}
    </Card>
  )
}
