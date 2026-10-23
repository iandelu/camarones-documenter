import { describe, expect, it } from 'vitest'
import { pipelineState, rows } from './ci.js'

describe('CI tab', () => {
  it('names the state of the last pipeline with a word, not only a colour', () => {
    expect(pipelineState({ status: 'success' })).toEqual({ state: 'ok', word: 'passed' })
    expect(pipelineState({ status: 'failure' })).toEqual({ state: 'bad', word: 'failed' })
    expect(pipelineState({ status: 'failed' })).toEqual({ state: 'bad', word: 'failed' })
    expect(pipelineState({ status: 'in_progress' })).toEqual({ state: 'running', word: 'running' })
    expect(pipelineState(null)).toBeNull()
  })

  it('lists what is installed, missing or out of date, in a fixed order', () => {
    const s = { installed: { fresh: { path: '.camarones/ci/docs-fresh.github.yml', outdated: true },
      umbrella: { path: null, outdated: false }, snippet: { path: '.camarones/ci/repo.github.yml', outdated: false } } }
    expect(rows(s)).toEqual([
      { key: 'umbrella', path: null, state: 'missing' },
      { key: 'snippet', path: '.camarones/ci/repo.github.yml', state: 'current' },
      { key: 'fresh', path: '.camarones/ci/docs-fresh.github.yml', state: 'outdated' },
    ])
  })
})
