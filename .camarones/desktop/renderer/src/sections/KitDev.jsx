import { useEffect, useRef, useState } from 'react'
import { Aviso, Button, Card, Chip } from '@camaron/ui'
import { pytestSummary } from '../quality.js'
import { useKit } from '../hooks.js'
import { Failed, JobOutput, Page } from '../parts.jsx'
import { t } from '../i18n.js'

// Kit dev, in a checkout of the kit only (lib/kitdev.py): the sandbox, the pytest suite, and the two UIs' npm and
// the desktop helpers' tests, with the check that both committed builds match their source.
export default function KitDev({ srv, jobs }) {
  const [info, setInfo] = useState(null)
  const [error, setError] = useState('')
  const load = () => srv.get('app/kitdev').then((x) => { setInfo(x); setError('') }, (e) => setError(e.message))
  useEffect(() => { load() }, [])
  const p = { srv, jobs, info, reload: load }
  return (
    <Page title={t('nav.kitdev')}>
      {error ? <Failed title={t('kd.failed')} detail={error} onRetry={load} /> : null}
      <Sandbox {...p} />
      <Tests {...p} />
      <Builds {...p} />
    </Page>
  )
}

function Sandbox({ srv, jobs, info, reload }) {
  const c = useKit(srv, jobs)
  const [line, setLine] = useState('status')
  const [opened, setOpened] = useState(null)
  const [last, setLast] = useState('')
  const dialog = useRef(null)
  const run = async (task, body) => { setLast(task); await c.run(task, body); reload() }
  const openWizard = async () => {
    try { const r = await srv.post('app/kitdev', { task: 'sandbox-open' }); setOpened(r.opened ? 'ok' : 'none') } catch (e) { setOpened(e.message) }
  }
  const traces = c.job && !c.running && last === 'sandbox-traces'
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('kd.sandbox')}</span>
      <p className="muted small">{t('kd.never')}</p>
      {info ? <div className="row"><code className="small">{info.sandbox}</code>
        <Chip state={info.sandbox_exists ? 'ok' : 'warn'}>{info.sandbox_exists ? t('kd.exists') : t('kd.missing')}</Chip></div> : null}
      <div className="row">
        <Button size="sm" disabled={c.running} onClick={() => run('sandbox-traces')}>{t('kd.traces')}</Button>
        <Button size="sm" variant="ghost" disabled={c.running} onClick={openWizard}>{t('kd.open')}</Button>
        <Button size="sm" variant="ghost" disabled={c.running} onClick={() => dialog.current.showModal()}>{t('kd.reset')}</Button>
      </div>
      <div className="row">
        <code className="muted">camaron</code>
        <input className="cu-input dk-grow" value={line} onChange={(e) => setLine(e.target.value)} aria-label={t('kd.cli')} />
        <Button size="sm" variant="ghost" disabled={c.running || !line.trim()} onClick={() => run('sandbox-cli', { line })}>{t('kd.runCli')}</Button>
      </div>
      {opened ? (opened === 'ok' ? <p className="small" role="status">{t('kd.opened')}</p>
        : <Aviso tone="warn" title={opened === 'none' ? t('kd.noTerminal') : opened} />) : null}
      {/* traces exits 1 when the kit left something: with the project installed that is expected, not a failure */}
      {traces && c.job.rc === 1 ? <Chip state="warn">{t('kd.traced')}</Chip> : null}
      {traces && c.job.rc === 0 ? <Chip state="ok">{t('kd.pristine')}</Chip> : null}
      <JobOutput c={c} />
      <dialog ref={dialog} className="dk-dialog">
        <h2>{t('kd.resetTitle')}</h2>
        <p>{t('kd.resetText')}</p>
        <div className="row">
          <Button variant="ghost" onClick={() => dialog.current.close()}>{t('cancel')}</Button>
          <Button variant="danger" onClick={() => { dialog.current.close(); run('sandbox-reset') }}>{t('kd.reset')}</Button>
        </div>
      </dialog>
    </Card>
  )
}

function Tests({ srv, jobs }) {
  const c = useKit(srv, jobs)
  const [k, setK] = useState('')
  const [paths, setPaths] = useState('')
  const sum = pytestSummary(c.job?.lines)
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('kd.tests')}</span>
      <div className="dk-fields">
        <div className="cu-field"><label className="cu-field-label" htmlFor="kd-k">{t('kd.filter')} <code className="cu-flag">-k</code></label>
          <input id="kd-k" className="cu-input" value={k} onChange={(e) => setK(e.target.value)} placeholder="catalog and not drift" /></div>
        <div className="cu-field"><label className="cu-field-label" htmlFor="kd-paths">{t('kd.paths')}</label>
          <input id="kd-paths" className="cu-input" value={paths} onChange={(e) => setPaths(e.target.value)} placeholder="tests/test_catalog.py" /></div>
      </div>
      <div className="row">
        {c.running ? <Button size="sm" variant="danger" onClick={c.stop}>{t('job.stop')}</Button>
          : <Button size="sm" variant="primary" onClick={() => c.run('pytest', { k: k.trim(), paths: paths.split(/\s+/).filter(Boolean) })}>{t('kd.runTests')}</Button>}
        {sum.map(([w, n]) => <Chip key={w} state={w === 'passed' ? 'ok' : ['skipped', 'deselected'].includes(w) ? undefined : 'bad'}>{n} {w}</Chip>)}
      </div>
      <JobOutput c={c} />
    </Card>
  )
}

// The portal and the app's UI: npm ci / test / build each, the desktop helpers' tests, and whether both committed
// builds (app-build, renderer-build) match their source — `git status --porcelain` prints nothing when they do.
function Builds({ srv, jobs, info }) {
  const c = useKit(srv, jobs)
  const [same, setSame] = useState(null)
  const task = (name) => async () => {
    setSame(null)
    const end = await c.run(name)
    if (name === 'build-diff' && end?.status === 'done') setSame(end.lines.every((l) => !l.trim()))
  }
  const row = (label, ui, modules) => (
    <div className="row">
      <b className="dk-build">{label}</b>
      {info && !modules ? <span className="muted small">{t('kd.noModules')}</span> : null}
      <Button size="sm" variant="ghost" disabled={c.running} onClick={task(`${ui}-ci`)}>npm ci</Button>
      <Button size="sm" disabled={c.running} onClick={task(`${ui}-test`)}>npm test</Button>
      <Button size="sm" variant="ghost" disabled={c.running} onClick={task(`${ui}-build`)}>npm run build</Button>
    </div>
  )
  return (
    <Card className="dk-run">
      <span className="eyebrow">{t('kd.builds')}</span>
      {row(t('kd.portal'), 'portal', info?.has_node_modules)}
      {row(t('kd.app'), 'renderer', info?.renderer_node_modules)}
      <div className="row">
        <Button size="sm" variant="ghost" disabled={c.running} onClick={task('build-diff')}>{t('kd.diff')}</Button>
        <Button size="sm" variant="ghost" disabled={c.running} onClick={task('desktop-test')}>{t('kd.desktop')}</Button>
        {typeof same === 'boolean' ? <Chip state={same ? 'ok' : 'warn'}>{same ? t('kd.same') : t('kd.changed')}</Chip> : null}
      </div>
      <JobOutput c={c} />
    </Card>
  )
}
