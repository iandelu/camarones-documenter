import { expect, test } from 'vitest'
import { linkTarget, oldWikiPath, rawPath } from './links.js'

const known = new Set(['repos/api/index.md', 'flows/orders.md', 'wikis/api/index.md', 'wikis/api/quickstart.md'])
const has = (p) => known.has(p)

test('a wiki page links a docs page as its file sits on disk: docs/<page> is the docs page', () => {
  expect(linkTarget('docs/flows/orders.md', has)).toBe('flows/orders.md')
  expect(linkTarget('flows/orders.md', has)).toBe('flows/orders.md')
})

test('a wiki page old path (repos/<repo>/<page>) names it where no docs page has that path', () => {
  expect(linkTarget('repos/api/quickstart.md', has)).toBe('wikis/api/quickstart.md')
  expect(linkTarget('repos/api/index.md', has)).toBe('repos/api/index.md')
  expect(linkTarget('wikis/api/index.md', has)).toBe('wikis/api/index.md')
  expect(linkTarget('flows/nope.md', has)).toBe('flows/nope.md')
})

test('old wiki paths and raw files', () => {
  expect(oldWikiPath('repos/api/deep/a.md')).toBe('wikis/api/deep/a.md')
  expect(oldWikiPath('repos/api')).toBeNull()
  expect(oldWikiPath('flows/a.md')).toBeNull()
  expect(rawPath('docs/img/a.png')).toBe('img/a.png')
  expect(rawPath('wikis/api/a.png')).toBe('wikis/api/a.png')
})
