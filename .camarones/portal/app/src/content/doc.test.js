import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'
import { flowViewId, slugify } from './doc.js'

// Heading anchors must match lib/docs.py slugify: a comment or a link that names a section by slug finds it.
test('slugify keeps letters, digits, spaces, _ and -, lower case, spaces → -', () => {
  expect(slugify('6. Editar: dónde y cuándo')).toBe('6-editar-dónde-y-cuándo')
  expect(slugify('  The flow (v2) ')).toBe('the-flow-v2')
  expect(slugify('snake_case-and-dash')).toBe('snake_case-and-dash')
})

test('a business flow page and its dynamic C4 view (CONVENTIONS: one view per flow)', () => {
  expect(flowViewId('flows/book-a-visit.md')).toBe('flow_book_a_visit')
  expect(flowViewId('flows/index.md')).toBeNull()
  expect(flowViewId('domain/visits.md')).toBeNull()
})

// 4.1.2: a heading's # is the mouse's way to copy a section link; hidden from screen readers, it must not take the
// keyboard focus either (the heading's own id is the anchor).
test('the heading anchors stay out of the Tab order', () => {
  const src = readFileSync(new URL('./doc.js', import.meta.url), 'utf-8')
  expect(src).toMatch(/<a class="anchor" [^>]*aria-hidden="true" tabindex="-1">#<\/a>/)
})
