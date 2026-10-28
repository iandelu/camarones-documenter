import { expect, test } from 'vitest'
import { newPagePath, pageBanners, pager } from './docpage.js'

const d = (over = {}) => ({ exists: true, trust: 'confirmed', fresh: 'fresh', ...over })

test('a confirmed, fresh page in English has no banner', () => {
  expect(pageBanners(d(), {}, '')).toEqual([])
})

test('a translation that is missing or older than the English page says so', () => {
  expect(pageBanners(d({ exists: false }), {}, 'es')).toEqual([{ tone: 'info', key: 'noTranslation' }])
  expect(pageBanners(d(), { i18n: { es: 'outdated' } }, 'es')).toEqual([{ tone: 'warn', key: 'outdatedTranslation' }])
  expect(pageBanners(d(), { i18n: { es: 'current' } }, 'es')).toEqual([])
})

test('trust and freshness banners, the cited files of a stale page included', () => {
  expect(pageBanners(d({ trust: 'needs-reconfirm' }), {}, '')).toEqual([{ tone: 'info', key: 'banner.needs-reconfirm' }])
  expect(pageBanners(d({ fresh: 'stale', freshness: { missing: ['a.java'], changed: ['b.java'] } }), {}, ''))
    .toEqual([{ tone: 'warn', key: 'banner.stale', code: 'a.java, b.java' }])
  expect(pageBanners(d({ trust: 'draft' }), {}, '')).toEqual([{ tone: 'warn', key: 'banner.draft', draft: true }])
  expect(pageBanners(d({ trust: 'draft' }), { space: 'notes' }, '')).toEqual([])     // working notes are drafts by nature
})

test('a page covered by an accepted ADR says so, pending implementation when new', () => {
  const decisions = [{ id: '0012', title: '0012 — Sessions', path: 'decisions/0012-sessions.md', kind: 'new', implementation: 'pending' },
    { id: '0003', title: '0003 — JPA', path: 'decisions/0003-jpa.md', kind: 'retro', implementation: 'n/a' }]
  expect(pageBanners(d({ decisions }), { space: 'docs' }, '').map((b) => b.key)).toEqual(['banner.adrPending', 'banner.adr'])
  expect(pageBanners(d({ decisions }), {}, '')[0]).toEqual({ tone: 'info', key: 'banner.adrPending',
    adr: { id: '0012', title: '0012 — Sessions', path: 'decisions/0012-sessions.md' } })
})

test('a new decision already implemented, or a page with no decisions, carries no pending banner', () => {
  const done = { id: '0012', title: 'T', path: 'decisions/0012-t.md', kind: 'new', implementation: 'done' }
  expect(pageBanners(d({ decisions: [done] }), {}, '').map((b) => b.key)).toEqual(['banner.adr'])
  expect(pageBanners(d({ decisions: [] }), {}, '')).toEqual([])
  expect(pageBanners(d({ decisions: undefined }), {}, '')).toEqual([])
})

test('the decision banners come after the translation, trust and freshness ones', () => {
  const decisions = [{ id: '0012', title: 'T', path: 'decisions/0012-t.md', kind: 'new', implementation: 'pending' }]
  expect(pageBanners(d({ trust: 'draft', decisions }), {}, '').map((b) => b.key)).toEqual(['banner.draft', 'banner.adrPending'])
})

test('the pager follows the reading order; a page outside it has none', () => {
  expect(pager(['a', 'b', 'c'], 'b')).toEqual({ prev: 'a', next: 'c' })
  expect(pager(['a', 'b'], 'a')).toEqual({ prev: null, next: 'b' })
  expect(pager(['a'], 'z')).toBeNull()
})

test('a new page goes under guides/ with a slug of its title', () => {
  expect(newPagePath('How to deploy (prod)')).toBe('guides/how-to-deploy-prod.md')
  expect(newPagePath('')).toBe('guides/.md')
})
