import { RUNS } from './api.js'
import { t } from './i18n.js'

// Machine work (runs, scans, builds, CI files, AI answers) starts only in the desktop app's window; the browser
// portal, the team's viewer, says where to find it instead of offering a button the server would refuse.
export default function AppOnly({ children, inline = false }) {
  if (RUNS) return children
  return inline ? <span className="aviso small">{t('appOnly')}</span> : <p className="aviso small">{t('appOnly')}</p>
}
