import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@camaron/ui/ui.css'
import App from './App.jsx'
import { machineLang, setLang } from './i18n.js'
import { applyTheme } from './theme.js'
import './app.css'

// The theme first (the portal's pick or the system's; the window controls follow it), then the app's language: the one
// picked on this machine (~/.camarones.json, through the window's bridge), else Spanish.
applyTheme()
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => applyTheme())
machineLang(window).then(setLang).then(() => createRoot(document.getElementById('app')).render(<StrictMode><App /></StrictMode>))
