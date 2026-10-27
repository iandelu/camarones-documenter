import { useEffect, useRef, useState } from 'react'
import { Button, Chip } from '@camaron/ui'
import { ago, chip, state } from './jobs.js'
import { useStore } from './hooks.js'
import { t } from './i18n.js'

const now = () => Date.now() / 1000

// The jobs panel under every section: the job that runs (or the last one) in one line; open, the recent ones and the
// output of the one picked, live while it runs. A process the app started can be stopped from here.
export default function JobsPanel({ srv, jobs }) {
  const { running, recent } = useStore(jobs)
  const [open, setOpen] = useState(false)
  const [picked, setPicked] = useState(null)
  const head = running[0] || recent[0]
  const shown = recent.find((j) => j.id === picked) || head
  const stop = async (j) => {
    try { await srv.post(`app/jobs/${j.id}/cancel`, {}) } finally { jobs.refresh() }
  }
  return (
    <section className={'dk-jobs' + (open ? ' open' : '')} aria-label={t('jobs')} data-tour="jobs">
      <div className="dk-jobs-bar">
        <span className="eyebrow">{t('jobs')}</span>
        {head ? <JobLine job={head} /> : <span className="muted small">{t('jobs.none')}</span>}
        {running.length > 1 && <span className="muted small">+{running.length - 1}</span>}
        <span className="dk-grow"></span>
        {recent.length > 0 && (
          <Button size="sm" variant="ghost" aria-expanded={open} onClick={() => setOpen(!open)}>
            {t(open ? 'fold' : 'jobs.history')}</Button>
        )}
      </div>
      {open && shown && (
        <div className="dk-jobs-body">
          <ul className="dk-job-list">
            {recent.map((j) => (
              <li key={j.id} className="row">
                <button type="button" className={'dk-job' + (j.id === shown.id ? ' on' : '')} aria-pressed={j.id === shown.id}
                  onClick={() => setPicked(j.id)}><JobLine job={j} /></button>
                {j.stoppable && <Button size="sm" variant="danger" onClick={() => stop(j)}>{t('job.stop')}</Button>}
              </li>
            ))}
          </ul>
          <JobLog srv={srv} job={shown} />
        </div>
      )}
    </section>
  )
}

function JobLine({ job }) {
  return (
    <>
      <Chip state={chip(job)}>{t('job.' + state(job))}</Chip>
      <span className="dk-job-label">{job.label || job.kind}</span>
      <span className="muted small">{ago(job.started, now(), t)}</span>
    </>
  )
}

// A job's output: what it printed so far, then only the new lines while it runs (jobs/<id>?since=n).
function JobLog({ srv, job }) {
  const [lines, setLines] = useState([])
  const box = useRef(null)
  useEffect(() => {
    let gone = false, timer = null, seen = 0
    setLines([])
    const look = async () => {
      try {
        const j = await srv.get(`jobs/${job.id}?since=${seen}`)
        if (gone) return
        seen = j.lines
        if (j.log.length) setLines((cur) => [...cur, ...j.log])
        if (j.status === 'running') timer = setTimeout(look, 1000)
      } catch { /* the panel's next look says it */ }
    }
    look()
    return () => { gone = true; clearTimeout(timer) }
  }, [job.id, job.status])
  useEffect(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight }, [lines])
  return (
    <pre className="dk-log" ref={box} tabIndex={0} aria-label={job.label || job.kind}>
      {lines.length ? lines.join('\n') : t('job.empty')}
    </pre>
  )
}
