import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Chip, Skeleton } from '@camaron/ui'
import { setupProgress } from '../quality.js'
import { useCmd } from '../hooks.js'
import { Failed, JobOutput, Page } from '../parts.jsx'
import Commands from './Commands.jsx'
import { t } from '../i18n.js'

// This machine by task: prepare it (setup, with its progress), the language and models of the agent sessions, the
// forge tokens (kept in the OS keychain), this project's repos and plan, the kit itself; and, apart, uninstall —
// previewed first. Every action is a catalog command run by the server (lib/appapi.py).
export default function Machine({ srv, jobs, app }) {
  const [m, setM] = useState(null)
  const [error, setError] = useState('')
  const load = () => srv.get('app/machine').then((x) => { setM(x); setError('') }, (e) => setError(e.message))
  useEffect(() => { load() }, [])
  const p = { srv, jobs, m, reload: load }
  return (
    <Page title={t('nav.machine')}>
      {error ? <Failed title={t('mc.failed')} detail={error} onRetry={() => { setError(''); load() }} /> : null}
      {!m && !error ? <Skeleton lines={6} /> : null}
      {m ? (<>
        <Setup {...p} />
        <Settings {...p} />
        <Tokens srv={srv} />
        <Repos {...p} />
        <Kit {...p} app={app} />
        <Commands srv={srv} jobs={jobs} section="machine" />
        <Uninstall srv={srv} jobs={jobs} app={app} />
      </>) : null}
    </Page>
  )
}

function Setup({ srv, jobs, m }) {
  const c = useCmd(srv, jobs)
  const { done, pct } = setupProgress(c.job?.lines, m.setup_steps)
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('mc.setup')}</span>
      {c.job ? <progress className="dk-progress" value={c.running ? pct : 100} max={100} aria-label={t('mc.setup')} /> : null}
      <div className="row">
        <Button size="sm" variant="primary" disabled={c.running} onClick={() => c.run('setup', {})}>{t('mc.setupGo')}</Button>
        {c.running ? <span className="muted small">{done}/{m.setup_steps}</span> : null}
      </div>
      <JobOutput c={c} />
    </Card>
  )
}

function Settings({ srv, jobs, m, reload }) {
  const c = useCmd(srv, jobs)
  const s = m.settings
  const [codex, setCodex] = useState(s.codex_model || '')
  const set = async (key, value) => { await c.run('config', { action: 'set', key, value }); reload() }
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('mc.settings')}</span>
      <div className="dk-fields">
        <div className="cu-field"><label className="cu-field-label" htmlFor="mc-lang">{t('mc.lang')}</label>
          <select id="mc-lang" className="cu-input" value={s.lang} disabled={c.running} onChange={(e) => set('lang', e.target.value)}>
            <option value="es">Español</option><option value="en">English</option></select></div>
        <div className="cu-field"><label className="cu-field-label" htmlFor="mc-model">{t('mc.model')}</label>
          <select id="mc-model" className="cu-input" value={s.model} disabled={c.running} onChange={(e) => set('model', e.target.value)}>
            {m.models.map((x) => <option key={x} value={x}>{x}</option>)}</select></div>
        <div className="cu-field"><label className="cu-field-label" htmlFor="mc-codex">{t('mc.codex')}</label>
          <input id="mc-codex" className="cu-input" value={codex} disabled={c.running} onChange={(e) => setCodex(e.target.value)}
                 onBlur={() => codex.trim() && codex.trim() !== s.codex_model && set('codex_model', codex.trim())} /></div>
      </div>
      <p className="muted small">{t('mc.agents', { list: m.agents.length ? m.agents.map((a) => a.label).join(', ') : t('mc.noAgents') })}</p>
      <JobOutput c={c} />
    </Card>
  )
}

// GitLab / GitHub tokens in the OS keychain: they reach the server in a request body only (never a command line)
// and never come back. `host` fills the form in (the first-run wizard, for a repo that failed to clone).
export function Tokens({ srv, host = '' }) {
  const [d, setD] = useState(null)
  const [form, setForm] = useState({ host, kind: /github/i.test(host) ? 'github' : 'gitlab', token: '' })
  const [note, setNote] = useState({ ok: '', error: '' })
  const [busy, setBusy] = useState(false)
  const load = () => srv.get('app/creds').then(setD, (e) => setNote({ ok: '', error: e.message }))
  useEffect(() => { load() }, [])
  async function act(path, body, ok) {
    setBusy(true)
    setNote({ ok: '', error: '' })
    try { const r = await srv.post(path, body); setNote({ ok: ok(r), error: '' }); await load(); return true } catch (e) { setNote({ ok: '', error: e.message }); return false } finally { setBusy(false) }
  }
  const save = async (anyway) => {
    if (await act('app/creds', { ...form, anyway }, (r) => t('mc.tokSaved', { host: r.host, user: r.user || '—' }))) setForm((f) => ({ ...f, token: '' }))
  }
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('mc.tokens')}</span>
      {d?.hosts.length ? (
        <ul className="dk-units">{d.hosts.map((h) => (
          <li key={h.host} className="dk-unit"><div className="dk-unit-main"><b>{h.host}</b><span className="muted small">{h.kind}{h.user ? ` · ${h.user}` : ''}</span></div>
            <div className="row dk-unit-acts"><Chip state={h.saved ? 'ok' : 'warn'}>{h.saved ? t('mc.tokOk') : t('mc.tokMissing')}</Chip>
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => act('app/creds/test', { host: h.host },
                (r) => (r.ok ? t('mc.tokWorks', { user: r.info }) : t('mc.tokFails', { err: r.info })))}>{t('mc.tokTest')}</Button>
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => act('app/creds/delete', { host: h.host }, () => t('mc.tokDeleted'))}>{t('mc.tokDelete')}</Button></div>
          </li>))}</ul>
      ) : d ? <p className="muted small">{t('mc.tokNone')}</p> : null}
      <form className="dk-fields" onSubmit={(e) => { e.preventDefault(); save(false) }}>
        <div className="cu-field"><label className="cu-field-label" htmlFor="tk-host">{t('mc.tokHost')}</label>
          <input id="tk-host" className="cu-input" value={form.host} onChange={set('host')} placeholder="gitlab.example.com" required /></div>
        <div className="cu-field"><label className="cu-field-label" htmlFor="tk-kind">{t('mc.tokKind')}</label>
          <select id="tk-kind" className="cu-input" value={form.kind} onChange={set('kind')}><option value="gitlab">GitLab</option><option value="github">GitHub</option></select></div>
        <div className="cu-field"><label className="cu-field-label" htmlFor="tk-token">{t('mc.tokToken')}</label>
          <input id="tk-token" className="cu-input" type="password" autoComplete="off" value={form.token} onChange={set('token')} required /></div>
        <div className="cu-field"><Button type="submit" size="sm" disabled={busy || !form.host.trim() || !form.token.trim()}>{t('mc.tokSave')}</Button></div>
      </form>
      {note.ok ? <p className="small" role="status">{note.ok}</p> : null}
      {note.error ? (
        <Aviso tone="error" title={t('unit.failed')} detail={note.error}>
          {form.token ? <Button size="sm" variant="ghost" disabled={busy} onClick={() => save(true)}>{t('mc.tokAnyway')}</Button> : null}
        </Aviso>
      ) : null}
      <p className="muted small">{t('mc.tokWhere', { where: d?.backend || '…' })}</p>
    </Card>
  )
}

// This project's repos (cloned here or not, the stack its docs use) and its plan, quick or full.
function Repos({ srv, jobs, m, reload }) {
  const c = useCmd(srv, jobs)
  const [stacks, setStacks] = useState(() => Object.fromEntries(m.repos.map((r) => [r.name, r.stack || ''])))
  useEffect(() => { setStacks(Object.fromEntries(m.repos.map((r) => [r.name, r.stack || '']))) }, [m])
  const run = async (cmd, args) => { await c.run(cmd, args); reload() }
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('mc.repos')}</span>
      {m.repos.length ? (
        <ul className="dk-units">{m.repos.map((r) => (
          <li key={r.name} className="dk-unit">
            <div className="dk-unit-main"><b>{r.name}</b></div>
            <div className="row dk-unit-acts">
              <Chip state={r.cloned ? 'ok' : 'warn'}>{r.cloned ? t('mc.cloned') : t('mc.notCloned')}</Chip>
              <input className="cu-input dk-stack" value={stacks[r.name] || ''} placeholder={t('mc.detected')} aria-label={t('mc.stack', { repo: r.name })}
                     onChange={(e) => setStacks((s) => ({ ...s, [r.name]: e.target.value }))} />
              {(stacks[r.name] || '') !== (r.stack || '') ? (
                <Button size="sm" disabled={c.running} onClick={() => run('stack', stacks[r.name].trim() ? { repo: r.name, text: stacks[r.name].trim() } : { repo: r.name, reset: true })}>{t('tm.save')}</Button>
              ) : r.stack ? <Button size="sm" variant="ghost" disabled={c.running} onClick={() => run('stack', { repo: r.name, reset: true })}>{t('mc.reset')}</Button> : null}
            </div>
          </li>))}</ul>
      ) : <p className="muted small">{t('mc.noRepos')}</p>}
      <div className="row">
        <Button size="sm" disabled={c.running} onClick={() => run('sync', {})}>{t('mc.sync')}</Button>
        <Button size="sm" variant="ghost" disabled={c.running} onClick={() => run('detect', {})}>{t('mc.detect')}</Button>
        <label className="dk-inline">{t('mc.profile')}
          <select className="cu-input dk-select" value={m.profile || ''} disabled={c.running} onChange={(e) => e.target.value && run('profile', { name: e.target.value })}>
            {!m.profile ? <option value="">—</option> : null}<option value="quick">{t('mc.quick')}</option><option value="full">{t('mc.full')}</option></select></label>
      </div>
      <JobOutput c={c} />
    </Card>
  )
}

// The kit: update the global one (then restart the app on it), or put back what the kit owns.
function Kit({ srv, jobs, m, app }) {
  const c = useCmd(srv, jobs)
  const [updated, setUpdated] = useState(false)
  const update = async () => { const end = await c.run('self-update', {}); if (end?.status === 'done') setUpdated(true) }
  return (
    <Card className="dk-run">
      <div className="row"><span className="eyebrow">{t('mc.kit')}</span><span className="muted small">{t('mc.version', { v: m.kit.version })}</span></div>
      <div className="row">
        {m.kit.global ? <Button size="sm" disabled={c.running} onClick={update}>{t('mc.update')}</Button> : <span className="muted small">{t('mc.localKit')}</span>}
        <Button size="sm" variant="ghost" disabled={c.running} onClick={() => c.run('repair', {})}>{t('mc.repair')}</Button>
        {updated && app.relaunch ? <Button size="sm" variant="primary" onClick={() => app.relaunch()}>{t('mc.relaunch')}</Button> : null}
      </div>
      <JobOutput c={c} />
    </Card>
  )
}

// Uninstall, previewed first: `uninstall --dry-run` lists what goes (it only reads), and only then the real one,
// behind a dialog that repeats that list. No jokes here.
function Uninstall({ srv, jobs, app }) {
  const preview = useCmd(srv, jobs)
  const go = useCmd(srv, jobs)
  const [opts, setOpts] = useState({ user_level: false, no_backup: false })
  const dialog = useRef(null)
  const lines = preview.job?.status === 'done' ? preview.job.lines : null
  const args = (dry) => ({ ...(opts.user_level ? { user_level: true } : {}), ...(opts.no_backup && !dry ? { no_backup: true } : {}), ...(dry ? { dry_run: true } : {}) })
  const set = (k) => (e) => setOpts((o) => ({ ...o, [k]: e.target.checked }))
  return (
    <Card className="dk-run dk-cmd careful">
      <span className="eyebrow">{t('un.title')}</span>
      <p className="small">{t('un.lead')}</p>
      <label className="dk-check"><input type="checkbox" checked={opts.user_level} onChange={set('user_level')} disabled={go.running} />{t('un.global')}</label>
      <label className="dk-check"><input type="checkbox" checked={opts.no_backup} onChange={set('no_backup')} disabled={go.running} />{t('un.noBackup')}</label>
      <div className="row">
        <Button size="sm" disabled={preview.running || go.running} onClick={() => preview.run('uninstall', args(true))}>{t('un.preview')}</Button>
        {lines ? <Button size="sm" variant="danger" disabled={go.running} onClick={() => dialog.current.showModal()}>{t('un.go')}</Button> : null}
      </div>
      {lines && !go.job ? <pre className="dk-log">{lines.join('\n')}</pre> : <JobOutput c={go.job ? go : preview} />}
      {go.job?.status === 'done' ? (
        <div className="row"><span className="small">{t('un.done')}</span>{app.hub ? <Button size="sm" onClick={() => app.hub()}>{t('un.hub')}</Button> : null}</div>
      ) : null}
      <dialog ref={dialog} className="dk-dialog">
        <h2>{t('un.confirmTitle')}</h2>
        <p>{opts.no_backup ? t('un.confirmNoBackup') : t('un.confirmBackup')}</p>
        {lines ? <pre className="dk-log">{lines.filter((l) => l.trim().startsWith('•')).join('\n')}</pre> : null}
        <div className="row">
          <Button variant="ghost" onClick={() => dialog.current.close()}>{t('cancel')}</Button>
          <Button variant="danger" onClick={() => { dialog.current.close(); go.run('uninstall', args(false), true) }}>{t('un.go')}</Button>
        </div>
      </dialog>
    </Card>
  )
}
