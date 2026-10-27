import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, expect, test, vi } from 'vitest'

const { seen } = vi.hoisted(() => ({ seen: [] }))
vi.mock('@xyflow/react', async (original) => ({ ...(await original()), ReactFlow: (props) => { seen.push(props); return null } }))
const { default: Canvas } = await import('./sections/Canvas.jsx')

afterEach(() => { seen.length = 0; vi.unstubAllGlobals() })
const units = [
  { id: 'a', title: 'A', status: 'doing', runner: 'agent', phase: 1, deps: [] },
  { id: 'b', title: 'B', status: 'todo', runner: 'agent', phase: 2, deps: ['a'] },
]
const flow = () => {
  renderToStaticMarkup(<Canvas srv={{ stream: () => new Promise(() => {}) }} units={units} run={null} pilot={null} onOpen={() => {}} />)
  return seen.at(-1)
}
const win = (pick, systemDark) => ({ localStorage: { getItem: () => pick }, matchMedia: () => ({ matches: systemDark }) })

// React Flow forgets a node's size and its handles whenever a node object comes back without `measured` (every tick of
// the clock, every batch of events, every drag move), and then draws no edge until it measures again.
test('every node keeps the size it was laid out at, so a rebuilt node does not lose its handles', () => {
  const { nodes } = flow()
  expect(nodes).toHaveLength(2)
  for (const n of nodes) expect(n.measured).toEqual({ width: n.width, height: n.height })
})

// The app's picked theme (data-theme, from cam-theme) wins over the system's; React Flow must say the same.
test('the canvas follows the theme the app resolved, not the system alone', () => {
  vi.stubGlobal('window', win('light', true))
  expect(flow().colorMode).toBe('light')
  vi.stubGlobal('window', win('dark', false))
  expect(flow().colorMode).toBe('dark')
  vi.stubGlobal('window', win('', true))
  expect(flow().colorMode).toBe('dark')
})
