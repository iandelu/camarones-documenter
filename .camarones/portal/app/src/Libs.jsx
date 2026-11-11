import { useEffect, useState } from 'react'
import { getJSON } from './api.js'
import { t } from './i18n.js'
import { LibrariesBoard, Skeleton } from '@camaron/ui'
import Failed from './Failed.jsx'
import { repoFilter } from './libs.js'

// Every repo's direct dependencies (lib/inventory.py) on the shared board the desktop app draws too: one line per
// library with its version and the latest stable one. Read-only: where the app updates, the portal gives the command.
export const LibsView = ({ inv, arg = '' }) => <LibrariesBoard inv={inv} repo={repoFilter(arg, inv.libraries)} />

export default function Libs({ arg = '' }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const load = () => getJSON('inventory').then((x) => { setData(x); setError('') }, (e) => setError(e.message))
  useEffect(() => { load() }, [])
  return (
    <section className="view libs">
      <h1>{t('libsTitle')}</h1>
      {data ? <LibsView inv={data} arg={arg} />
        : error ? <Failed title={t('libsFailed')} detail={error} onRetry={() => { setError(''); load() }} /> : <Skeleton lines={4} />}
    </section>
  )
}
