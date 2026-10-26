import { useEffect, useState } from 'react'
import { getJSON } from './api.js'
import { t } from './i18n.js'
import { Aviso, HealthBoard, Skeleton, uiText } from '@camaron/ui'
import Failed from './Failed.jsx'

// Where each row that has a place in the portal opens. A row with no link is hidden: the portal only reads.
const LINKS = { fresh: '#/review', review: '#/review', libs: '#/libs', context: '#/kpis', evals: '#/kpis' }
const repoHref = (r) => `#/health/${encodeURIComponent(r)}`

// How the project is, from the snapshot `camaron health` (or the app) last wrote. Read-only: it never runs a check.
export default function Health() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const load = () => getJSON('health').then((x) => { setData(x); setError('') }, (e) => setError(e.message))
  useEffect(() => { load() }, [])
  if (!data) return <section className="view">{error ? <Failed title={t('healthFailed')} detail={error} onRetry={() => { setError(''); load() }} /> : <Skeleton lines={4} />}</section>
  return (
    <section className="view health">
      <h1>{t('healthTitle')}</h1>
      {data.snapshot ? <HealthBoard snapshot={data.snapshot} links={LINKS} repoHref={repoHref} />
        : <Aviso tone="info" title={uiText('hb.never')} />}
    </section>
  )
}
