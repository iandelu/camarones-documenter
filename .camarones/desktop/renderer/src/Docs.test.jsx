import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test } from 'vitest'
import Docs from './sections/Docs.jsx'

const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }
const index = { docs: [{ path: 'repos/api/wiki/index.md', space: 'wiki' }, { path: 'repos/ui/wiki/a.md', space: 'wiki' },
  { path: 'index.md', space: 'docs' }] }

afterEach(() => { delete globalThis.location })

// Reading is the portal's, in the system browser: buttons that call app.openExternal, never a link the window follows.
test('Docs opens the portal through the browser and builds the C4 explorer and each wiki graph', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const out = renderToStaticMarkup(<Docs srv={srv} jobs={null} app={{ openExternal: () => {} }} index={index} />)
  expect(out).not.toMatch(/<a [^>]*href=/)
  for (const label of ['Leer la documentación', 'Revisar borradores', 'Buscar o preguntar']) expect(out).toContain(label)
  expect(out).toContain('Construir el explorador C4')
  expect(out).toContain('Grafo del wiki · api')
  expect(out).toContain('Grafo del wiki · ui')
  expect(out.match(/>Ver</g)).toHaveLength(3)          // C4 + one per wiki
  expect(out.match(/>Construir</g)).toHaveLength(3)
})

test('with no wikis there is no graph card', () => {
  globalThis.location = { origin: 'http://127.0.0.1:5000', hash: '#/docs' }
  const out = renderToStaticMarkup(<Docs srv={srv} jobs={null} app={{ openExternal: () => {} }} index={{ docs: [] }} />)
  expect(out).toContain('Construir el explorador C4')
  expect(out).not.toContain('Grafo del wiki')
})
