import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import Start, { Steps } from './sections/Start.jsx'

const srv = { get: () => new Promise(() => {}), post: () => new Promise(() => {}) }

// Sketch C: one row of steps, the current one marked, the finished ones ticked, the rest numbered.
test('the step row marks where the first run stands', () => {
  const out = renderToStaticMarkup(<Steps steps={['repos', 'tools', 'setup', 'intro']} at={2} done={false} />)
  expect(out).toContain('<li class="done">✔ Repos</li>')
  expect(out).toContain('<li class="done">✔ Herramientas</li>')
  expect(out).toContain('<li class="current" aria-current="step">3. Instalar</li>')
  expect(out).toContain('<li class="future">4. Listo</li>')
  const all = renderToStaticMarkup(<Steps steps={['tools', 'setup', 'intro']} at={2} done />)
  expect(all.match(/class="done"/g)).toHaveLength(3)
})

test('the wizard waits for its state with a skeleton', () => {
  const out = renderToStaticMarkup(<Start srv={srv} jobs={null} app={{}} />)
  expect(out).toContain('aria-busy="true"')
})
