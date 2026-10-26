import { readFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { Found } from './Hub.jsx'
import { card } from './hub.js'

// Sketch B: one card per case, then the name and the way on. Rendered to text (no DOM in these tests).
const found = (over = {}) => ({ case: 'empty', kind: 'greenfield', workspace: '/w/shop', docs_root: '/w/shop/cam-docs',
  name: 'shop', repos: [], siblings: [], warning: '', ...over })
const draw = (f, props = {}) => renderToStaticMarkup(<Found c={card(f)} name={f.name} setName={() => {}} {...props} />)
const primary = (out) => out.match(/cu-btn--primary/g)?.length ?? 0

test('a folder of repos: badge, its repos, where cam-docs goes, the name and Continue', () => {
  const out = draw(found({ case: 'umbrella', repos: [{ name: 'api' }, { name: 'web' }, { name: 'infra' }] }))
  expect(out).toContain('<span class="cu-chip cu-chip--info">Código existente</span>')
  expect(out).toContain('<h2>3 repos con código</h2>')
  expect(out).toContain('<p>api, web y infra. Los analizo y documento lo que hay.</p>')
  expect(out).toContain('<code>/w/shop/cam-docs</code>')
  expect(out).toMatch(/<input class="cu-input" id="h-name"[^>]*value="shop"/)
  expect(out).toContain('Continuar →')
  expect(primary(out)).toBe(1)
})

test('a project keeps its name: nothing to ask, Continue opens it', () => {
  const out = draw(found({ case: 'project' }))
  expect(out).toContain('cu-chip--warn">Ya documentado')
  expect(out).not.toContain('id="h-name"')
  expect(out).toContain('Continuar →')
})

// I1: no Continue; the warning explains it and holds "Initialise git here", the one primary button.
test('code without git offers git init and no Continue', () => {
  const out = draw(found({ case: 'code', warning: 'no-git' }))
  expect(out).toContain('Este código no está en un repositorio git')
  expect(out).toMatch(/<button type="button" class="cu-btn cu-btn--primary"[^>]*>Inicializar git aquí<\/button>/)
  expect(out).toContain('Cambiar carpeta')
  expect(out).not.toContain('Continuar')
  expect(out).not.toContain('id="h-name"')
  expect(primary(out)).toBe(1)
})

// I2: explained, and "Change folder" is the only button left.
test('home or a drive root leaves only Change folder', () => {
  const out = draw(found({ case: 'repo', repos: [{ name: 'dotfiles' }], warning: 'home', docs_root: '/home/me/cam-docs' }))
  expect(out).toContain('Aquí no puedo crear el proyecto')
  expect(out).toMatch(/<button type="button" class="cu-btn cu-btn--primary">Cambiar carpeta<\/button>/)
  expect(out).not.toContain('Continuar')
  expect(out).not.toContain('Inicializar git')
  expect(out.match(/<button/g)).toHaveLength(1)
})

test('a refusal shows the hub\'s sentence and the CLI\'s line', () => {
  const out = draw(found(), { say: { key: 'hub.taken', detail: 'cam-docs is not empty', error: true } })
  expect(out).toContain('role="alert"')
  expect(out).toContain('Esa carpeta ya tiene un cam-docs que no es un proyecto de Camarón.')
  expect(out).toContain('<code class="cu-aviso-detail">cam-docs is not empty</code>')
})

// The join form, read from the source (its state needs clicks): every try goes through joinOnce (hub.js), so a
// rejected hub.join clears the token like any other non-auth outcome, and the fields wait while a request runs.
test('the join form clears the token on any outcome and locks its fields while busy', () => {
  const src = readFileSync(new URL('./Hub.jsx', import.meta.url), 'utf-8')
  expect(src).toContain('await joinOnce(hub, js, u, token)')
  expect(src).not.toMatch(/hub\.join\(/)
  for (const id of ['h-url', 'h-token']) expect(src).toMatch(new RegExp(`<Field id="${id}"[^/]*disabled=\{busy\}`))
})
