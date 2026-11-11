// The Libraries board and its helpers live in the shared kit (@camaron/ui libs.js, libs.jsx): the desktop app draws the same.
export { applyFilter, facets, matrix, worst } from '@camaron/ui/libs.js'

// #/libs/<repo> opens the board filtered to that repo; one the inventory does not have leaves the filter empty.
export const repoFilter = (arg, rows) => (arg && (rows || []).some((r) => r.repo === arg) ? arg : '')
