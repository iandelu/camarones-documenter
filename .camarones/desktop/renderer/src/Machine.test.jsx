import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { Setup } from './sections/Machine.jsx'

const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }
const render = (setup) => renderToStaticMarkup(<Setup srv={srv} jobs={null} m={{ setup_steps: 5, setup }} reload={() => {}} />)

test('a machine never set up gets setup as its next step', () => {
  const out = render(null)
  expect(out).toContain('Ejecutar setup')
  expect(out).toContain('cu-btn--primary')
  expect(out).not.toContain('Lista')
})

test('once setup ran here, it says so and offers it again only as a quiet option', () => {
  const out = render({ at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(), kit: '4.68.0' })
  expect(out).toContain('Lista')
  expect(out).toContain('hace 2 h')
  expect(out).toContain('4.68.0')
  expect(out).toContain('Volver a ejecutar')
  expect(out).not.toContain('cu-btn--primary')
})

test('a machine set up by an older kit, at an unknown time, is ready too', () => {
  const out = render({ at: null, kit: '4.60.0' })
  expect(out).toContain('Lista')
  expect(out).toContain('4.60.0')
})
