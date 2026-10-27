import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { TourBubble } from './Tour.jsx'
import { TourOffer } from './sections/Summary.jsx'
import Machine from './sections/Machine.jsx'
import { entries } from './palette.js'
import { markSeen, tourIds, TOURS } from './tour.js'
import { MACHINE, PROJECT } from './nav.js'
import { setLang, t } from './i18n.js'

afterEach(() => setLang('es'))

const HERE = dirname(fileURLToPath(import.meta.url))
const KIT = join(HERE, '..', '..', '..')
const GUIDES = [join(KIT, 'templates', 'docs', 'guides'), join(KIT, 'templates', 'docs', 'i18n', 'es', 'guides')]
const markers = (kind) => GUIDES.flatMap((d) => readdirSync(d).filter((f) => f.endsWith('.md'))
  .flatMap((f) => [...readFileSync(join(d, f), 'utf8').matchAll(new RegExp(`^<!--\\s*${kind}:(\\S+)\\s*-->`, 'gm'))].map((m) => [f, m[1]])))
const sources = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((e) => e.isDirectory() ? sources(join(dir, e.name))
  : /\.jsx?$/.test(e.name) && !/\.test\./.test(e.name) ? [readFileSync(join(dir, e.name), 'utf8')] : [])

test('the bubble: where you are, the step, and the way on', () => {
  const out = renderToStaticMarkup(<TourBubble title="Plan" body="Las unidades." n={2} m={5} />)
  expect(out).toMatch(/role="dialog"/)
  expect(out).toMatch(/aria-modal="true"/)
  expect(out).toContain('2 de 5')
  expect(out).toContain('Las unidades.')
  expect(out).toContain('>Atrás<')
  expect(out).toContain('>Siguiente<')
  expect(out).toContain('>Cerrar<')
  expect(out).not.toContain(t('tour.missing'))
})

test('the first step has no Back, the last says Done, a missing target says so', () => {
  const first = renderToStaticMarkup(<TourBubble title="a" body="b" n={1} m={3} />)
  expect(first).not.toContain('>Atrás<')
  expect(renderToStaticMarkup(<TourBubble title="a" body="b" n={3} m={3} />)).toContain('>Hecho<')
  expect(renderToStaticMarkup(<TourBubble title="a" body="b" n={2} m={3} missing />)).toContain(t('tour.missing'))
})

test('every Show me in the guides starts a tour that exists, every Go to names a section', () => {
  for (const [f, id] of markers('tour')) expect(tourIds(), `${f}: tour:${id}`).toContain(id)
  for (const [f, s] of markers('go')) expect([...PROJECT, ...MACHINE], `${f}: go:${s}`).toContain(s)
})

test('every step points at something the app marks with data-tour', () => {
  const code = [...sources(HERE), ...sources(join(KIT, 'ui', 'src'))].join('\n')
  const marked = new Set([...code.matchAll(/data-tour="([\w-]+)"/g)].map((m) => m[1]))
  const navMarked = /data-tour=\{`nav-\$\{s\}`\}/.test(code)
  for (const id of tourIds()) for (const s of TOURS[id]) {
    if (s.target.startsWith('nav-')) expect(navMarked && [...PROJECT, ...MACHINE].includes(s.target.slice(4)), s.target).toBe(true)
    else expect(marked, `${id}: ${s.target}`).toContain(s.target)
  }
})

const memory = () => { const box = {}; return { getItem: (k) => box[k] ?? null, setItem: (k, v) => { box[k] = v } } }

test('the Summary offers the tour once', () => {
  const store = memory()
  const out = renderToStaticMarkup(<TourOffer storage={store} />)
  expect(out).toContain('Hacer el recorrido')
  expect(out).toContain('Ahora no')
  markSeen(store)
  expect(renderToStaticMarkup(<TourOffer storage={store} />)).toBe('')
})

test('the palette and Machine both start the tour', () => {
  const groups = entries({ sections: ['summary'], t })
  expect(groups.find((g) => g.id === 'actions').items).toContainEqual({ id: 'tour', label: 'Hacer el recorrido', action: 'tour' })
  const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }
  expect(renderToStaticMarkup(<Machine srv={srv} jobs={null} app={{}} />)).toContain('Hacer el recorrido')
})
