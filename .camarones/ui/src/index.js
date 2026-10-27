// The shared kit, imported as @camaron/ui by the portal and the desktop app. Styles: ui.css (the tokens come from
// theme/tokens.css, linked by each app).
export { Aviso, Brand, Breadcrumbs, Button, Card, Chip, EmptyState, Field, Keys, Skeleton, SkipLink } from './components.jsx'
export { HealthBoard } from './health.jsx'
export { PlanCost } from './plancost.jsx'
export { fmtDuration, fmtTokens, money } from './plancost.js'
export { fmtAgo, gateState, gateWord, safeUrl, sonarConnectHash, sonarReason, sourceWord, stateWord } from './health.js'
export { lang as uiLang, t as uiText } from '../i18n/index.js'
