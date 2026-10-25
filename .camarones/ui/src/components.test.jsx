import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { Aviso, Brand, Breadcrumbs, Button, Card, Chip, EmptyState, Field, Keys, Skeleton, SkipLink } from './index.js'

const html = (node) => renderToStaticMarkup(node)

// Both apps route by the hash: the skip link moves the focus itself instead of setting #main.
test('the skip link points at the content and says so', () => {
  expect(html(<SkipLink target="native">Saltar al contenido</SkipLink>))
    .toBe('<a class="cu-skip" href="#native">Saltar al contenido</a>')
})

test('Brand stacks the wordmark over the project name', () => {
  const out = html(<Brand project="petclinic" href="#/" />)
  expect(out).toMatch(/^<a class="cu-brand" href="#\/">/)
  expect(out).toContain('<span class="cu-brand-wm">camarón</span><span class="cu-brand-sub">petclinic</span>')
  expect(html(<Brand />)).not.toContain('cu-brand-sub')
})

test.each(['primary', 'secondary', 'ghost', 'danger'])('Button %s is a real button with its variant', (variant) => {
  const out = html(<Button variant={variant}>Confirmar</Button>)
  expect(out).toBe(`<button type="button" class="cu-btn cu-btn--${variant}">Confirmar</button>`)
})

test('Button defaults to secondary: only the main action is filled', () => {
  expect(html(<Button>Editar</Button>)).toContain('cu-btn--secondary')
  expect(html(<Button size="sm">Editar</Button>)).toContain('cu-btn cu-btn--secondary cu-btn--sm')
})

test('Button with href is a link', () => {
  expect(html(<Button href="#/review">Abrir</Button>)).toBe('<a class="cu-btn cu-btn--secondary" href="#/review">Abrir</a>')
})

test('Chip shows its state with its word, never colour alone', () => {
  expect(html(<Chip state="ok">Confirmada</Chip>)).toBe('<span class="cu-chip cu-chip--ok">Confirmada</span>')
  expect(() => html(<Chip state="warn" />)).toThrow(/word/)
})

test('Keys renders one kbd per key', () => {
  expect(html(<Keys keys={['Ctrl', 'K']} />)).toBe('<span class="cu-keys"><kbd class="cu-kbd">Ctrl</kbd><kbd class="cu-kbd">K</kbd></span>')
})

test('Card is a section by default', () => {
  expect(html(<Card aria-label="Plan">x</Card>)).toBe('<section class="cu-card" aria-label="Plan">x</section>')
})

test('an error Aviso is an alert and shows the server message as it is', () => {
  const out = html(<Aviso tone="error" title="El puerto está ocupado" detail="OSError: Address already in use">Ciérralo.</Aviso>)
  expect(out).toMatch(/^<div class="cu-aviso cu-aviso--error" role="alert">/)
  expect(out).toContain('<strong class="cu-aviso-title">El puerto está ocupado</strong>')
  expect(out).toContain('<code class="cu-aviso-detail">OSError: Address already in use</code>')
})

// No dead end: the way out (Try again, Fix it) comes last, after the server's message.
test('an Aviso ends with its action', () => {
  const out = html(<Aviso tone="error" title="No he podido leer el plan" detail="HTTP 500" action={<Button size="sm">Reintentar</Button>} />)
  expect(out).toMatch(/<code class="cu-aviso-detail">HTTP 500<\/code><span class="cu-aviso-action"><button type="button" class="cu-btn cu-btn--secondary cu-btn--sm">Reintentar<\/button><\/span><\/div>$/)
})

test('a warning Aviso is a status, not an alert', () => {
  expect(html(<Aviso tone="warn" title="Borrador de IA" />)).toContain('role="status"')
})

test('EmptyState needs a title and the action that fills it', () => {
  const out = html(<EmptyState title="Aún no hay pizarras" action={<Button variant="primary">Nueva</Button>} />)
  expect(out).toContain('<strong class="cu-empty-title">Aún no hay pizarras</strong>')
  expect(out).toContain('cu-btn--primary')
  expect(() => html(<EmptyState title="Vacío" />)).toThrow(/action/)
})

test('Skeleton is busy and has the requested lines', () => {
  const out = html(<Skeleton lines={2} lang="es" />)
  expect(out).toMatch(/^<div class="cu-skel" aria-busy="true" aria-label="Cargando…">/)
  expect(out.match(/cu-skel-line/g)).toHaveLength(2)
})

test('Field binds its label and shows the CLI flag as a hint', () => {
  const out = html(<Field id="runs" label="Rondas" flag="--runs" defaultValue="3" />)
  expect(out).toContain('<label class="cu-field-label" for="runs">Rondas <code class="cu-flag">--runs</code></label>')
  expect(out).toContain('<input class="cu-input" id="runs" value="3"/>')
})

test('Breadcrumbs: a nav, links up to the current page, which is marked', () => {
  const out = html(<Breadcrumbs lang="es" items={[{ label: 'Docs', href: '#/docs' }, { label: 'Visitas' }]} />)
  expect(out).toMatch(/^<nav class="cu-crumbs" aria-label="Ruta"><ol>/)
  expect(out).toContain('<li><a href="#/docs">Docs</a><span class="cu-crumbs-sep" aria-hidden="true">→</span></li>')
  expect(out).toContain('<li><span aria-current="page">Visitas</span></li>')
})

test('Breadcrumbs: a step without an address is text, not a dead link', () => {
  const out = html(<Breadcrumbs items={[{ label: 'Dominio' }, { label: 'Visitas' }]} />)
  expect(out).toContain('<li><span>Dominio</span><span class="cu-crumbs-sep" aria-hidden="true">→</span></li>')
  expect(out).not.toContain('<a')
})
