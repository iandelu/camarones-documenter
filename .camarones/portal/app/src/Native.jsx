import { lazy, Suspense } from 'react'
import { MotionConfig } from 'motion/react'
import Ask from './Ask.jsx'

const Pipeline = lazy(() => import('./Pipeline.jsx'))           // React Flow loads only with this view
const Boards = lazy(() => import('./Boards.jsx'))
const Kpis = lazy(() => import('./Kpis.jsx'))

// The React views of the portal; the docs router (legacy/app.js) shows them through window.CamaronNative.
export default function Native({ view, arg }) {
  const View = { pipeline: Pipeline, boards: Boards, ask: Ask, kpis: Kpis }[view]
  if (!View) return null
  return (
    <MotionConfig reducedMotion="user">
      <Suspense fallback={<p className="muted">…</p>}><View key={view + (arg || '')} arg={arg} /></Suspense>
    </MotionConfig>
  )
}
