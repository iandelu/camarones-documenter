import { lazy, Suspense } from 'react'
import { MotionConfig } from 'motion/react'
import Ask from './Ask.jsx'

const Pipeline = lazy(() => import('./Pipeline.jsx'))           // React Flow loads only with this view
const Kpis = lazy(() => import('./Kpis.jsx'))
const Ci = lazy(() => import('./Ci.jsx'))
const Libs = lazy(() => import('./Libs.jsx'))
const Data = lazy(() => import('./Data.jsx'))
const Taller = lazy(() => import('./Taller.jsx'))
const Interview = lazy(() => import('./Interview.jsx'))
const Sync = lazy(() => import('./Sync.jsx'))
const Kanban = lazy(() => import('./Kanban.jsx'))
const Next = lazy(() => import('./Next.jsx'))               // the app's landing view (#/next)
const Onboarding = lazy(() => import('./Onboarding.jsx'))   // the first run, desktop app only (#/start)
const TALLER = ['generate', 'analyze', 'check', 'interviews', 'team', 'machine', 'kitdev']

// The React views of the portal; the docs router (legacy/app.js) shows them through window.CamaronNative.
export default function Native({ view, arg }) {
  if (TALLER.includes(view)) return <Suspense fallback={<div className="skeleton" aria-busy="true" />}><Taller key={view} zone={view} /></Suspense>
  const View = { pipeline: Pipeline, ask: Ask, kpis: Kpis, ci: Ci, libs: Libs, data: Data, interview: Interview, sync: Sync, kanban: Kanban, start: Onboarding, next: Next }[view]
  if (!View) return null
  return (
    <MotionConfig reducedMotion="user">
      <Suspense fallback={<div className="skeleton" aria-busy="true" />}><View key={view === 'kanban' ? view : view + (arg || '')} arg={arg} /></Suspense>
    </MotionConfig>
  )
}
