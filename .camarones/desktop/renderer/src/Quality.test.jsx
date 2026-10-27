import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { DriftList } from './sections/Quality.jsx'

const drift = [
  { path: 'chub/CLAUDE.md', state: 'not linked', what: 'workspace link', why: 'yours' },
  { path: '.claude/skills/cam-docs-unit/SKILL.md', state: 'edited', what: 'kit skill' },
  { path: 'chub/.mcp.json', state: 'not linked', what: 'workspace link', why: 'missing' },
]

test('each kit file that is off says what and why, and whether Repair can fix it', () => {
  const out = renderToStaticMarkup(<DriftList items={drift} repaired={false} />)
  expect(out).toContain('chub/CLAUDE.md')
  expect(out).toContain('Es tuyo: el kit nunca lo reemplaza')
  expect(out).toContain('Editado a mano: Reparar vuelve al texto del kit.')
  expect(out).toContain('Falta el enlace a cam-docs: Reparar lo crea.')
})

test('after a repair it says plainly what it could not fix', () => {
  const out = renderToStaticMarkup(<DriftList items={drift.slice(2)} repaired />)
  expect(out).toContain('Reparar no ha podido con 1')
})

test('nothing off: it says all is in place', () => {
  expect(renderToStaticMarkup(<DriftList items={[]} repaired />)).toContain('Todo en su sitio')
})

test('a file of the person\'s that stays is not a failure: all is in place, and it is listed as kept', () => {
  const out = renderToStaticMarkup(<DriftList items={drift.slice(0, 1)} repaired />)
  expect(out).toContain('Todo en su sitio')
  expect(out).not.toContain('no ha podido')
  expect(out).toContain('chub/CLAUDE.md')
  expect(out).toContain('se queda como está')
})
