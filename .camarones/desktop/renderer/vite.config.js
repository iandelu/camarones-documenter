import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { UI, camaronTheme, uiResolve } from '../../ui/vite.js'

// The desktop app's UI: served by each project's own server at /desktop/ (same origin as its API, the app token as
// the key) and loaded from disk for the hub. The build is committed so users never need Node for it; relative base
// for both. Output goes to renderer-build/, not dist/: the kit installer skips dist folders.
export default defineConfig({
  base: './',
  plugins: [react(), camaronTheme()],
  resolve: uiResolve,
  build: { outDir: '../renderer-build', emptyOutDir: true, sourcemap: false },
  server: { fs: { allow: ['.', UI] } },
  test: { environment: 'node', include: ['src/**/*.test.{js,jsx}'] },
})
