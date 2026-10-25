import { Button, Card } from '@camaron/ui'
import { portalUrl, wikiRepos } from '../docs.js'
import { useJob } from '../hooks.js'
import { JobOutput, Page } from '../parts.jsx'
import { t } from '../i18n.js'

// Reading is the portal's, on this same server one folder up: these buttons open it in the system browser (never an
// href the window would follow). The portal has no token, so what it shows but cannot build — the C4 explorer and each
// wiki's graph — is built here.
export default function Docs({ srv, jobs, app, index }) {
  const open = (hash) => app.openExternal?.(portalUrl(location.origin, hash))
  return (
    <Page title={t('nav.docs')}>
      <div className="row">
        <Button variant="primary" onClick={() => open('#/')}>{t('docs.read')}</Button>
        <Button onClick={() => open('#/review')}>{t('docs.review')}</Button>
        <Button variant="ghost" onClick={() => open('#/search')}>{t('docs.search')}</Button>
      </div>
      <BuildCard srv={srv} jobs={jobs} title={t('docs.c4')} hint={t('docs.c4Hint')} body={{ what: 'c4' }} onView={() => open('#/c4')} />
      {wikiRepos(index).map((repo) => (
        <BuildCard key={repo} srv={srv} jobs={jobs} title={t('docs.wiki', { repo })} hint={t('docs.wikiHint')}
          body={{ what: 'wiki-graph', repo }} onView={() => open(`#/wiki/${repo}`)} />
      ))}
    </Page>
  )
}

// A build job of the project server (POST build, token-gated): Build runs it and follows it; View opens its result.
function BuildCard({ srv, jobs, title, hint, body, onView }) {
  const build = useJob(srv, jobs, () => srv.post('build', body))
  return (
    <Card className="dk-run">
      <div className="row"><span className="eyebrow">{title}</span><span className="dk-grow"></span>
        <Button size="sm" disabled={build.running} onClick={() => build.run()}>{t('docs.build')}</Button>
        <Button size="sm" variant="ghost" onClick={onView}>{t('docs.view')}</Button></div>
      <p className="muted small">{hint}</p>
      <JobOutput c={build} />
    </Card>
  )
}
