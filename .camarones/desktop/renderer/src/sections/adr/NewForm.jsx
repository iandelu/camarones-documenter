import { Aviso, Button, Field } from '@camaron/ui'
import { t } from '../../i18n.js'
import { Page } from '../../parts.jsx'
import { TouchSearch } from './TouchSearch.jsx'

// Problema (spec §2.2): the title, the kind, the problem, drivers / constraints / options one per line, Toca and the
// accepted ADR it supersedes. The fields are the person's text as typed; `toBody` turns them into POST app/adr/new.

export const EMPTY = { title: '', kind: 'new', problem: '', drivers: '', constraints: '', options: '', touches: [], supersedes: '' }
const lines = (text) => [...new Set(String(text ?? '').split(/\r?\n/).map((l) => l.trim()).filter(Boolean))]

export const check = (f) => (String(f?.title ?? '').trim() ? {} : { title: true })

export function toBody(f) {
  return {
    title: String(f.title ?? '').trim(), kind: f.kind === 'retro' ? 'retro' : 'new', problem: String(f.problem ?? '').trim(),
    drivers: lines(f.drivers), constraints: lines(f.constraints), options_hint: lines(f.options), touches: [...(f.touches || [])],
    ...(f.supersedes ? { supersedes: f.supersedes } : {}),
  }
}

function Area({ id, label, help, ...rest }) {
  return (
    <div className="cu-field">
      <label className="cu-field-label" htmlFor={id}>{label}</label>
      {help ? <span id={`${id}-help`} className="muted small">{help}</span> : null}
      <textarea id={id} className="cu-input dk-adr-area" rows={3} aria-describedby={help ? `${id}-help` : undefined} {...rest} />
    </div>
  )
}

const KINDS = [['new', 'adr.f.kindNew', 'adr.f.kindNewWhat'], ['retro', 'adr.f.kindRetro', 'adr.f.kindRetroWhat']]

// `accepted`: the rows it may supersede; `next`: the number creating it takes; `search`: Toca's (TouchSearch).
export function NewFormView({ fields, errors = {}, onChange, onSubmit, onCancel, prefilled = false, next = '', accepted = [], busy = false,
  error = '', search }) {
  const set = (k) => (e) => onChange({ ...fields, [k]: e.target.value })
  const submit = (e) => { e.preventDefault(); onSubmit() }
  return (
    <Page title={t('adr.new')}>
      <p className="dk-adr-lede">{t('adr.new.lede')}{next ? <span className="muted">{` ${t('adr.new.number', { next })}`}</span> : null}</p>
      {prefilled ? <Aviso tone="info" title={t('adr.new.prefilled')} /> : null}
      <form className="dk-adr-form" onSubmit={submit} noValidate>
        <fieldset disabled={busy}>
          <div className="dk-adr-titlef">
            <Field id="adr-f-title" label={t('adr.f.title')} value={fields.title} onChange={set('title')} required aria-required="true"
              aria-invalid={errors.title || undefined} aria-describedby={errors.title ? 'adr-f-title-err' : undefined} />
            {errors.title ? <p id="adr-f-title-err" className="small dk-adr-err" role="alert">{t('adr.f.needTitle')}</p> : null}
          </div>
          <fieldset className="dk-adr-kinds">
            <legend className="cu-field-label">{t('adr.f.kind')}</legend>
            {KINDS.map(([k, name, what]) => (
              <label key={k} className="dk-adr-kind">
                <input type="radio" name="adr-kind" value={k} checked={fields.kind === k} onChange={set('kind')} />
                <span><b>{t(name)}</b><span className="muted small">{t(what)}</span></span>
              </label>
            ))}
          </fieldset>
          <Area id="adr-f-problem" label={t('adr.f.problem')} help={t('adr.f.problemHelp')} value={fields.problem} onChange={set('problem')}
            rows={4} />
          <div className="dk-adr-lists">
            <Area id="adr-f-drivers" label={t('adr.f.drivers')} help={t('adr.f.perLine')} value={fields.drivers} onChange={set('drivers')} />
            <Area id="adr-f-constraints" label={t('adr.f.constraints')} help={t('adr.f.perLine')} value={fields.constraints}
              onChange={set('constraints')} />
            <Area id="adr-f-options" label={t('adr.f.options')} help={t('adr.f.optionsHelp')} value={fields.options} onChange={set('options')} />
          </div>
          <TouchSearch id="adr-f-touches" label={t('adr.f.touches')} help={t('adr.f.touchesHelp')} touches={fields.touches} search={search}
            onChange={(touches) => onChange({ ...fields, touches })} />
          <div className="cu-field">
            <label className="cu-field-label" htmlFor="adr-f-supersedes">{t('adr.f.supersedes')}</label>
            <select id="adr-f-supersedes" className="cu-input dk-adr-select" value={fields.supersedes} onChange={set('supersedes')}
              disabled={!accepted.length}>
              <option value="">{t('adr.f.noSupersedes')}</option>
              {accepted.map((a) => <option key={a.id} value={a.id}>{`${a.id} · ${a.title}`}</option>)}
            </select>
          </div>
          {error ? <Aviso tone="error" title={t('adr.new.failed')} detail={error} /> : null}
          <div className="row">
            <Button type="submit" variant="primary" aria-busy={busy || undefined}>{t('adr.create')}</Button>
            <Button onClick={onCancel}>{t('cancel')}</Button>
          </div>
        </fieldset>
      </form>
    </Page>
  )
}
