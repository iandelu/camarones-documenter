import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

// Every section that reads the server says so when it fails, with the server's own message and Try again; none
// swallows the error and leaves a skeleton up for good.
test.each(['App.jsx', 'Hub.jsx', 'sections/Summary.jsx', 'sections/Plan.jsx', 'sections/Interviews.jsx', 'sections/Team.jsx',
  'sections/Machine.jsx', 'sections/KitDev.jsx', 'sections/Commands.jsx', 'sections/Quality.jsx', 'sections/Start.jsx'])('%s fails with a way out', (f) => {
  const src = readFileSync(new URL(`./${f}`, import.meta.url), 'utf-8')
  expect(src).toMatch(/<Failed [^>]*onRetry=/)
  expect(src).not.toMatch(/srv\.get\('(tree|app\/summary|pipeline|interview|app\/machine|app\/kitdev|inventory)'\)\.then\([^)]*\), \(\) => \{\}\)/)
})
