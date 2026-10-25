import { RUNS } from './api.js'

// Machine work (scans, builds, CI files, AI answers) starts only in the desktop app's window. The browser portal, the
// team's viewer, does not show what it cannot do (until 4.52 it said "open it in the app").
export default function AppOnly({ children }) {
  return RUNS ? children : null
}
