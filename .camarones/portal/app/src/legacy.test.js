import { readFileSync, readdirSync } from 'node:fs'
import { expect, test } from 'vitest'

// The docs views are plain scripts the bundler never parses: a typo there blanks the whole portal (no build error), so
// every one of them must at least parse.
const dir = new URL('../public/legacy/', import.meta.url)
test.each(readdirSync(dir).filter((f) => f.endsWith('.js')))('legacy/%s parses', (file) => {
  expect(() => new Function(readFileSync(new URL(file, dir), 'utf-8'))).not.toThrow()
})
