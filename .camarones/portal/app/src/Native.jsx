import { lazy, Suspense } from 'react'
import { MotionConfig } from 'motion/react'
import Ask from './Ask.jsx'

const Pipeline = lazy(() => import('./Pipeline.jsx'))           // React Flow loads only with this view
const Boards = lazy(() => import('./Boards.jsx'))
const Kpis = lazy(() => import('./Kpis.jsx'))
const Ci = lazy(() => import('./Ci.jsx'))
const Libs = lazy(() => import('./Libs.jsx'))
const Data = lazy(() => import('./Data.jsx'))

// The React views of the portal; the docs router (legacy/app.js) shows them through window.CamaronNative.
export default function Native({ view, arg }) {
  const View = { pipeline: Pipeline, boards: Boards, ask: Ask, kpis: Kpis, ci: Ci, libs: Libs, data: Data }[view]
  if (!View) return null
  return (
    <MotionConfig reducedMotion="user">
      <Suspense fallback={<div className="skeleton" aria-busy="true" />}><View key={view + (arg || '')} arg={arg} /></Suspense>
    </MotionConfig>
  )
}
