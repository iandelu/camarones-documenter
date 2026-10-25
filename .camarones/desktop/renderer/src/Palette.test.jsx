import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import Palette from './Palette.jsx'

const groups = [
  { id: 'sections', label: 'Secciones', items: [{ id: 'go:summary', label: 'Resumen', keys: ['g', 's'], href: '#/summary' },
    { id: 'go:plan', label: 'Plan', keys: ['g', 'p'], href: '#/plan' }] },
  { id: 'commands', label: 'Comandos', items: [{ id: 'cmd:radar', label: 'Radar', sub: 'camaron radar', href: '#/quality/radar' }] },
]

// WCAG 4.1.2: the field is a combobox that owns a listbox; the active option is named by aria-activedescendant, so the
// focus stays in the field while the arrows move.
test('the palette is a combobox over a listbox of grouped options', () => {
  const out = renderToStaticMarkup(<Palette open groups={groups} onClose={() => {}} onPick={() => {}} />)
  expect(out).toMatch(/<input[^>]*role="combobox"[^>]*aria-expanded="true"[^>]*aria-controls="dk-pal-list"[^>]*aria-activedescendant="dk-pal-opt-0"/)
  expect(out).toContain('<div id="dk-pal-list" role="listbox"')
  expect(out).toContain('<div role="group" aria-label="Secciones">')
  expect(out).toMatch(/<div id="dk-pal-opt-0" role="option" aria-selected="true" class="dk-pal-item on">/)
  expect(out).toMatch(/<div id="dk-pal-opt-1" role="option" aria-selected="false" class="dk-pal-item">/)
  expect(out).toContain('<kbd class="cu-kbd">g</kbd><kbd class="cu-kbd">p</kbd>')
  expect(out).not.toContain('Radar')                     // commands wait for a query
})

test('closed, it is an empty dialog', () => {
  expect(renderToStaticMarkup(<Palette open={false} groups={groups} onClose={() => {}} onPick={() => {}} />))
    .toBe('<dialog class="dk-pal"></dialog>')
})
