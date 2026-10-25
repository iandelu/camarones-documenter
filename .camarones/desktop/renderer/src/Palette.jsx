import { useEffect, useRef, useState } from 'react'
import { Keys } from '@camaron/ui'
import { pick } from './palette.js'
import { t } from './i18n.js'

// ⌘K / Ctrl K: go to a section, open another project, leave for the portal, find a command. The field keeps the
// focus; ↑↓ move the active option (aria-activedescendant), Enter picks it, Esc closes and the dialog gives the focus
// back. Picking closes first, so the focus is back in the window before the pick moves it.
export default function Palette({ open, onClose, groups, onPick }) {
  const dialog = useRef(null)
  const [q, setQ] = useState('')
  const [sel, setSel] = useState(0)
  useEffect(() => {
    const d = dialog.current
    if (open && !d.open) { setQ(''); setSel(0); d.showModal() }
    if (!open && d.open) d.close()
  }, [open])
  useEffect(() => {                                        // the active option stays in sight as the arrows move
    if (open) document.getElementById(`dk-pal-opt-${sel}`)?.scrollIntoView({ block: 'nearest' })
  }, [open, sel, q])

  if (!open) return <dialog ref={dialog} className="dk-pal" onClose={onClose} />
  const shown = pick(groups, q)
  const items = shown.flatMap((g) => g.items)
  const active = Math.min(sel, Math.max(items.length - 1, 0))
  const choose = (it) => { dialog.current?.close(); onPick(it) }
  const onKey = (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (items.length) setSel((active + (e.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (items[active]) choose(items[active])
    }
  }
  let n = 0
  return (
    <dialog ref={dialog} className="dk-pal" aria-label={t('pal.label')} onClose={onClose}
      onClick={(e) => { if (e.target === dialog.current) dialog.current.close() }}>
      <input value={q} autoFocus type="text" autoComplete="off" spellCheck="false" placeholder={t('pal.ph')}
        role="combobox" aria-expanded="true" aria-controls="dk-pal-list" aria-label={t('pal.label')}
        aria-activedescendant={items.length ? `dk-pal-opt-${active}` : undefined}
        onChange={(e) => { setQ(e.target.value); setSel(0) }} onKeyDown={onKey} />
      <div id="dk-pal-list" role="listbox" aria-label={t('pal.label')} className="dk-pal-list">
        {shown.map((g) => (
          <div key={g.id} role="group" aria-label={g.label}>
            <div className="eyebrow dk-pal-group" aria-hidden="true">{g.label}</div>
            {g.items.map((it) => {
              const i = n++
              return (
                <div key={it.id} id={`dk-pal-opt-${i}`} role="option" aria-selected={i === active}
                  className={'dk-pal-item' + (i === active ? ' on' : '')} onClick={() => choose(it)} onMouseMove={() => setSel(i)}>
                  <span className="dk-pal-label">{it.label}{it.sub ? <span className="muted small"> · {it.sub}</span> : null}</span>
                  {it.keys ? <Keys keys={it.keys} /> : null}
                </div>
              )
            })}
          </div>
        ))}
        {!items.length && <p className="muted dk-pal-empty">{t('pal.none')}</p>}
      </div>
      <p className="muted small dk-pal-foot">{t('pal.hint')}</p>
    </dialog>
  )
}
