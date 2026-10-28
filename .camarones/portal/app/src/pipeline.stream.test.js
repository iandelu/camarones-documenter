import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

// A run stopped from outside never logs run.finished: the server ends its stream and answers the reconnect with 204,
// which closes the EventSource for good. The Pipeline lets go of it then, so its poll sees the run is over.
test('a stream the server closed for good gives the Pipeline back to its poll', () => {
  const src = readFileSync(new URL('./Pipeline.jsx', import.meta.url), 'utf-8')
  expect(src).toMatch(/source\.onerror = \(\) => \{[^}]*readyState === EventSource\.CLOSED[^}]*source = null/)
})
