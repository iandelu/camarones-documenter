import { describe, expect, it } from 'vitest'
import { draftName, nameAfterPick, slug } from './boardName.js'

describe('board names', () => {
  it('slugs like the server accepts them', () => {
    expect(slug('Containers — Pet Clinic (v2)')).toBe('containers-pet-clinic-v2')
    expect(slug('Año ñandú')).toBe('ano-nandu')
  })

  it('a view gives <title>-draft, numbered when taken', () => {
    expect(draftName({ id: 'index', title: 'System context' }, [])).toBe('system-context-draft')
    expect(draftName({ id: 'index', title: 'System context' }, ['system-context-draft'])).toBe('system-context-draft-2')
    expect(draftName({ id: 'index', title: 'System context' }, ['system-context-draft', 'system-context-draft-2']))
      .toBe('system-context-draft-3')
    expect(draftName({ id: 'containers', title: '' }, [])).toBe('containers-draft')
  })

  it('picking a view fills the name unless the user typed one', () => {
    const view = { id: 'index', title: 'System context' }
    expect(nameAfterPick('', '', view, [])).toBe('system-context-draft')
    expect(nameAfterPick('system-context-draft', 'system-context-draft', { id: 'c', title: 'Containers' }, []))
      .toBe('containers-draft')                                    // the previous auto name follows the view
    expect(nameAfterPick('my-board', 'system-context-draft', view, [])).toBe('my-board')
    expect(nameAfterPick('system-context-draft', 'system-context-draft', null, [])).toBe('')   // back to blank
  })
})
