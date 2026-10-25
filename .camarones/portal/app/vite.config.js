import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { UI, camaronTheme, uiResolve } from '../../ui/vite.js'

// The portal (served by `camaron up` at /, exported by `camaron portal`); the build is committed so users never need
// Node for it. Relative base: the static export also works under a sub-path (GitLab/GitHub Pages).
// Output goes to app-build/, not dist/: the kit installer skips dist folders.
export default defineConfig({
  base: './',
  plugins: [react(), camaronTheme()],
  resolve: uiResolve,
  build: { outDir: '../app-build', emptyOutDir: true, manifest: true, sourcemap: false },
  server: { proxy: { '/api': 'http://127.0.0.1:8080' }, fs: { allow: ['.', UI] } },
  test: { environment: 'node', include: ['src/**/*.test.{js,jsx}', '../../ui/**/*.test.{js,jsx}'] },
})
