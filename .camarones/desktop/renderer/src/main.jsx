import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@camaron/ui/ui.css'
import App from './App.jsx'
import { setLang } from './i18n.js'
import './app.css'

// The app's language: the one picked on this machine (~/.camarones.json, through the hub), else Spanish.
const ready = window.camaronHub?.lang ? window.camaronHub.lang().then(setLang, () => setLang('es')) : Promise.resolve(setLang('es'))
ready.then(() => createRoot(document.getElementById('app')).render(<StrictMode><App /></StrictMode>))
