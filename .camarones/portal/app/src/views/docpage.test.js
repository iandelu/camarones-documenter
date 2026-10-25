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

test('the pager follows the reading order; a page outside it has none', () => {
  expect(pager(['a', 'b', 'c'], 'b')).toEqual({ prev: 'a', next: 'c' })
  expect(pager(['a', 'b'], 'a')).toEqual({ prev: null, next: 'b' })
  expect(pager(['a'], 'z')).toBeNull()
})

test('a new page goes under guides/ with a slug of its title', () => {
  expect(newPagePath('How to deploy (prod)')).toBe('guides/how-to-deploy-prod.md')
  expect(newPagePath('')).toBe('guides/.md')
})
