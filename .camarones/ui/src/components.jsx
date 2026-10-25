import { t } from '../i18n/index.js'

// The kit's base components: markup and classes only (ui.css), so the portal and the desktop app look like one
// product. Rules from CAMARON.md live here once: one filled button per block, a state is a word, no dead-end copy.

const cls = (...names) => names.filter(Boolean).join(' ')

// The wordmark with the project stacked under it, small and dim.
export function Brand({ project, href }) {
  return (
    <a className="cu-brand" href={href}>
      <span className="cu-brand-wm">camarón</span>
      {project && <span className="cu-brand-sub">{project}</span>}
    </a>
  )
}

// primary is the one filled action of a block; secondary is the default; danger is for what cannot be undone.
export function Button({ variant = 'secondary', size, href, className, children, ...rest }) {
  const c = cls('cu-btn', `cu-btn--${variant}`, size && `cu-btn--${size}`, className)
  if (href) return <a className={c} href={href} {...rest}>{children}</a>
  return <button type="button" className={c} {...rest}>{children}</button>
}

// state: ok | warn | info | bad. The colour never stands alone: the chip needs its word.
export function Chip({ state, children }) {
  if (children == null || children === '') throw new Error('Chip needs its word, not only a colour')
  return <span className={cls('cu-chip', state && `cu-chip--${state}`)}>{children}</span>
}

export function Keys({ keys }) {
  return <span className="cu-keys">{keys.map((k) => <kbd key={k} className="cu-kbd">{k}</kbd>)}</span>
}

export function Card({ as: Tag = 'section', className, children, ...rest }) {
  return <Tag className={cls('cu-card', className)} {...rest}>{children}</Tag>
}

// tone: info | warn | error. An error interrupts (alert) and shows the server's message as it is (detail).
export function Aviso({ tone = 'info', title, detail, children }) {
  return (
    <div className={`cu-aviso cu-aviso--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <strong className="cu-aviso-title">{title}</strong>
      {children && <span className="cu-aviso-body">{children}</span>}
      {detail && <code className="cu-aviso-detail">{detail}</code>}
    </div>
  )
}

// An empty screen says what is missing and offers the action that fills it.
export function EmptyState({ title, action, children }) {
  if (!action) throw new Error('EmptyState needs the action that fills it')
  return (
    <div className="cu-empty">
      <strong className="cu-empty-title">{title}</strong>
      {children && <span className="cu-empty-body">{children}</span>}
      {action}
    </div>
  )
}

// Loading has the shape of what comes, never a bare "Loading…".
export function Skeleton({ lines = 3, lang }) {
  return (
    <div className="cu-skel" aria-busy="true" aria-label={t('loading', lang)}>
      {Array.from({ length: lines }, (_, i) => <div key={i} className="cu-skel-line" />)}
    </div>
  )
}

// A human label; the CLI flag stays as a hint for whoever knows the command.
export function Field({ id, label, flag, ...rest }) {
  return (
    <div className="cu-field">
      <label className="cu-field-label" htmlFor={id}>{label}{flag && <> <code className="cu-flag">{flag}</code></>}</label>
      <input className="cu-input" id={id} {...rest} />
    </div>
  )
}

// items: [{ label, href }], the last one is the current page; a step without href is plain text.
export function Breadcrumbs({ items, lang }) {
  return (
    <nav className="cu-crumbs" aria-label={t('crumbs', lang)}>
      <ol>
        {items.map((it, i) => i < items.length - 1
          ? <li key={i}>{it.href ? <a href={it.href}>{it.label}</a> : <span>{it.label}</span>}
              <span className="cu-crumbs-sep" aria-hidden="true">→</span></li>
          : <li key={i}><span aria-current="page">{it.label}</span></li>)}
      </ol>
    </nav>
  )
}
