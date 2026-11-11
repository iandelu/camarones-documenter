import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { t } from '../i18n/index.js'
import { Button, Chip } from './components.jsx'
import { advisories, applyFilter, compareVersions, facets, isMajor, latestOf, matrix, outdated, placesOf, proposal,
  rowsOf, versionSpan } from './libs.js'
import { severities } from './result.js'

// The Libraries screen, shared by the portal (read-only) and the desktop app (`actions`, `status`, `renderUpdate`).
// One line per library with the version its repos use and the latest stable one (lib/latest.py), no column per repo,
// so nothing scrolls sideways; the filters and the table's header stick while the page scrolls. A line opens on how
// to update it, why it is flagged and why it is there.

export const fill = (s, vars = {}) => s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m))
const tv = (k, vars) => fill(t(k), vars)
export const SEV = { critical: 'bad', high: 'bad', medium: 'warn', moderate: 'warn' }
const word = (prefix, k) => { const w = t(`${prefix}.${k}`); return w === `${prefix}.${k}` ? k : w }
export const sevWord = (s) => word('lb.sev', s)
const day = (iso) => (iso || '').slice(0, 10)
const libCount = (rows) => new Set(rows.map((r) => r.ecosystem + r.name)).size
const lowest = (item) => Object.values(item.cells).map((c) => c.exact).filter(Boolean).sort(compareVersions)[0] || null

export function LibrariesBoard({ inv, actions = null, status = null, renderUpdate = null, repo = '' }) {
  const [f, setF] = useState(() => (repo ? { repo } : {}))
  const [open, setOpen] = useState(null)
  const root = useRef(null)
  const bar = useRef(null)
  useEffect(() => { setF((cur) => ((cur.repo || '') === repo ? cur : { ...cur, repo })) }, [repo])
  useEffect(() => {                                          // the table's header sticks right under the filters
    if (typeof ResizeObserver === 'undefined' || !bar.current) return undefined
    const ro = new ResizeObserver(() => root.current?.style.setProperty('--cu-libs-bar-h', `${bar.current?.offsetHeight || 0}px`))
    ro.observe(bar.current)
    return () => ro.disconnect()
  }, [])
  const rows = inv.libraries || []
  const latest = inv.latest || null
  const shown = useMemo(() => applyFilter(rows, f, latest), [rows, f, latest])
  const m = useMemo(() => matrix(shown), [shown])
  const fc = useMemo(() => facets(rows), [rows])
  const set = (k) => (v) => setF((cur) => ({ ...cur, [k]: v }))
  return (
    <section className="cu-libs" ref={root}>
      <p className="cu-libs-lead">{t('lb.lead')}</p>
      <Summary inv={inv} rows={rows} />
      {actions ? (
        <div className="cu-libs-actions" data-tour="libs-actions">{actions}<span className="cu-libs-note">{t('lb.sends')}</span></div>
      ) : <p className="cu-libs-note">{t('lb.readOnly')}</p>}
      {status}
      {rows.length ? (<>
        <div className="cu-libs-bar" data-tour="libs-filters" ref={bar}>
          <input type="search" className="cu-input cu-libs-search" placeholder={t('lb.search')} aria-label={t('lb.search')}
            value={f.q || ''} onChange={(e) => set('q')(e.target.value)} />
          <Facet label={t('lb.category')} value={f.category} onChange={set('category')} options={fc.category} />
          <Facet label={t('lb.repo')} value={f.repo} onChange={set('repo')} options={fc.repo} />
          <Facet label={t('lb.scope')} value={f.scope} onChange={set('scope')} options={fc.scope} />
          <Check label={t('lb.onlyVuln')} checked={!!f.vulnerable} onChange={set('vulnerable')} />
          {latest ? <Check label={t('lb.onlyOutdated')} checked={!!f.outdated} onChange={set('outdated')} /> : null}
        </div>
        {m.items.length ? (
          <table className="cu-libs-table" data-tour="libs-table">
            <colgroup><col style={{ width: '46%' }} /><col style={{ width: '18%' }} /><col style={{ width: '20%' }} /><col style={{ width: '16%' }} /></colgroup>
            <thead><tr>
              <th scope="col">{t('lb.library')}</th><th scope="col">{t('lb.version')}</th><th scope="col">{t('lb.latest')}</th>
              <th scope="col"><span className="sr-only">{t('lb.action')}</span></th>
            </tr></thead>
            <tbody>{m.items.map((x) => (
              <Line key={x.key} item={x} latest={latest} open={open === x.key} onToggle={() => setOpen(open === x.key ? null : x.key)}
                rows={rows} scanned={!!inv.vulns} renderUpdate={renderUpdate} />
            ))}</tbody>
          </table>
        ) : <p className="cu-libs-note">{t('lb.nothing')}</p>}
      </>) : <p className="cu-libs-note">{t('lb.none')}</p>}
    </section>
  )
}

function Summary({ inv, rows }) {
  const sev = severities(rows)
  const latest = inv.latest || null
  const newer = latest ? matrix(rows).items.filter((x) => outdated(x, latestOf(latest, x)) === true).length : 0
  const looked = !latest ? t('lb.neverLooked')
    : latest.failed?.length ? tv('lb.lookFailed', { registries: latest.failed.join(', '), day: day(latest.at) })
      : tv('lb.lookedAt', { day: day(latest.at) })
  return (
    <div className="cu-libs-summary">
      <b>{tv('lb.count', { n: libCount(rows) })}</b>
      {inv.vulns ? (sev.length ? sev.map(([s, n]) => <Chip key={s} state={SEV[s]}>{`${n} ${sevWord(s)}`}</Chip>)
        : <Chip state="ok">{t('lb.cvClean')}</Chip>) : null}
      {newer ? <Chip state="warn">{tv('lb.newer', { n: newer })}</Chip> : null}
      <span className="cu-libs-note">{inv.vulns ? tv('lb.cvAt', { day: day(inv.vulns.at) }) : t('lb.cvNever')}</span>
      <span className="cu-libs-note">{looked}</span>
    </div>
  )
}

function Facet({ label, value, onChange, options }) {
  return (
    <select className="cu-input cu-libs-select" value={value || ''} aria-label={label} onChange={(e) => onChange(e.target.value)}>
      <option value="">{`${label}: ${t('lb.all')}`}</option>
      {options.map(([k, n]) => <option key={k} value={k}>{`${k} (${n})`}</option>)}
    </select>
  )
}

const Check = ({ label, checked, onChange }) => (
  <label className="cu-libs-check"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />{label}</label>
)

// One library: its versions, the latest, and Update ▾ unless it is up to date with no known vulnerability. Opening it
// scrolls it into view.
function Line({ item, latest, open, onToggle, rows, scanned, renderUpdate }) {
  const ref = useRef(null)
  useEffect(() => { if (open) ref.current?.scrollIntoView?.({ block: 'nearest' }) }, [open])
  const newest = latestOf(latest, item)
  const behind = outdated(item, newest)
  const update = !(behind === false && !item.vulns.length)
  const cls = [item.worst ? `vuln sev-${SEV[item.worst] || 'low'}` : '', open ? 'on' : ''].filter(Boolean).join(' ')
  return (<>
    <tr ref={ref} className={cls || undefined}>
      <td>
        <button type="button" className="cu-libs-name" aria-expanded={open} onClick={onToggle}><code>{item.name}</code></button>
        {' '}<span className="cu-libs-eco">{item.ecosystem}</span>
        {item.worst ? <> <Chip state={SEV[item.worst]}>{sevWord(item.worst)}</Chip></> : null}
        {item.drift ? <> <Chip state="warn">{t('lb.versions')}</Chip></> : null}
        <br /><Where item={item} />
      </td>
      <td className="cu-libs-v">{versionSpan(item)}</td>
      <td className="cu-libs-v">{newest ? <>
        {newest}
        {behind === false ? <> <Chip state="ok">{t('lb.upToDate')}</Chip></> : null}
        {behind && isMajor(lowest(item), newest) ? <> <Chip state="warn">{t('lb.major')}</Chip></> : null}
      </> : '—'}</td>
      <td className="cu-libs-act">{update
        ? <Button size="sm" aria-expanded={open} onClick={onToggle}>{`${t('lb.updateOpen')} ▾`}</Button> : null}</td>
    </tr>
    {open ? (
      <tr className="cu-libs-open"><td colSpan={4}>
        <LibraryDetail item={item} rows={rowsOf(rows, item.key)} latest={latest} scanned={scanned} renderUpdate={renderUpdate} />
      </td></tr>
    ) : null}
  </>)
}

// Which repos have this library, the flagged ones first, then up to three names: the line itself says where.
export function Where({ item }) {
  const { shown, more } = placesOf(item)
  return (
    <span className="cu-libs-where">{t('lb.in')} {shown.map((p, i) => (
      <Fragment key={p.repo}>{i ? ' · ' : ''}{p.flagged ? <b className="cu-libs-where-bad">{p.repo}</b> : p.repo}</Fragment>
    ))}{more ? ` ${tv('lb.more', { n: more })}` : ''}</span>
  )
}

// An open library: how to update it in each repo first, then why it is flagged, then why it is there.
export function LibraryDetail({ item, rows, latest, scanned, renderUpdate }) {
  const advs = advisories(item.vulns)
  const newest = latestOf(latest, item)
  return (
    <div className="cu-libs-detail">
      <section>
        <h3>{t('lb.updateTitle')}</h3>
        <ul className="cu-libs-repos">{rows.map((r) => {
          const p = proposal(r, newest)
          return (
            <li key={r.repo + r.source}>
              <span className="cu-libs-repo"><b>{r.repo}</b> <span className="cu-libs-note">
                {`${r.source.split(':').slice(1).join(':')} · ${word('lb.scope', r.scope)} · ${r.version || r.declared || '—'} →`}</span></span>
              {renderUpdate ? renderUpdate(r, p) : <BumpCommand row={r} proposal={p} />}
            </li>
          )
        })}</ul>
      </section>
      <section>
        <h3>{t('lb.flagged')}</h3>
        {!scanned ? <p className="cu-libs-note">{t('lb.notScanned')}</p>
          : !advs.length ? <p>{t('lb.clean')}</p> : (<>
            <p>{tv('lb.flaggedLead', { n: advs.length })}</p>
            <div className="cu-libs-advs">{advs.map((v) => <Advisory key={v.id} v={v} />)}</div>
          </>)}
      </section>
      <section>
        <h3>{t('lb.why')}</h3>
        <p className="cu-libs-note">{tv('lb.whyLead', { category: item.category, language: item.language })}</p>
        <table className="cu-libs-why"><thead><tr><th>{t('lb.repo')}</th><th>{t('lb.manifest')}</th><th>{t('lb.declared')}</th>
          <th>{t('lb.version')}</th><th>{t('lb.scope')}</th></tr></thead>
          <tbody>{rows.map((r) => (
            <tr key={r.repo + r.source}>
              <th>{r.repo}</th>
              <td><code>{r.source.split(':').slice(1).join(':')}</code></td>
              <td><code>{r.declared || '—'}</code>{r.managedBy ? <span className="cu-libs-note">{` · ${tv('lb.managed', { by: r.managedBy })}`}</span> : null}</td>
              <td className={(r.vulns || []).length ? 'cell-vuln' : undefined}>{r.version || '—'}</td>
              <td>{word('lb.scope', r.scope)}</td>
            </tr>))}</tbody></table>
      </section>
    </div>
  )
}

// The versions worth proposing, as chips that pick one: the one that fixes the advisories and the latest stable.
export function Suggestions({ proposal: p, value, onPick }) {
  const opts = [p.fix && { v: p.fix, label: tv('lb.fixes', { v: p.fix }) },
    p.latest && p.latest !== p.fix && { v: p.latest, label: tv('lb.latestIs', { v: p.latest }) }].filter(Boolean)
  if (!opts.length) return null
  return (
    <span className="cu-libs-sugg">{opts.map((o) => (
      <button key={o.v} type="button" className="cu-chip cu-libs-pick" aria-pressed={value === o.v} onClick={() => onPick?.(o.v)}>{o.label}</button>
    ))}</span>
  )
}

// The portal runs nothing on the machine: in place of the app's Update it gives the command, ready to copy.
export function BumpCommand({ row, proposal: p }) {
  const [version, setVersion] = useState(p.version)
  const [copied, setCopied] = useState(false)
  const cmd = `camaron bump ${row.repo} ${row.name} ${version || '<version>'}`
  const copy = async () => {
    try { await navigator.clipboard.writeText(cmd); setCopied(true) } catch { /* no clipboard here: the command stays selectable */ }
  }
  return (
    <div className="cu-libs-bump">
      <Suggestions proposal={p} value={version} onPick={(v) => { setVersion(v); setCopied(false) }} />
      <span className="cu-libs-cmd"><code>{cmd}</code><Button size="sm" variant="ghost" onClick={copy}>{t(copied ? 'lb.copied' : 'lb.copy')}</Button></span>
      <span className="cu-libs-note">{t('lb.bumpNote')}</span>
    </div>
  )
}

// An advisory as the last scan kept it: what it is, which versions it affects and its text; a scan from before the
// full text was kept links to it instead.
export function Advisory({ v }) {
  const osv = `https://osv.dev/vulnerability/${encodeURIComponent(v.id)}`
  const ranges = (v.ranges || []).map((r) => (r.fixed ? tv('lb.range', { from: r.introduced, to: r.fixed })
    : r.last_affected ? tv('lb.rangeLast', { from: r.introduced, to: r.last_affected }) : tv('lb.rangeOpen', { from: r.introduced })))
  return (
    <details className="cu-libs-adv">
      <summary>
        <b>{v.cve || v.id}</b> <Chip state={SEV[v.severity]}>{`${sevWord(v.severity)}${v.score ? ` ${v.score}` : ''}`}</Chip>{' '}
        <span>{v.summary}</span>{v.fixed ? <> <b>{tv('lb.fixed', { v: v.fixed })}</b></> : null}
      </summary>
      <div className="cu-libs-adv-body">
        <dl className="cu-libs-adv-facts">
          <dt>{t('lb.ids')}</dt><dd><code>{[v.id, ...(v.aliases || []).filter((a) => a !== v.id)].join(' · ')}</code></dd>
          {ranges.length ? <><dt>{t('lb.affects')}</dt><dd>{ranges.join('; ')}</dd></> : null}
          {v.published ? <><dt>{t('lb.published')}</dt><dd>{`${v.published.slice(0, 10)}${v.modified ? ` · ${tv('lb.modified', { day: v.modified.slice(0, 10) })}` : ''}`}</dd></> : null}
          {v.cwes?.length ? <><dt>{t('lb.cwe')}</dt><dd>{v.cwes.join(', ')}</dd></> : null}
        </dl>
        {v.details ? <div className="cu-libs-adv-text">{v.details}</div>
          : <p className="cu-libs-note">{t(v.details === undefined ? 'lb.rescan' : 'lb.noText')}</p>}
        <ul className="cu-libs-adv-refs">
          <li><a href={osv} target="_blank" rel="noreferrer">osv.dev</a></li>
          {(v.references || []).map((r) => <li key={r.url}><a href={r.url} target="_blank" rel="noreferrer">{r.url}</a>
            {r.type ? <span className="cu-libs-note">{` ${r.type.toLowerCase()}`}</span> : null}</li>)}
        </ul>
      </div>
    </details>
  )
}
