// Strings of the React views, in the reader's portal language (the classic views keep theirs in legacy/core.js).
const S = {
  en: {
    askTitle: 'Ask the docs', askLead: 'The sections that best answer your question, each with where it comes from. No AI: '
      + 'it searches the docs the same way agents do, and leaves out what is out of date.',
    askPh: 'How is a payment retried?', ask: 'Ask', nothing: 'Nothing in the docs answers this.', withheld: 'agents do not get this page yet',
    boardsTitle: 'Boards', boardsLead: 'Whiteboards versioned in cam-docs (docs/boards/). Start one blank or from a C4 view.',
    newBoard: 'New board', name: 'name', blank: 'Blank', fromView: 'From C4 view', open: 'Open', save: 'Save', saved: 'Saved',
    allBoards: '← All boards', noBoards: 'No boards yet.', loading: 'Loading…', readOnly: 'Read-only in the exported portal.',
  },
  es: {
    askTitle: 'Pregunta a la documentación', askLead: 'Las secciones que mejor responden a tu pregunta, con su origen. Sin IA: '
      + 'busca en la documentación igual que los agentes y deja fuera lo desactualizado.',
    askPh: '¿Cómo se reintenta un pago?', ask: 'Preguntar', nothing: 'Nada en la documentación responde a esto.',
    withheld: 'los agentes aún no reciben esta página',
    boardsTitle: 'Pizarras', boardsLead: 'Pizarras versionadas en cam-docs (docs/boards/). Empieza una en blanco o desde una vista C4.',
    newBoard: 'Nueva pizarra', name: 'nombre', blank: 'En blanco', fromView: 'Desde vista C4', open: 'Abrir', save: 'Guardar',
    saved: 'Guardada', allBoards: '← Todas las pizarras', noBoards: 'Aún no hay pizarras.', loading: 'Cargando…',
    readOnly: 'Solo lectura en el portal exportado.',
  },
}

export function t(key) {
  let lang = ''
  try { lang = localStorage.getItem('cam-lang') || '' } catch { /* private mode */ }
  return (S[lang] || S.en)[key] ?? S.en[key] ?? key
}
