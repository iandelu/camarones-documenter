import { Excalidraw } from '@excalidraw/excalidraw'
import '@excalidraw/excalidraw/index.css'

export default function BoardCanvas({ scene, dark, onApi }) {
  return (
    <Excalidraw initialData={{ elements: scene.elements || [], appState: { ...(scene.appState || {}), theme: dark ? 'dark' : 'light' },
      files: scene.files || {}, scrollToContent: true }} theme={dark ? 'dark' : 'light'} excalidrawAPI={onApi} />
  )
}
