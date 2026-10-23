import { Excalidraw } from '@excalidraw/excalidraw'
import '@excalidraw/excalidraw/index.css'

// A board opens zoomed to fit everything: a sketch from a C4 view is wider than the screen at 100 %.
export default function BoardCanvas({ scene, dark, onApi }) {
  function ready(api) {
    onApi(api)
    if (api) setTimeout(() => api.scrollToContent(undefined, { fitToViewport: true, viewportZoomFactor: 0.9 }), 0)
  }
  return (
    <Excalidraw initialData={{ elements: scene.elements || [], appState: { ...(scene.appState || {}), theme: dark ? 'dark' : 'light' },
      files: scene.files || {}, scrollToContent: true }} theme={dark ? 'dark' : 'light'} excalidrawAPI={ready} />
  )
}
