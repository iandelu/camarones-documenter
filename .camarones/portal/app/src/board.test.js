import { describe, expect, it } from 'vitest'
import { apply, changedRun, columns, initial, layout, pipelinePath } from './board.js'

const pipeline = {
  run: { run: 'r-1', finished: false },
  units: [
    { id: 'setup', type: 'setup', phase: 0, status: 'done', deps: [] },
    { id: 'discovery:api', type: 'discovery', phase: 1, status: 'todo', deps: ['setup'] },
    { id: 'discovery:web', type: 'discovery', phase: 1, status: 'todo', deps: ['setup'] },
  ],
}

describe('board', () => {
  it('folds a run into the units: start, log, usage, finish, merge', () => {
    let s = initial(pipeline)
    for (const ev of [
      { type: 'unit.started', unit: 'discovery:api', runner: 'claude', isolation: 'worktree' },
      { type: 'tool.call', unit: 'discovery:api', name: 'Read', arg: 'pom.xml' },
      { type: 'usage', unit: 'discovery:api', in: 10, out: 5, cache_read: 900, cache_write: 100, cost_usd: 0.2 },
      { type: 'unit.finished', unit: 'discovery:api', outcome: 'ok', status: 'done', seconds: 61 },
      { type: 'merge.ok', unit: 'discovery:api' },
    ]) s = apply(s, ev)
    const u = s.units['discovery:api']
    expect(u.status).toBe('done')
    expect(u.live).toMatchObject({ runner: 'claude', outcome: 'ok', seconds: 61, merge: 'merged', tokens_in: 10,
      tokens_cache: 1000, tokens_out: 5, cost_usd: 0.2, log: ['· Read pom.xml'] })
  })
  it('puts running units in their own column and ignores events of unknown units', () => {
    let s = apply(initial(pipeline), { type: 'unit.started', unit: 'discovery:web', runner: 'codex' })
    s = apply(s, { type: 'unit.started', unit: 'ghost' })
    const c = columns(s.units)
    expect(c.running.map((u) => u.id)).toEqual(['discovery:web'])
    expect(c.done.map((u) => u.id)).toEqual(['setup'])
    expect(c.todo.map((u) => u.id)).toEqual(['discovery:api'])
  })
  it('marks the run finished', () => {
    expect(apply(initial(pipeline), { type: 'run.finished' }).finished).toBe(true)
  })
  it('lays units out by phase and draws only known dependencies', () => {
    const units = initial({ units: [...pipeline.units, { id: 'x', phase: 1, status: 'todo', deps: ['missing'] }] }).units
    const { nodes, edges } = layout(units)
    expect(nodes.find((n) => n.id === 'setup').position).toEqual({ x: 0, y: 0 })
    expect(nodes.find((n) => n.id === 'discovery:web').position).toEqual({ x: 260, y: 76 })
    expect(edges.map((e) => e.id)).toEqual(['setup->discovery:api', 'setup->discovery:web'])
  })
  it('keeps log lines from the run detail and caps the live log', () => {
    let s = initial(pipeline, { units: [{ unit: 'discovery:api', runner: 'claude', seconds: 3, merge: 'merged' }] })
    expect(s.units['discovery:api'].live).toMatchObject({ runner: 'claude', seconds: 3, merge: 'merged', log: [] })
    for (let i = 0; i < 250; i++) s = apply(s, { type: 'log', unit: 'discovery:api', text: `${i}` })
    expect(s.units['discovery:api'].live.log).toHaveLength(200)
  })
  it('notices a new run, or the end of the one shown', () => {
    expect(changedRun(null, { run: 'r-2', finished: false })).toBe(true)
    expect(changedRun({ run: 'r-1', finished: true }, { run: 'r-2', finished: false })).toBe(true)
    expect(changedRun({ run: 'r-2', finished: false }, { run: 'r-2', finished: true })).toBe(true)
    expect(changedRun({ run: 'r-2', finished: true }, { run: 'r-2', finished: true })).toBe(false)
    expect(changedRun({ run: 'r-2', finished: true }, null)).toBe(false)
  })
  it('puts units a run never finished back where they were when the run ends', () => {
    let s = apply(initial(pipeline), { type: 'unit.started', unit: 'discovery:web', runner: 'claude' })
    s = apply(s, { type: 'run.finished', interrupted: true })
    expect(s.units['discovery:web'].status).toBe('todo')
    expect(s.units['discovery:web'].live.outcome).toBe('interrupted')
  })
  it('asks for the units in the language the page speaks (their titles come in it)', () => {
    expect(pipelinePath('es')).toBe('pipeline?lang=es')
    expect(pipelinePath('en')).toBe('pipeline?lang=en')
  })
})
