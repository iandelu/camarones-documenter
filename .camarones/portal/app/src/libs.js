// The Libraries tab's helpers live in the shared kit (the desktop app shows the same table).
export { applyFilter, facets, matrix, worst } from '@camaron/ui/libs.js'

// #/libs/<repo> opens the table filtered to that repo; one the inventory does not have leaves the filter empty.
export const repoFilter = (arg, rows) => (arg && (rows || []).some((r) => r.repo === arg) ? arg : '')
