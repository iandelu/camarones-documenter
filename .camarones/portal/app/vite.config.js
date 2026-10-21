import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The portal (served by `camaron up` at /, exported by `camaron portal`); the build is committed so users never need
// Node for it. Relative base: the static export also works under a sub-path (GitLab/GitHub Pages).
// Output goes to app-build/, not dist/: the kit installer skips dist folders.
// Excalidraw always adds esm.sh as a last font source and fetches it too: point that fallback at a path of our own,
// so a board never calls a CDN (its fonts are served from public/excalidraw/fonts).
function offlineExcalidraw() {
  return {
    name: 'offline-excalidraw',
    transform(code, id) {
      if (id.includes('@excalidraw/excalidraw') && code.includes('https://esm.sh/')) {
        return code.replaceAll('`https://esm.sh/', '`${location.origin}/excalidraw-offline/')
      }
      return null
    },
  }
}

export default defineConfig({
  base: './',
  plugins: [react(), offlineExcalidraw()],
  resolve: { alias: { '@excalidraw/mermaid-to-excalidraw': fileURLToPath(new URL('./src/stubs/mermaid-to-excalidraw.js', import.meta.url)) } },
  build: { outDir: '../app-build', emptyOutDir: true, manifest: true, sourcemap: false },
  server: { proxy: { '/api': 'http://127.0.0.1:8080' } },
  test: { environment: 'node' },
})
