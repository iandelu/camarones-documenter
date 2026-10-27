import { Aviso, Button, Chip } from '@camaron/ui'
import { stepper } from '../../adr.js'
import { t } from '../../i18n.js'
import { Page } from '../../parts.jsx'
import { Prose } from './Prose.jsx'

// What the screens of one ADR share: its title, the head line (status chip, kind, repos, file), the stepper and its
// sections read as they are. LegacyView is an ADR with no working state (the kit did not write it, or wrote it before
// this section): read-only, with the way into a review session. ReadView holds an ADR in review or decided until the
// review screen takes it.

export const CHIPS = ['running', 'review', 'proposed', 'accepted', 'superseded', 'rejected', 'deprecated', 'unknown']   // lib/adr.py
const TONE = { running: 'info', review: 'warn', accepted: 'ok' }
const SECTIONS = ['context', 'drivers', 'options', 'decision', 'consequences', 'confirmation', 'diagram', 'evidence', 'decided_by']

// The chip the server derived, else the file's status (a hand-made row may carry either), else none known.
export const chipOf = (adr) => [adr?.chip, adr?.status].find((c) => CHIPS.includes(c)) || 'unknown'
export const StatusChip = ({ chip }) => <Chip state={TONE[chip]}>{t(`adr.chip.${chip}`)}</Chip>
export const heading = (adr) => [adr?.id, adr?.title].filter(Boolean).join(' · ')
// A legacy ADR's kind is the server's default, not something anyone said: it reads as legacy instead.
export const kindWord = (adr) => (adr?.legacy ? t('adr.legacy') : ['new', 'retro'].includes(adr?.kind) ? t(`adr.kind.${adr.kind}`) : '')

export function AdrHead({ adr }) {
  const meta = [kindWord(adr), (adr.repos || []).join(', ')].filter(Boolean).join(' · ')
  return (
    <div className="dk-adr-head">
      <StatusChip chip={chipOf(adr)} />
      {meta ? <span className="muted small">{meta}</span> : null}
      {adr.path ? <code className="dk-adr-path">{adr.path}</code> : null}
    </div>
  )
}

const GLYPH = { done: '✓', current: '●', todo: '○' }

// Where the ADR stands (adr.js `stepper`); the steps writing without AI skips are left out. The last step, once
// reached, is an end: accepted reads as done, rejected as crossed out.
export function Stepper({ phase, mode }) {
  const steps = stepper(phase, mode).filter((s) => s.state !== 'skipped')
  return (
    <ol className="dk-adr-steps" aria-label={t('adr.steps')}>
      {steps.map((s, i) => {
        const end = s.state === 'current' && i === steps.length - 1
        const cls = [s.state, end && (s.id === 'rejected' ? 'rejected' : 'end')].filter(Boolean).join(' ')
        return (
          <li key={s.id} className={cls} aria-current={s.state === 'current' ? 'step' : undefined}>
            <span className="dk-adr-glyph" aria-hidden="true">{end ? (s.id === 'rejected' ? '✕' : '✓') : GLYPH[s.state]}</span>
            {t(`adr.step.${s.id}`)}
            {s.state === 'done' ? <span className="sr-only">{` (${t('adr.stepDone')})`}</span> : null}
          </li>
        )
      })}
    </ol>
  )
}

const said = (text) => String(text ?? '').replace(/<!--[\s\S]*?-->/g, '').trim()

export function Sections({ sections }) {
  const shown = SECTIONS.filter((k) => said(sections?.[k]))
  if (!shown.length) return <p className="muted">{t('adr.noSections')}</p>
  return (
    <article className="dk-adr-doc">
      {shown.map((k) => (
        <section key={k} aria-labelledby={`adr-sec-${k}`}>
          <h2 id={`adr-sec-${k}`} className="dk-adr-sec">{t(`adr.sec.${k}`)}</h2>
          <Prose text={sections[k]} />
        </section>
      ))}
    </article>
  )
}

export function LegacyView({ adr, busy = false, error = '', notice = '', onReview }) {
  return (
    <Page title={heading(adr)}>
      <AdrHead adr={adr} />
      {notice ? <Aviso tone="info" title={notice} /> : null}
      <Aviso tone="info" title={t('adr.legacy.title')} action={
        <Button variant="primary" size="sm" disabled={busy} aria-busy={busy || undefined} onClick={onReview}>{t('adr.legacy.review')}</Button>}>
        {t('adr.legacy.body')}
      </Aviso>
      {error ? <Aviso tone="error" title={t('adr.legacy.failed')} detail={error} /> : null}
      <Sections sections={adr.sections} />
    </Page>
  )
}

export function ReadView({ adr, notice = '' }) {
  return (
    <Page title={heading(adr)}>
      <AdrHead adr={adr} />
      <Stepper phase={adr.state?.phase} mode={adr.state?.mode} />
      {notice ? <Aviso tone="info" title={notice} /> : null}
      <Sections sections={adr.sections} />
    </Page>
  )
}
