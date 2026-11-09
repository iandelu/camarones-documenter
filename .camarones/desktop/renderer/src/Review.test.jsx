import { readFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { ReviewView } from './sections/adr/Review.jsx'
import { S, setLang } from './i18n.js'

afterEach(() => setLang('es'))

const noop = () => {}
const review = (props, lang = 'es') => (setLang(lang), renderToStaticMarkup(
  <ReviewView onPart={noop} onPoint={noop} onAttendees={noop} onAccept={noop} onReject={noop} onPresent={noop} onGo={noop} onUi={noop}
    {...props} />))

const adr = (o = {}) => ({ id: '0012', title: 'Sesiones', status: 'proposed', sha: 's1',
  state: { phase: 'review', mode: 'manual', attendees: ['LA'] },
  parts: [{ id: 'context', status: 'approved' }, { id: 'point:p1', status: 'pending' }, { id: 'affected', status: 'pending' }],
  points: [{ id: 'p1', question: '¿Dónde viven las sesiones?', options: [{ id: 'A', name: 'Redis', pros: ['ya en uso'], cons: [] },
    { id: 'B', name: 'Postgres', pros: [], cons: ['escrituras'] }] }],
  sections: { context: 'Hoy en memoria.', decision: 'To be decided in review: see the decision points.' }, affected: ['orders.md'], ...o })

test('a decision point shows its options with keys and its question', () => {
  const out = review({ adr: adr(), current: 'point:p1' })
  for (const s of ['¿Dónde viven las sesiones?', 'A · Redis', 'B · Postgres', '>1<', '+ ya en uso', '− escrituras'])
    expect(out).toContain(s)
})

test('accept says why it is blocked', () => {
  expect(review({ adr: adr(), current: 'context' })).toContain('El punto P1 aún no tiene elección')
})

test('presentation mode drops the chrome and keeps the keys visible', () => {
  const out = review({ adr: adr(), current: 'point:p1', present: true })
  expect(out).toContain('dk-present')
  expect(out).toContain('Esc')
})

test('the review screen carries no joke', () => {
  for (const k of Object.keys(S.es).filter((k) => k.startsWith('adr.review.'))) expect(S.es[k]).not.toMatch(/camar[oó]n|🦐/i)
})

// ---------- the parts ----------
const chosen = (o = {}) => adr({ points: [{ ...adr().points[0], chosen: 'A', rationale: 'ya está en notifications', ...o }],
  parts: [{ id: 'context', status: 'approved' }, { id: 'point:p1', status: 'approved' }, { id: 'affected', status: 'pending' }] })

test('the parts list marks the one in view, the ones done and the ones to see, each with its status', () => {
  const out = review({ adr: adr({ parts: [{ id: 'context', status: 'approved' }, { id: 'drivers', status: 'deferred' },
    { id: 'point:p1', status: 'pending' }, { id: 'affected', status: 'pending' }] }), current: 'point:p1' })
  expect(out).toMatch(/<button type="button" class="dk-rv-part is-pending on" aria-current="step"><span[^>]*>●<\/span><span[^>]*>P1 · ¿Dónde viven las sesiones\?</)
  expect(out).toMatch(/✓<\/span>[^✓●○]*Contexto[^✓●○]*aprobada/)
  expect(out).toMatch(/○<\/span>[^✓●○]*Drivers[^✓●○]*aplazada/)
  expect(out).toMatch(/○<\/span>[^✓●○]*Docu afectada<\/span><span class="sr-only">por revisar/)
  expect(out).toContain('Punto de decisión 1 de 1 · Parte 3 de 4')
})

test('a text part reads with Aprobar, Editar and Aplazar, and no field until it is edited', () => {
  const out = review({ adr: adr(), current: 'context' })
  for (const s of ['Contexto', 'Hoy en memoria.', '>Aprobar<', '>Editar<', '>Aplazar<']) expect(out).toContain(s)
  expect(out).not.toContain('<textarea')
})

test('editing a part opens its Markdown in a field with Guardar', () => {
  const out = review({ adr: adr(), current: 'context', ui: { drafts: { context: { editing: true } } } })
  expect(out).toMatch(/<textarea[^>]*>Hoy en memoria\.<\/textarea>/)
  expect(out).toContain('>Guardar<')
  expect(out).toContain('>Cancelar<')
  const typed = review({ adr: adr(), current: 'context', ui: { drafts: { context: { editing: true, draft: 'Hoy en Redis.' } } } })
  expect(typed).toMatch(/<textarea[^>]*>Hoy en Redis\.<\/textarea>/)
})

// A draft written from text the file no longer has: saving it would replace what someone else wrote (tests/test_adr.py
// test_a_save_made_again_from_the_refused_sha_replaces_the_outside_edit).
const outside = () => adr({ sections: { ...adr().sections, context: 'Hoy en Postgres, según un pull.' } })
const outran = (text = 'Hoy en memoria.') => ({ drafts: { context: { editing: true, draft: 'Hoy en Redis.', base: text } } })
const armed = (out) => !/<button(?:(?!<\/button>).)*aria-disabled="true"(?:(?!<\/button>).)*>Guardar<\/button>/.test(out)

test('a draft the file outran shows what the file says now beside the draft', () => {
  const out = review({ adr: outside(), current: 'context', ui: outran() })
  expect(out).toMatch(/<textarea[^>]*>Hoy en Redis\.<\/textarea>/)
  expect(out).toMatch(/class="dk-rv-pane"(?:(?!<\/section>)[^])*Ahora en el archivo(?:(?!<\/section>)[^])*Hoy en Postgres, según un pull\./)
  expect(review({ adr: outside(), current: 'context', ui: outran() }, 'en')).toContain('Now in the file')
})

test('a draft the file outran cannot be saved until the person says which text stays', () => {
  const out = review({ adr: outside(), current: 'context', ui: outran() })
  expect(armed(out)).toBe(false)
  for (const s of ['Seguir con mi borrador', 'Usar el del archivo']) expect(out).toContain(s)
  const kept = review({ adr: outside(), current: 'context', ui: outran('Hoy en Postgres, según un pull.') })
  expect(armed(kept)).toBe(true)
  expect(kept).not.toContain('Ahora en el archivo')
})

test('a draft of a part nobody else touched saves as ever', () => {
  const out = review({ adr: adr(), current: 'context', ui: outran() })
  expect(armed(out)).toBe(true)
  expect(out).not.toContain('Ahora en el archivo')
})

// The screen's own handlers, fired with no DOM: the first element `hit` picks, with the components above it drawn by hand
// (one with hooks, a dialog, is not on the way to any of these).
function drawn(node, hit) {
  if (Array.isArray(node)) { for (const n of node) { const found = drawn(n, hit); if (found) return found } return null }
  if (!node?.type) return null
  if (hit(node)) return node
  if (typeof node.type !== 'function') return drawn(node.props?.children, hit)
  try { return drawn(node.type(node.props), hit) } catch { return null }
}
const view = (props) => <ReviewView current="context" onPart={noop} onPoint={noop} onAttendees={noop} onAccept={noop} onReject={noop} onPresent={noop} onGo={noop} onUi={noop} {...props} />
const editForm = (props) => drawn(view(props), (n) => n.type === 'form' && n.props.className === 'dk-rv-editf')
const button = (props, word) => drawn(view(props), (n) => n.type === 'button' && [].concat(n.props.children).includes(word))
const submit = (form) => form.props.onSubmit({ preventDefault: noop, currentTarget: { querySelector: () => null } })

test('pressing Guardar on a draft the file outran writes nothing, however often', () => {
  const saved = []
  const form = editForm({ adr: outside(), ui: outran(), onPart: (...a) => saved.push(a) })
  submit(form); submit(form)
  expect(saved).toEqual([])
})

test('keeping the draft moves it onto the file\'s text, and only then Guardar sends it', () => {
  let ui
  button({ adr: outside(), ui: outran(), onUi: (p) => { ui = p } }, 'Seguir con mi borrador').props.onClick()
  expect(ui.drafts.context).toEqual({ editing: true, draft: 'Hoy en Redis.', base: 'Hoy en Postgres, según un pull.' })
  const saved = []
  submit(editForm({ adr: outside(), ui, onPart: (...a) => saved.push(a) }))
  expect(saved).toEqual([['edit', 'Hoy en Redis.']])
})

test('using the file\'s text drops the draft and the editor shows it', () => {
  let ui
  button({ adr: outside(), ui: outran(), onUi: (p) => { ui = p } }, 'Usar el del archivo').props.onClick()
  expect(ui.drafts.context).toMatchObject({ editing: true, draft: undefined, base: undefined })
  expect(review({ adr: outside(), current: 'context', ui })).toMatch(/<textarea[^>]*>Hoy en Postgres, según un pull\.<\/textarea>/)
})

test('the first keystroke of a draft remembers the text it was typed over', () => {
  let ui
  const field = drawn(view({ adr: adr(), ui: { drafts: { context: { editing: true } } }, onUi: (p) => { ui = p } }), (n) => n.type === 'textarea')
  field.props.onChange({ target: { value: 'Hoy en Redis.' } })
  expect(ui.drafts.context).toEqual({ editing: true, draft: 'Hoy en Redis.', base: 'Hoy en memoria.' })
})

test('cancelling forgets the text a draft started from: the next one starts from what the file says then', () => {
  let ui
  button({ adr: outside(), ui: outran('Hoy en Postgres, según un pull.'), onUi: (p) => { ui = p } }, 'Cancelar').props.onClick()
  expect(ui.drafts.context).toMatchObject({ editing: false, draft: undefined, base: undefined })
})

test('a part emptied from outside says so instead of showing nothing', () => {
  const out = review({ adr: adr({ sections: { ...adr().sections, context: '' } }), current: 'context', ui: outran() })
  expect(armed(out)).toBe(false)
  expect(out).toContain('El archivo tiene esta parte vacía')
})

test('an open dialog says the ADR was read again: a refused accept stays open over the notice', () => {
  const out = review({ adr: chosen(), current: 'context', notice: 'El ADR había cambiado', ui: { dialog: 'accept' } })
  expect(out).toMatch(/<dialog(?:(?!<\/dialog>)[^])*El ADR había cambiado(?:(?!<\/dialog>)[^])*<\/dialog>/)
})

test('an empty part says how to fill it', () => {
  expect(review({ adr: adr({ parts: [{ id: 'drivers', status: 'pending' }] }), current: 'drivers' })).toContain('Esta parte está vacía')
})

test('a point offers Elegir y seguir with its why, Otra, Aplazar punto and Quitar', () => {
  const out = review({ adr: adr(), current: 'point:p1' })
  for (const s of ['Punto de decisión 1 de 1', 'Elegir y seguir', 'Por qué, en una línea', '>Otra<', 'Aplazar punto', '>Quitar<'])
    expect(out).toContain(s)
  expect(out).toMatch(/<button[^>]*aria-pressed="false"[^>]*>.*A · Redis/)
})

test('a picked option is pressed, and Otra opens the field for the option typed in the meeting', () => {
  const picked = review({ adr: adr(), current: 'point:p1', ui: { drafts: { 'point:p1': { picked: 'B' } } } })
  expect(picked).toMatch(/aria-pressed="true"[^>]*>(?:(?!<\/button>).)*B · Postgres/)
  const other = review({ adr: adr(), current: 'point:p1', ui: { drafts: { 'point:p1': { picked: 'other', other: 'Hazelcast' } } } })
  expect(other).toContain('La opción que se decide en la reunión')
  expect(other).toContain('value="Hazelcast"')
})

test('a chosen point shows its choice and why', () => {
  const out = review({ adr: chosen(), current: 'point:p1' })
  expect(out).toMatch(/aria-pressed="true"[^>]*>(?:(?!<\/button>).)*A · Redis(?:(?!<\/button>).)*Elegida/)
  expect(out).toContain('value="ya está en notifications"')
  const typed = review({ adr: chosen({ chosen: null, other: 'Hazelcast' }), current: 'point:p1' })
  expect(typed).toContain('value="Hazelcast"')
})

test('a deferred point says how to pick it up again', () => {
  expect(review({ adr: adr({ points: [{ ...adr().points[0], deferred: true }] }), current: 'point:p1' }))
    .toContain('Elige una opción para retomarlo')
})

test('Añadir punto opens a form with the question and two options to name', () => {
  expect(review({ adr: adr(), current: 'context' })).toContain('Añadir punto')
  const out = review({ adr: adr(), current: 'context', ui: { adding: { question: '', options: [{ name: '' }, { name: '' }] } } })
  for (const s of ['La pregunta', 'Opción A', 'Opción B', 'Otra opción', 'Añadir el punto']) expect(out).toContain(s)
  expect(review({ adr: adr(), current: 'context', ui: { adding: { question: '', options: [{}, {}], tried: true } } }))
    .toContain('Escribe la pregunta y al menos dos opciones.')
})

test('the affected docs part lists the pages, read-only', () => {
  const out = review({ adr: adr(), current: 'affected' })
  expect(out).toContain('orders.md')
  expect(out).toContain('>Aprobar<')
  expect(out).not.toContain('>Editar<')
  expect(review({ adr: adr({ affected: [] }), current: 'affected' })).toContain('Este ADR no toca ninguna página de docs y ninguna cita')
})

test('the Decision part is there to write when there is no point to decide', () => {
  const out = review({ adr: adr({ points: [], parts: [{ id: 'context', status: 'approved' }, { id: 'affected', status: 'pending' }] }),
    current: 'decision' })
  expect(out).toContain('Decisión')
  expect(out).toContain('Escribe la sección Decisión o añade un punto de decisión')
})

// ---------- attendees, accept, reject ----------
test('the attendees show as initials with a way to add and remove them', () => {
  const out = review({ adr: adr({ state: { phase: 'review', attendees: ['LA', 'Marta Pérez'] } }), current: 'context' })
  expect(out).toContain('Asistentes')
  expect(out).toMatch(/title="Marta Pérez"[^>]*>MP</)
  expect(out).toContain('aria-label="Quitar a Marta Pérez"')
  expect(out).toContain('Añadir asistente')
  expect(review({ adr: adr({ state: { phase: 'review', attendees: [] } }), current: 'context' })).toContain('Aún nadie')
})

test('accept looks disabled while blocked, still takes the focus and says why', () => {
  const blocked = review({ adr: adr(), current: 'context' })
  expect(blocked).toMatch(/<button[^>]*aria-disabled="true"[^>]*aria-describedby="rv-why"[^>]*>Aceptar ADR<\/button>/)
  expect(blocked).toMatch(/id="rv-why"[^>]*>El punto P1 aún no tiene elección/)
  const ready = review({ adr: chosen(), current: 'context' })
  expect(ready).toMatch(/<button[^>]*class="cu-btn cu-btn--primary"[^>]*>Aceptar ADR<\/button>/)
  expect(ready).not.toContain('aria-disabled="true"')
  expect(ready).toContain('>Rechazar<')
})

test('accepting confirms what is decided and who decides', () => {
  const out = review({ adr: chosen(), current: 'context', ui: { dialog: 'accept' } })
  for (const s of ['<dialog', 'Aceptar el ADR 0012', 'P1 · ¿Dónde viven las sesiones?', 'A · Redis', 'Deciden: LA']) expect(out).toContain(s)
  expect(review({ adr: chosen({ chosen: null, other: 'Hazelcast' }), current: 'context', ui: { dialog: 'accept' } })).toContain('Otra · Hazelcast')
})

test('the accept dialog warns of the sections that still ask a question, and still accepts', () => {
  const todo = chosen()
  todo.sections = { ...todo.sections, consequences: 'TODO(question): what gets easier and what gets harder?',
    context: 'Hoy en memoria. TODO(question): ¿y mañana?' }
  const out = review({ adr: todo, current: 'context', ui: { dialog: 'accept' } })
  expect(out).toMatch(/cu-aviso--warn[^]*Aún quedan preguntas sin responder[^]*Contexto, Consecuencias/)
  expect(out).toContain('Aceptar el ADR 0012')
  expect(out).toMatch(/<button[^>]*data-autofocus[^>]*>Aceptar ADR<\/button>/)
  expect(review({ adr: chosen(), current: 'context', ui: { dialog: 'accept' } })).not.toContain('Aún quedan preguntas')
  expect(review({ adr: todo, current: 'context', ui: { dialog: 'accept' } }, 'en')).toContain('These sections still hold a TODO(question): Context, Consequences')
})

test('rejecting asks why in a dialog', () => {
  const out = review({ adr: adr(), current: 'context', ui: { dialog: 'reject' } })
  for (const s of ['Rechazar el ADR 0012', 'Por qué se rechaza', '<textarea', '>Rechazar el ADR<']) expect(out).toContain(s)
  expect(review({ adr: adr(), current: 'context', ui: { dialog: 'reject', why: ' ', tried: true } })).toContain('Escribe el motivo.')
})

test('removing a point asks first and says what goes', () => {
  const out = review({ adr: adr(), current: 'point:p1', ui: { dialog: 'remove' } })
  expect(out).toContain('¿Quitar el punto P1?')
  expect(out).toContain('Quitar el punto P1')
})

test('a refusal from the server shows as it is', () => {
  const out = review({ adr: adr(), current: 'context', error: 'point P1 has no choice yet' })
  expect(out).toMatch(/role="alert"/)
  expect(out).toContain('point P1 has no choice yet')
})

// ---------- a decided ADR ----------
const accepted = (o = {}) => adr({ status: 'accepted', chip: 'accepted', state: { phase: 'accepted', attendees: ['LA', 'MP'] },
  points: chosen().points, parts: chosen().parts,
  sections: { context: 'Hoy en memoria.', status: 'Accepted (2026-10-21)', decided_by: '- 2026-10-21 · LA, MP' }, ...o })

test('an accepted ADR reads with its status and who decided, and nothing to change', () => {
  const out = review({ adr: accepted(), current: 'point:p1' })
  for (const s of ['Accepted (2026-10-21)', '2026-10-21 · LA, MP', 'A · Redis', 'Elegida', 'Aceptada']) expect(out).toContain(s)
  for (const s of ['>Aprobar<', '>Editar<', 'Elegir y seguir', 'Aceptar ADR', '>Rechazar<', 'Añadir punto', 'Añadir asistente', '<textarea', '<input'])
    expect(out, s).not.toContain(s)
  expect(out).toContain('href="#/decisions/new"')
})

test('a rejected ADR says why; a superseded one, by what', () => {
  expect(review({ adr: accepted({ chip: 'rejected', state: { phase: 'rejected' },
    sections: { status: 'Rejected (2026-10-22): demasiado caro' } }), current: 'context' })).toContain('demasiado caro')
  expect(review({ adr: accepted({ chip: 'superseded', sections: { status: 'Superseded by [0013](0013-sesiones-jwt.md)' } }), current: 'context' }))
    .toMatch(/Superseded by .*0013/)
})

// ---------- keys and presentation ----------
test('the key hints follow the part in view', () => {
  const hint = (out, word) => new RegExp(`</kbd></span> ${word}<`).test(out)
  const point = review({ adr: adr(), current: 'point:p1' })
  expect(point).toContain('<kbd class="cu-kbd">1–2</kbd></span> elegir<')
  for (const s of ['partes', 'editar', 'aplazar', 'aceptar', 'presentar']) expect(hint(point, s), s).toBe(true)
  expect(hint(review({ adr: adr(), current: 'context' }), 'elegir')).toBe(false)
  expect(hint(review({ adr: adr(), current: 'affected' }), 'editar')).toBe(false)
  const done = review({ adr: accepted(), current: 'context' })
  for (const s of ['editar', 'aplazar', 'aceptar']) expect(hint(done, s), s).toBe(false)
  expect(hint(done, 'partes')).toBe(true)
})

test('the key hints follow what is open: the add-point form and the editor', () => {
  const hint = (out, word) => new RegExp(`</kbd></span> ${word}<`).test(out)
  const adding = review({ adr: adr(), current: 'point:p1', ui: { adding: { question: '', options: [{}, {}] } } })
  for (const s of ['partes', 'elegir', 'editar', 'aplazar', 'aceptar']) expect(hint(adding, s), s).toBe(false)
  expect(adding).toContain('<kbd class="cu-kbd">Esc</kbd></span> cerrar<')
  expect(adding).toContain('<kbd class="cu-kbd">P</kbd></span> presentar<')
  const presenting = review({ adr: adr(), current: 'context', present: true, ui: { adding: { question: '', options: [{}, {}] } } })
  expect(presenting).toContain('<kbd class="cu-kbd">Esc</kbd></span> cerrar<')
  expect(presenting).toContain('<kbd class="cu-kbd">P</kbd></span> salir<')
  const editing = review({ adr: adr(), current: 'context', ui: { drafts: { context: { editing: true } } } })
  for (const s of ['aplazar', 'aceptar', 'elegir']) expect(hint(editing, s), s).toBe(false)
  for (const s of ['partes', 'editar']) expect(hint(editing, s), s).toBe(true)
  expect(editing).toContain('<kbd class="cu-kbd">Esc</kbd></span> cerrar<')
  expect(review({ adr: adr(), current: 'context', present: true })).toContain('<kbd class="cu-kbd">Esc</kbd></span> salir<')
})

test('outside the presentation the screen offers it; inside, the way out', () => {
  const out = review({ adr: adr(), current: 'context' })
  expect(out).not.toContain('dk-present')
  expect(out).toContain('Presentar')
  const shown = review({ adr: adr(), current: 'context', present: true })
  expect(shown).toContain('Salir de la presentación')
})

test('the review speaks English too', () => {
  const out = review({ adr: adr(), current: 'point:p1' }, 'en')
  for (const s of ['Choose and go on', 'Defer the point', 'Accept the ADR', 'Attendees', 'Point P1 has no choice yet']) expect(out).toContain(s)
})

// ---------- wiring, style and the design rules ----------
test('a review, accepted or rejected ADR opens on the review screen', () => {
  const src = readFileSync(new URL('./sections/Decisions.jsx', import.meta.url), 'utf-8')
  expect(src).toMatch(/<Review [^>]*adr=\{s\.adr\}/)
  expect(src).not.toMatch(/<ReadView/)
  expect(src).toMatch(/stale\(e\)/)
})

const css = readFileSync(new URL('./app.css', import.meta.url), 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')

const rule = (sel) => css.match(new RegExp(`(?:^|\\})\\s*${sel.replace(/[.()>:]/g, (c) => '\\' + c)}\\s*\\{([^}]*)\\}`))?.[1] ?? ''

test('presenting hides the rail, the sections, what the header holds and the bars, and enlarges the type from the theme', () => {
  const hidden = css.match(/\.dk:has\(\.dk-present\)\s*:is\(([^)]*)\)\s*\{\s*display:\s*none/)?.[1] ?? ''
  for (const sel of ['.dk-rail', '.dk-side', '.dk-top > *', '.dk-jobs', '.dk-status']) expect(hidden, sel).toContain(sel)
  expect(css).toMatch(/\.dk-present\s*\{[^}]*--text-display-md/)
  expect(css.match(/\.dk-present[^{]*\{[^}]*\}/g).join('\n')).not.toMatch(/font-size:\s*[\d.]+(px|rem)/)
})

// The header's row is the window's title bar: main.cjs draws the system's controls over it and it drags the window, so
// it stays, empty, and only what it holds goes.
test('presenting keeps the empty title bar in its row', () => {
  expect(rule('.dk:has(.dk-present)')).toMatch(/"top"\s+3\.5rem/)
  const hidden = css.match(/\.dk:has\(\.dk-present\)\s*:is\(([^)]*)\)\s*\{\s*display:\s*none/)?.[1] ?? ''
  expect(hidden.split(',').map((x) => x.trim())).not.toContain('.dk-top')
})

// .dk-rv-edit asks for 14rem and a bare .cu-input in this selector beat it, leaving 73 px to write a section in.
test('presenting makes the one-line controls tall and leaves a textarea its own height', () => {
  const tall = [...css.matchAll(/([^{}]*\.dk-present[^{}]*)\{[^}]*min-height:\s*3rem[^}]*\}/g)].map((m) => m[1])
  expect(tall.length).toBeGreaterThan(0)
  for (const sel of tall) expect(sel).not.toMatch(/(^|[\s,(])\.cu-input/)
  expect(rule('.dk-rv-edit')).toMatch(/min-height:\s*14rem/)
})

// A decision point at the display sizes is taller than the screen: it scrolls inside its pane, and the row with Aceptar
// and the keys stay in view instead of falling off the bottom edge.
test('presenting scrolls the part, never the accept row', () => {
  const pane = rule('.dk-present .dk-rv-pane')
  expect(pane).toMatch(/overflow-y:\s*auto/)
  expect(pane).toMatch(/flex:\s*1 1 0/)
  expect(pane).not.toMatch(/svh/)
  expect(rule('.dk-present .dk-rv')).toMatch(/display:\s*flex/)
  expect(rule('.dk-present .dk-rv')).toMatch(/min-height:\s*0/)
  expect(rule('.dk-present .dk-rv')).toMatch(/align-items:\s*stretch/)         // .dk-rv's `start` would shrink the pane to its text
  for (const sel of ['.dk-present .dk-rv-nav', '.dk-present .dk-rv-foot', '.dk-present .dk-rv-keys']) expect(rule(sel), sel).toMatch(/flex:\s*none/)
})

test('a part comes in without moving for who asked for less motion', () => {
  const reduced = css.slice(css.lastIndexOf('@media (prefers-reduced-motion: reduce)'))
  expect(reduced).toMatch(/\.dk-rv-pane[^{]*\{[^}]*animation:\s*none/)
})

test('CAMARON.md records the presentation type scale as an approved exception', () => {
  const md = readFileSync(new URL('../../../../.claude/skills/cofundo-design-system/CAMARON.md', import.meta.url), 'utf-8')
  expect(md).toMatch(/fifth approved exception[^.]*presentation/i)
  expect(md).toContain('Review.jsx')
})
