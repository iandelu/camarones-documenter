import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Skeleton } from '@camaron/ui'
import { useCmd } from '../hooks.js'
import { Failed, JobOutput, Page } from '../parts.jsx'
import Commands from './Commands.jsx'
import { t } from '../i18n.js'

// The team by task: the team's cam-docs repo and sharing with it (where it stands, share now), the agent config and
// hooks that came with it and this machine has not approved, and the plugins. The board and CI are the portal's.
// A kind or a state the CLI names in English (trust, plugins), in the user's words; an unknown one as it comes.
const word = (family, v) => { const k = `${family}.${v}`; const w = t(k); return w === k ? v : w }

export default function Team({ srv, jobs }) {
  return (
    <Page title={t('nav.team')}>
      <Repo srv={srv} jobs={jobs} />
      <Trust srv={srv} jobs={jobs} />
      <Plugins srv={srv} jobs={jobs} />
      <div className="row">
        <Button size="sm" variant="ghost" href="../#/kanban">{t('tm.board')}</Button>
        <Button size="sm" variant="ghost" href="../#/ci">{t('tm.ci')}</Button>
      </div>
      <Commands srv={srv} jobs={jobs} section="team" />
    </Page>
  )
}

// The team's repo (remote) and sharing (env.sync_status / env.share): sharing is the team action — checkpoint, bring
// in the team's work, push; a clash is undone and reported, never forced.
function Repo({ srv, jobs }) {
  const [s, setS] = useState(null)
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const c = useCmd(srv, jobs)
  const load = (fetch) => srv.get(`sync${fetch ? '?fetch=1' : ''}`)
    .then((x) => { setS(x); setUrl(x.remote || ''); setError('') }, (e) => setError(e.message))
  useEffect(() => { load(false) }, [])
  const cmd = async (name, args) => { await c.run(name, args); load(false) }
  async function share() {
    setBusy('share')
    setResult(null)
    try { const r = await srv.post('sync/share', {}); setResult(r.result); setS(r.sync) } catch (e) { setResult({ status: 'error', detail: e.message }) } finally { setBusy('') }
  }
  async function check() { setBusy('check'); try { await load(true) } finally { setBusy('') } }
  const ok = result && ['pushed', 'up-to-date', 'nothing'].includes(result.status)
  const say = (r) => { const k = `sy.${r.status}`; const m = t(k, { detail: r.detail || '' }); return m === k ? r.status : m }
  const clean = url.trim()
  return (
    <Card className="dk-run" data-tour="team-repo">
      <span className="eyebrow">{t('tm.repo')}</span>
      <div className="row">
        <input className="cu-input dk-grow" value={url} placeholder="git@github.com:equipo/cam-docs.git" aria-label={t('tm.repo')}
               onChange={(e) => setUrl(e.target.value)} />
        <Button size="sm" disabled={c.running || !clean || clean === s?.remote || clean.startsWith('-')}
                onClick={() => cmd('remote', { url: clean })}>{t('tm.save')}</Button>
      </div>
      {error ? <Failed title={t('tm.failed')} detail={error} onRetry={() => { setError(''); load(false) }} />
        : !s ? <Skeleton lines={2} /> : !s.remote ? <p className="muted small">{t('tm.noRemote')}</p> : (<>
        <div className="dk-stats dk-stats-sm">
          <div><span className="eyebrow">{t('tm.ahead')}</span><b className="dk-stat-sm">{s.ahead ?? '—'}</b></div>
          <div><span className="eyebrow">{t('tm.behind')}</span><b className="dk-stat-sm">{s.behind ?? '—'}</b></div>
          <div><span className="eyebrow">{t('tm.pending')}</span><b className="dk-stat-sm">{s.pending.length}</b></div>
        </div>
        <div className="row">
          <Button size="sm" variant="primary" disabled={!!busy} onClick={share}>{t('tm.share')}</Button>
          <Button size="sm" variant="ghost" disabled={!!busy} onClick={check}>{t('tm.check')}</Button>
          <label className="dk-check"><input type="checkbox" checked={!!s.auto} disabled={c.running}
            onChange={() => cmd('share', { auto: s.auto ? 'off' : 'on' })} />{t('tm.auto')}</label>
        </div>
      </>)}
      {s?.fetched && !s.fetched.ok ? <Aviso tone="warn" title={t('tm.fetchFailed')} detail={s.fetched.reason} /> : null}
      {result ? (ok ? <p className="small" role="status">{say(result)}</p> : <Aviso tone="error" title={say(result)} />) : null}
      <JobOutput c={c} />
    </Card>
  )
}

// What came with the team's repo (agent config, plugins) and this machine has not approved: nothing of it loads
// until it is. Approving runs `trust --yes` after a dialog that lists it. The method hooks, on or off.
function Trust({ srv, jobs }) {
  const list = useCmd(srv, jobs, { quiet: true })
  const hooks = useCmd(srv, jobs, { quiet: true })
  const act = useCmd(srv, jobs)
  const dialog = useRef(null)
  const load = () => { list.run('trust', { json: true }); hooks.run('hooks', { json: true }) }
  useEffect(() => { load() }, [])
  const rows = list.job?.result?.pending
  const on = hooks.job?.result?.enabled
  const then = async (p) => { await p; load() }
  return (
    <Card className="dk-run" data-tour="team-trust">
      <span className="eyebrow">{t('tm.trust')}</span>
      {rows ? (rows.length ? (<>
        <ul className="dk-units">{rows.map((r) => (
          <li key={r.kind + r.label} className="dk-unit"><div className="dk-unit-main"><b>{r.label}</b>
            <span className="muted small">{word('tk', r.kind)}{r.detail ? ` · ${r.detail}` : ''}</span></div>
            <span className="cu-chip cu-chip--warn">{word('ts', r.status)}</span></li>))}</ul>
        <div className="row"><Button size="sm" variant="primary" disabled={act.running} onClick={() => dialog.current.showModal()}>
          {t('tm.approve', { n: rows.length })}</Button></div>
        <dialog ref={dialog} className="dk-dialog">
          <h2>{t('tm.approveTitle')}</h2>
          <p>{t('tm.approveText')}</p>
          <ul>{rows.map((r) => <li key={r.kind + r.label}><code>{r.label}</code></li>)}</ul>
          <div className="row">
            <Button variant="ghost" onClick={() => dialog.current.close()}>{t('cancel')}</Button>
            <Button variant="primary" onClick={() => { dialog.current.close(); then(act.run('trust', {}, true)) }}>{t('tm.approveGo')}</Button>
          </div>
        </dialog>
      </>) : <p className="small">{t('tm.trusted')}</p>) : <JobOutput c={list} />}
      {on != null ? (
        <label className="dk-check"><input type="checkbox" checked={on} disabled={act.running}
          onChange={() => then(act.run('hooks', { state: on ? 'off' : 'on' }))} />{t('tm.hooks')}</label>
      ) : null}
      <JobOutput c={act} />
    </Card>
  )
}

// The plugins: the kit's own (installed with Camarón, nothing downloaded) and the team's (folders in the team repo's
// .camarones/plugins/, they arrive when you pull it). On or off is this machine's choice only; a team plugin that
// runs code or steers an agent is approved first (the card above), one that sends the docs out is off until enabled.
const PLUGIN_STATE = { active: ['ok', 'tm.active'], 'off on this machine': [undefined, 'tm.off'], invalid: ['bad', 'tm.invalid'] }
function Plugins({ srv, jobs }) {
  const list = useCmd(srv, jobs, { quiet: true })
  const act = useCmd(srv, jobs)
  useEffect(() => { list.run('plugins', { json: true }) }, [])
  const rows = list.job?.result
  const toggle = async (p) => { await act.run('plugins', { action: p.status === 'active' ? 'disable' : 'enable', target: p.name }); list.run('plugins', { json: true }) }
  if (Array.isArray(rows) && !rows.length) return null
  return (
    <Card className="dk-run" data-tour="team-plugins">
      <span className="eyebrow">{t('tm.plugins')}</span>
      <p className="muted small">{t('tm.pluginsLead')}</p>
      {Array.isArray(rows) ? (
        <ul className="dk-units">{rows.map((p) => {
          // a kit plugin that sends the docs out (Confluence, Notion) is simply off until enabled here
          const [state, label] = PLUGIN_STATE[p.status] || (p.source === 'kit' ? [undefined, 'tm.off'] : ['warn', 'tm.needsOk'])
          return (
            <li key={p.name} className="dk-unit">
              <div className="dk-unit-main"><b>{p.name} <span className="muted small">{p.version}</span></b>
                <span className="muted small">{t(p.source === 'kit' ? 'tm.fromKit' : 'tm.fromTeam')} · {(p.provides || []).map((k) => word('pk', k)).join(', ')}</span>
                {p.errors?.length ? <span className="small">{p.errors.join(' · ')}</span> : null}</div>
              <div className="row dk-unit-acts">
                {p.runs_code ? <span className="cu-chip cu-chip--warn">{t('tm.runsCode')}</span> : null}
                {p.sends_data ? <span className="cu-chip cu-chip--warn">{t('tm.sendsData')}</span> : null}
                <span className={'cu-chip' + (state ? ` cu-chip--${state}` : '')}>{t(label)}</span>
                {p.status !== 'invalid' ? <Button size="sm" variant="ghost" disabled={act.running} onClick={() => toggle(p)}>{p.status === 'active' ? t('tm.disable') : t('tm.enable')}</Button> : null}
              </div>
            </li>
          )
        })}</ul>
      ) : <JobOutput c={list} />}
      <JobOutput c={act} />
    </Card>
  )
}
