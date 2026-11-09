import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test, vi } from 'vitest'
import { Setup, Uninstall } from './sections/Machine.jsx'
import { setLang } from './i18n.js'

// These tests have no DOM to click in, so the uninstall card's bench below runs React's hooks by hand while it calls the
// card; every other render goes to the real ones.
const hand = vi.hoisted(() => ({ slots: null, at: 0 }))
vi.mock('react', async (original) => {
  const real = await original()
  const slot = (make) => { const i = hand.at++; return (hand.slots[i] ??= make()) }
  const cell = (v) => { const c = { v, set: (x) => { c.v = typeof x === 'function' ? x(c.v) : x } }; return c }
  return { ...real,
    useState: (v) => { if (!hand.slots) return real.useState(v); const c = slot(() => cell(v)); return [c.v, c.set] },
    useRef: (v) => (hand.slots ? slot(() => ({ current: v })) : real.useRef(v)),
    useEffect: (fn, deps) => (hand.slots ? undefined : real.useEffect(fn, deps)),
  }
})

afterEach(() => setLang('es'))

const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }
const render = (setup) => renderToStaticMarkup(<Setup srv={srv} jobs={null} m={{ setup_steps: 5, setup }} reload={() => {}} />)

test('a machine never set up gets setup as its next step', () => {
  const out = render(null)
  expect(out).toContain('Ejecutar setup')
  expect(out).toContain('cu-btn--primary')
  expect(out).not.toContain('Lista')
})

test('once setup ran here, it says so and offers it again only as a quiet option', () => {
  const out = render({ at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(), kit: '4.73.0' })
  expect(out).toContain('Lista')
  expect(out).toContain('hace 2 h')
  expect(out).toContain('4.73.0')
  expect(out).toContain('Volver a ejecutar')
  expect(out).not.toContain('cu-btn--primary')
  setLang('en')
  const en = render({ at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(), kit: '4.73.0' })
  expect(en).toContain('Ready')
  expect(en).toContain('Prepared 2 h ago with kit 4.73.0.')
  expect(en).toContain('Run it again')
})

test('a machine set up by an older kit, at an unknown time, is ready too', () => {
  const out = render({ at: null, kit: '4.60.0' })
  expect(out).toContain('Lista')
  expect(out).toContain('Preparada con el kit 4.60.0.')
})

// What `uninstall --dry-run` prints for these options (lib/uninstall.py main, tests/test_uninstall.py holds it to that).
const BACKUP = '  • back up cam-docs/ to /tmp/demo-date.zip'
const GLOBAL = '  • ~/.camarones/ (cache, projects.json)'
const DOCS = '  • cam-docs/ — docs, wikis and its git history'
const dryRun = (args) => ['Uninstall demo', '', ...(args.no_backup ? [] : [BACKUP]), DOCS, ...(args.user_level ? [GLOBAL] : []),
  '', 'Not touched:', '  · the repos', '', '(dry run — nothing changed)']

const NO_BACKUP = 'Sin copia de seguridad'
const USER_LEVEL = 'También los ajustes, tokens y cachés de esta máquina (~/.camarones*)'
const PREVIEW = 'Ver qué borraría'
const UNINSTALL = 'Desinstalar'
const STALE = 'Cambiaron las opciones'

const elements = (el, out = []) => {
  if (Array.isArray(el)) el.forEach((x) => elements(x, out))
  else if (el?.props) { out.push(el); elements(el.props.children, out) }
  return out
}
const words = (el) => (typeof el === 'string' ? el : Array.isArray(el) ? el.map(words).join('') : el?.props ? words(el.props.children) : '')
const settle = () => new Promise((resolve) => setImmediate(resolve))

// The real card and its real useCmd on a fake server that answers the way the real one does and never runs anything.
function bench() {
  const slots = []
  const posted = []
  const waiting = []
  const srv = {
    post: async (path, body) => { posted.push({ path, ...body }); return { id: posted.length } },
    get: () => new Promise((resolve) => waiting.push(resolve)),
  }
  const app = { hub: () => {} }
  const render = () => {
    hand.slots = slots
    hand.at = 0
    try { return Uninstall({ srv, jobs: null, app }) } finally { hand.slots = null }
  }
  const parts = () => {
    const card = render()
    const dialog = elements(card).find((e) => e.type === 'dialog')
    dialog.props.ref.current = { showModal() {}, close() {} }
    return { html: renderToStaticMarkup(card), outside: elements(card).filter((e) => !elements(dialog).includes(e)), dialog }
  }
  const button = (inside, label) => inside.find((e) => e.props.onClick && words(e) === label)
  return {
    posted,
    html: () => parts().html,
    offered: () => !!button(parts().outside, UNINSTALL),
    tick: (label) => {
      const box = parts().outside.find((e) => e.type === 'label' && words(e) === label)
      box.props.children[0].props.onChange({ target: { checked: true } })
    },
    preview: async () => { button(parts().outside, PREVIEW).props.onClick(); await settle() },
    finish: async () => {
      const log = dryRun(posted.at(-1).args)
      waiting.shift()({ status: 'done', rc: 0, result: null, stopped: false, lines: log.length, log })
      await settle()
    },
    confirm: async () => {
      const { outside, dialog } = parts()
      button(outside, UNINSTALL).props.onClick()
      const shown = { text: words(elements(dialog).find((e) => e.type === 'p')), list: words(elements(dialog).find((e) => e.type === 'pre')) }
      button(elements(dialog), UNINSTALL).props.onClick()
      await settle()
      return shown
    },
  }
}

test.each([NO_BACKUP, USER_LEVEL])('ticking "%s" after a preview takes Desinstalar and the old list away until a new preview', async (option) => {
  const b = bench()
  await b.preview()
  await b.finish()
  expect(b.offered()).toBe(true)
  expect(b.html()).toContain(BACKUP.trim())

  b.tick(option)
  expect(b.offered()).toBe(false)
  expect(b.html()).not.toContain(BACKUP.trim())
  expect(b.html()).toContain(STALE)

  await b.preview()
  await b.finish()
  expect(b.offered()).toBe(true)
  expect(b.html()).not.toContain(STALE)
})

test.each([NO_BACKUP, USER_LEVEL])('a preview still running when "%s" is ticked does not count once it ends', async (option) => {
  const b = bench()
  await b.preview()
  b.tick(option)
  expect(b.html()).not.toContain(STALE)         // its button is still disabled: nothing to do yet
  await b.finish()
  expect(b.offered()).toBe(false)
  expect(b.html()).not.toContain(BACKUP.trim())
  expect(b.html()).toContain(STALE)

  await b.preview()
  await b.finish()
  expect(b.offered()).toBe(true)
})

test.each([
  { ticks: [], dry: { dry_run: true }, real: {}, list: [BACKUP, DOCS], says: 'copia .zip' },
  { ticks: [NO_BACKUP], dry: { no_backup: true, dry_run: true }, real: { no_backup: true }, list: [DOCS], says: 'sin copia' },
  { ticks: [USER_LEVEL], dry: { user_level: true, dry_run: true }, real: { user_level: true }, list: [BACKUP, DOCS, GLOBAL], says: 'copia .zip' },
  { ticks: [NO_BACKUP, USER_LEVEL], dry: { user_level: true, no_backup: true, dry_run: true }, real: { user_level: true, no_backup: true }, list: [DOCS, GLOBAL], says: 'sin copia' },
])('the dialog lists what runs with these options: $ticks', async ({ ticks, dry, real, list, says }) => {
  const b = bench()
  ticks.forEach((option) => b.tick(option))
  await b.preview()
  await b.finish()
  const shown = await b.confirm()
  expect(shown.list).toBe(list.join('\n'))
  expect(shown.text).toContain(says)
  expect(b.posted).toEqual([
    { path: 'app/cmd', cmd: 'uninstall', args: dry, confirmed: false, quiet: false },
    { path: 'app/cmd', cmd: 'uninstall', args: real, confirmed: true, quiet: false },
  ])
})
