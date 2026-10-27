import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { GuideView, markerAction } from './sections/Guide.jsx'
import Machine from './sections/Machine.jsx'
import { parse } from './guide.js'
import { setLang } from './i18n.js'

afterEach(() => setLang('es'))

const SECTIONS = ['summary', 'plan', 'quality', 'machine', 'guide']
const COMMANDS = [{ name: 'check', zone: 'check', verdict: 'app' }, { name: 'setup', zone: 'machine', verdict: 'app' }]
const APP = [
  '## Plan',
  'Run the **ready** units. Press <kbd>Ctrl</kbd> <kbd>K</kbd>; <b>not bold</b>. See [the portal](portal.md#review).',
  '<!-- go:plan -->',
  '<!-- cmd:check -->',
  '<!-- go:kitdev -->',
  '<!-- tour:plan -->',
  '<!-- portal:#/review -->',
  '### Keys',
  '```sh',
  'camaron run',
  '```',
].join('\n')
const GUIDES = [{ name: 'app', title: 'La app', description: 'Cada sección.', blocks: parse(APP) },
  { name: 'portal', title: 'El portal', description: 'Cada vista.', blocks: parse('## Review\n\nThe queue.') }]

const render = (props = {}) => renderToStaticMarkup(<GuideView guides={GUIDES} at={{ name: 'app', anchor: '' }}
  sections={SECTIONS} commands={COMMANDS} tours={[]} {...props} />)

test('the guide shows a tab per guide, its chapters and its text, the current tab marked', () => {
  const out = render()
  expect(out).toMatch(/role="tab"[^>]*aria-selected="true"[^>]*>La app</)
  expect(out).toMatch(/role="tab"[^>]*aria-selected="false"[^>]*>El portal</)
  expect(out).toContain('href="#/guide/app/plan"')
  expect(out).toContain('id="g-plan"')
  expect(out).toContain('Cada sección.')
  expect(out).toContain('<strong>ready</strong>')
  expect(out).toContain('<kbd>Ctrl</kbd>')
  expect(out).toContain('&lt;b&gt;not bold&lt;/b&gt;')
  expect(out).toContain('href="#/guide/portal/review"')
  expect(out).toContain('camaron run')
})

test('markers become buttons only for what this window has', () => {
  const out = render()
  expect(out).toContain('Ir a Plan')
  expect(out).toContain('Abrir camaron check')
  expect(out).toContain('Abrir en el portal')
  expect(out).not.toContain('Ir a Kit dev')               // not in this window's sections
  expect(out).not.toContain('Enséñamelo')                 // no such tour yet
  expect(render({ tours: ['plan'] })).toContain('Enséñamelo')
})

test('markerAction: where each marker goes, null when it cannot go there', () => {
  const ctx = { sections: SECTIONS, commands: COMMANDS, tours: ['plan'] }
  expect(markerAction({ kind: 'go', target: 'plan' }, ctx)).toEqual({ label: 'Ir a Plan', href: '#/plan' })
  expect(markerAction({ kind: 'cmd', target: 'check' }, ctx)).toEqual({ label: 'Abrir camaron check', href: '#/quality/check' })
  expect(markerAction({ kind: 'cmd', target: 'setup' }, ctx)).toEqual({ label: 'Abrir camaron setup', href: '#/machine' })
  expect(markerAction({ kind: 'cmd', target: 'nope' }, ctx)).toBeNull()
  expect(markerAction({ kind: 'cmd', target: 'check' }, { ...ctx, commands: [] })).toBeNull()   // catalog not read yet
  expect(markerAction({ kind: 'portal', target: '#/review' }, ctx)).toEqual({ label: 'Abrir en el portal', portal: '#/review' })
  expect(markerAction({ kind: 'portal', target: 'javascript:alert(1)' }, ctx)).toBeNull()
  expect(markerAction({ kind: 'tour', target: 'plan' }, ctx)).toEqual({ label: 'Enséñamelo', tour: 'plan' })
  expect(markerAction({ kind: 'go', target: 'kitdev' }, ctx)).toBeNull()
})

test('the search box is there, in the machine language', () => {
  setLang('en')
  const out = render()
  expect(out).toContain('Search the guides')
  expect(out).toContain('Go to Plan')
})

test('Machine opens with the guide card, before its own read arrives', () => {
  const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }
  const out = renderToStaticMarkup(<Machine srv={srv} jobs={null} app={{}} />)
  expect(out).toContain('Guía y recorrido')
  expect(out).toContain('href="#/guide"')
  expect(out.indexOf('Guía y recorrido')).toBeLessThan(out.indexOf('cu-skel') === -1 ? Infinity : out.indexOf('cu-skel'))
})

test('tabs carry a short name for the guides the kit ships, the title for any other', () => {
  const guides = [{ name: 'internals', title: 'Cómo funciona Camarón', description: '', blocks: [] },
    { name: 'tutorial', title: 'Tutorial — Camarón, el asistente de documentación del proyecto', description: '', blocks: [] },
    { name: 'extra', title: 'Otra guía', description: '', blocks: [] }]
  const out = renderToStaticMarkup(<GuideView guides={guides} at={{ name: 'internals', anchor: '' }} sections={SECTIONS} commands={[]} />)
  expect(out).toMatch(/role="tab"[^>]*>Por dentro</)
  expect(out).toMatch(/role="tab"[^>]*>Comandos</)
  expect(out).toMatch(/role="tab"[^>]*>Otra guía</)
  expect(out).not.toContain('>Tutorial — Camarón')
})
