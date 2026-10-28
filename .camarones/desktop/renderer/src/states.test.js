import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

// Every section that reads the server says so when it fails, with the server's own message and Try again; none
// swallows the error and leaves a skeleton up for good.
test.each(['App.jsx', 'Hub.jsx', 'sections/Summary.jsx', 'sections/Plan.jsx', 'sections/Interviews.jsx', 'sections/Team.jsx',
  'sections/Machine.jsx', 'sections/KitDev.jsx', 'sections/Commands.jsx', 'sections/Quality.jsx', 'sections/Start.jsx', 'sections/Decisions.jsx'])('%s fails with a way out', (f) => {
  const src = readFileSync(new URL(`./${f}`, import.meta.url), 'utf-8')
  expect(src).toMatch(/<Failed [^>]*onRetry=/)
  expect(src).not.toMatch(/srv\.get\('(tree|app\/summary|pipeline|interview|app\/machine|app\/kitdev|inventory)'\)\.then\([^)]*\), \(\) => \{\}\)/)
})

// The first-run wizard's second read (the tools list, for the tools and install steps) fails with a way out too: its
// error is kept for the panel, which offers to read it again.
test('the wizard tools read fails with a way out', () => {
  const src = readFileSync(new URL('./sections/Start.jsx', import.meta.url), 'utf-8')
  expect(src).toMatch(/srv\.get\('app\/onboard\/tools'\)[\s\S]{0,200}\(e\) => setToolsError\(/)
  expect(src).toMatch(/<Tools [^>]*error=\{toolsError\} onRetry=\{loadTools\}/)
  expect(src).toMatch(/<Setup [^>]*error=\{toolsError\}[^>]*reloadTools=\{loadTools\}/)
})
