import { Aviso, Button, Card, Thinking } from '@camaron/ui'
import { t } from '../../i18n.js'
import { Page } from '../../parts.jsx'
import { AdrHead, Stepper, heading } from './Read.jsx'
import { TouchChip } from './TouchSearch.jsx'

// Evidencia (spec §2.3): the problem as it was framed, the pack (lib/adr_pack.py, no AI) as one line and as its
// Markdown, and the way on. S1 has one: Escribir sin IA. Investigar comes with the jury (S2) and is not drawn here.

const PARTS = ['files', 'neighbours', 'pages', 'adrs', 'commits', 'c4', 'libraries', 'questions']     // adr_pack.PARTS
const ALWAYS = ['files', 'pages', 'adrs', 'commits', 'c4']

// The pack's summary in words: the spec's five always (a fresh project reads zeros, never an error), the others only
// when the pack found some. A count the server left out is zero.
export function packLine(summary, tr) {
  return PARTS.flatMap((p) => {
    const n = Number(summary?.[p]) || 0
    return n || ALWAYS.includes(p) ? [tr(`adr.pack.${p}.${n === 1 ? 'one' : 'many'}`, { n })] : []
  })
}

const texts = (v) => (Array.isArray(v) ? v.filter((x) => typeof x === 'string' && x.trim()) : [])

function Framing({ state }) {
  const s = state || {}
  const rows = [[t('adr.f.drivers'), texts(s.drivers)], [t('adr.f.constraints'), texts(s.constraints)], [t('adr.f.options'), texts(s.options_hint)]]
  const touches = texts(s.touches)
  return (
    <dl className="dk-adr-dl">
      <div className="dk-adr-dlrow"><dt className="sr-only">{t('adr.f.problem')}</dt>
        <dd>{String(s.problem ?? '').trim() ? <p className="dk-adr-problem">{s.problem}</p> : <span className="muted">{t('adr.noProblem')}</span>}</dd></div>
      {rows.filter(([, list]) => list.length).map(([label, list]) => (
        <div key={label} className="dk-adr-dlrow"><dt>{label}</dt><dd><ul>{list.map((x) => <li key={x}>{x}</li>)}</ul></dd></div>
      ))}
      {touches.length ? (
        <div className="dk-adr-dlrow"><dt>{t('adr.f.touches')}</dt>
          <dd><ul className="dk-adr-touches">{touches.map((x) => <TouchChip key={x} touch={x} />)}</ul></dd></div>
      ) : null}
      {s.supersedes ? (
        <div className="dk-adr-dlrow"><dt>{t('adr.f.supersedes')}</dt><dd><a href={`#/decisions/${s.supersedes}`}>{`ADR ${s.supersedes}`}</a></dd></div>
      ) : null}
    </dl>
  )
}

// `pack`: undefined while it is read, null when none was gathered, else {summary, markdown}. `packing`: gathering now.
export function EvidenceView({ adr, pack, packing = false, packError = '', busy = false, error = '', notice = '', onPack, onWrite }) {
  return (
    <Page title={heading(adr)}>
      <AdrHead adr={adr} />
      <Stepper phase={adr.state?.phase} mode={adr.state?.mode} />
      {notice ? <Aviso tone="info" title={notice} /> : null}
      <div className="dk-adr-ev">
        <Card className="dk-adr-card" aria-labelledby="adr-frame-h">
          <h2 id="adr-frame-h" className="eyebrow">{t('adr.step.problem')}</h2>
          <Framing state={adr.state} />
        </Card>
        <Card className="dk-adr-card" aria-labelledby="adr-pack-h">
          <h2 id="adr-pack-h" className="eyebrow">{t('adr.step.evidence')}</h2>
          <p className="muted small">{t('adr.pack.what')}</p>
          {packing ? <p className="small" role="status"><Thinking timer>{t('adr.pack.gathering')}</Thinking></p>
            : pack ? (<>
              <ul className="dk-adr-sum">{packLine(pack.summary, t).map((s, i) => <li key={i}>{s}</li>)}</ul>
              <details className="dk-adr-packmd"><summary>{t('adr.pack.show')}</summary><pre className="dk-log">{pack.markdown}</pre></details>
            </>) : pack === null ? <p className="small">{t('adr.pack.none')}</p> : null}
          {packError ? <Aviso tone="error" title={t('adr.pack.failed')} detail={packError} /> : null}
          {!packing && (pack !== undefined || packError) ? (
            <div className="row"><Button size="sm" disabled={busy} onClick={onPack}>{t(pack ? 'adr.pack.again' : 'adr.pack.gather')}</Button></div>
          ) : null}
        </Card>
      </div>
      <Card className="dk-adr-next" aria-labelledby="adr-next-h">
        <h2 id="adr-next-h" className="eyebrow">{t('adr.next')}</h2>
        <p className="small">{t('adr.write.what')}</p>
        {error ? <Aviso tone="error" title={t('adr.write.failed')} detail={error} /> : null}
        <div className="row">
          <Button variant="primary" disabled={busy || packing} aria-busy={busy || undefined} onClick={onWrite}>{t('adr.write')}</Button>
        </div>
      </Card>
    </Page>
  )
}
