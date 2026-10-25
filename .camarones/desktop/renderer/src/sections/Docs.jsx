import { Button, Card } from '@camaron/ui'
import { buildFailed, docsCards, openPortal, startBuild } from '../docs.js'
import { useJob } from '../hooks.js'
import { errorLine } from '../onboarding.js'
import { JobOutput, Page } from '../parts.jsx'
import { t } from '../i18n.js'

// Reading is the portal's, on this same server one folder up: these buttons open it in the system browser (never an
// href the window would follow). The portal has no token, so what it shows but cannot build — the C4 explorer and each
// wiki's graph — is built here.
export default function Docs({ srv, jobs, app, index }) {
  const open = (hash) => openPortal(app, location.origin, hash)
  return (
    <Page title={t('nav.docs')}>
      <div className="row">
        <Button variant="primary" onClick={() => open('#/')}>{t('docs.read')}</Button>
        <Button onClick={() => open('#/review')}>{t('docs.review')}</Button>
        <Button variant="ghost" onClick={() => open('#/search')}>{t('docs.search')}</Button>
      </div>
      {docsCards(index).map((c) => (
        <Build key={c.id} srv={srv} jobs={jobs} card={c} title={c.repo ? t('docs.wiki', { repo: c.repo }) : t('docs.c4')}
          hint={c.repo ? t('docs.wikiHint') : t('docs.c4Hint')} onView={() => open(c.hash)} />
      ))}
    </Page>
  )
}

// A build job of the project server (POST build, token-gated) followed to its end.
function Build({ srv, jobs, card, ...rest }) {
  const build = useJob(srv, jobs, () => startBuild(srv, card))
  return <BuildCard build={build} onBuild={() => build.run()} {...rest} />
}

// The card itself: Build runs the job (Retry once it failed, with the reason in the person's language), View opens the
// result in the portal. The buttons repeat on every card, so each says whose it is.
export function BuildCard({ title, hint, build, onBuild, onView }) {
  const failed = buildFailed(build)
  const go = failed ? t('retry') : t('docs.build')
  const shown = build.error ? { ...build, error: errorLine({ message: build.error }, t) } : build
  return (
    <Card className="dk-run">
      <div className="row"><span className="eyebrow">{title}</span><span className="dk-grow"></span>
        <Button size="sm" disabled={build.running} aria-label={`${go}: ${title}`} onClick={onBuild}>{go}</Button>
        <Button size="sm" variant="ghost" aria-label={`${t('docs.view')}: ${title}`} onClick={onView}>{t('docs.view')}</Button></div>
      <p className="muted small">{hint}</p>
      <JobOutput c={shown} />
    </Card>
  )
}
