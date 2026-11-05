import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import { Setup } from './sections/Machine.jsx'
import { setLang } from './i18n.js'

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
