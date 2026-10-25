import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@camaron/ui/ui.css'
import App from './App.jsx'
import { machineLang, setLang } from './i18n.js'
import './app.css'

// The app's language: the one picked on this machine (~/.camarones.json, through the window's bridge), else Spanish.
machineLang(window).then(setLang).then(() => createRoot(document.getElementById('app')).render(<StrictMode><App /></StrictMode>))
