// Excalidraw's "Mermaid to Excalidraw" dialog pulls a second copy of Mermaid (~5 MB with its parsers) into the build.
// The portal's boards start from C4 views instead (lib/boards.py sketch), so the dialog says it is not available.
export async function parseMermaidToExcalidraw() {
  throw new Error('Mermaid import is not available in the Camarón portal: start a board from a C4 view instead.')
}
