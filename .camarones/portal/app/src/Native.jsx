import { lazy, Suspense } from 'react'
import { MotionConfig } from 'motion/react'
import Ask from './Ask.jsx'
import Home from './views/Home.jsx'

const Pipeline = lazy(() => import('./Pipeline.jsx'))           // React Flow loads only with this view
const Kpis = lazy(() => import('./Kpis.jsx'))
const Ci = lazy(() => import('./Ci.jsx'))
const Libs = lazy(() => import('./Libs.jsx'))
const Data = lazy(() => import('./Data.jsx'))
const Taller = lazy(() => import('./Taller.jsx'))
const Interview = lazy(() => import('./Interview.jsx'))
const Sync = lazy(() => import('./Sync.jsx'))
const TALLER = ['generate', 'analyze', 'check', 'interviews', 'team', 'machine', 'kitdev']

// The React views of the portal; the shell (shell/Shell.jsx) shows them when the router says `native`.
export default function Native({ view, arg }) {
  if (TALLER.includes(view)) return <Suspense fallback={<div className="skeleton" aria-busy="true" />}><Taller key={view} zone={view} /></Suspense>
  const View = { home: Home, pipeline: Pipeline, ask: Ask, kpis: Kpis, ci: Ci, libs: Libs, data: Data, interview: Interview, sync: Sync }[view]
  if (!View) return null
  return (
    <MotionConfig reducedMotion="user">
      <Suspense fallback={<div className="skeleton" aria-busy="true" />}><View key={view + (arg || '')} arg={arg} /></Suspense>
    </MotionConfig>
  )
}
