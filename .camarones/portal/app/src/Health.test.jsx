import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { HealthBoard, uiText } from '@camaron/ui'
import { LINKS } from './Health.jsx'

const snapshot = {
  v: 1, at: '2026-10-26T10:00:00Z',
  areas: {
    machine: { state: 'bad', figures: [{ key: 'machine.tools', n: 12 }, { key: 'machine.missing', n: 2 }], next: { key: 'machine.missing', row: 'doctor' } },
    docs: { state: 'ok', figures: [{ key: 'docs.stale', n: 0 }, { key: 'docs.review', n: 0 }], next: null },
    code: { state: 'ok', figures: [{ key: 'code.libraries', n: 3 }, { key: 'code.vulnHigh', n: 0 }], next: null },
  },
  verdict: [{ key: 'machine.missing', n: 2 }], repo_state: {},
  machine: { at: 'x', missing: ['uv', 'gitleaks'], drift: 1, tools: 12 },
  docs: { at: 'x', stale: [], suspect: [], evals: { total: 5, confirmed: 3 }, context: { total: 900, budget: 2000, over: false }, review: 0 },
  inventory: { at: '2026-10-20T00:00:00Z', scanned: true },
  repos: {},
}
const board = (props) => renderToStaticMarkup(<HealthBoard snapshot={snapshot} links={LINKS} {...props} />)

test('the portal has no place for the machine checks: the Machine panel says where they are, not an empty list', () => {
  expect(LINKS.doctor).toBeUndefined()
  expect(LINKS.drift).toBeUndefined()
  const out = board({ initialTab: 'machine' })
  const panel = out.match(/<(\w+)[^>]*role="tabpanel"[^>]*>(.*?)<\/\1>/)[2]
  expect(panel).toContain(uiText('hb.inApp'))
  expect(out).not.toMatch(/<ul[^>]*role="tabpanel"/)
  expect(out).not.toContain('data-row="doctor"')
  expect(uiText('hb.inApp', 'en')).toBe('This is checked in the desktop app')
  expect(uiText('hb.inApp', 'es')).toBe('Esto se revisa en la app de escritorio')
})

test('an area with a row the portal can show keeps its list and not the line', () => {
  const out = board({ initialTab: 'docs' })
  expect(out).toContain('data-row="fresh"')
  expect(out).not.toContain(uiText('hb.inApp'))
})
