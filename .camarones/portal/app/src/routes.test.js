import { describe, expect, it } from 'vitest'
import { href, parse } from './routes.js'

describe('routes', () => {
  it('reads the view and its argument from the hash', () => {
    expect(parse('#/pipeline')).toEqual({ view: 'pipeline', arg: null })
    expect(parse('#/pipeline/discovery:api')).toEqual({ view: 'pipeline', arg: 'discovery:api' })
  })
  it('falls back to home for empty or unknown hashes', () => {
    expect(parse('')).toEqual({ view: 'home', arg: null })
    expect(parse('#/nope')).toEqual({ view: 'home', arg: null })
  })
  it('builds hashes back', () => {
    expect(href('home')).toBe('#/')
    expect(href('pipeline', 'flow:checkout')).toBe('#/pipeline/flow:checkout')
  })
})
