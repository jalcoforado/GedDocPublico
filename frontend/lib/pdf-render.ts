/**
 * Abrir e desenhar páginas de PDF no navegador com pdf.js (SI-68).
 *
 * Fica atrás desta interface pequena por dois motivos: o pdf.js só pode ser
 * carregado no navegador (toca em DOM ao importar, então nada de import no
 * topo de arquivo que o SSR avalia), e os testes do vitest trocam este módulo
 * por um falso — o jsdom não desenha PDF.
 *
 * Build `legacy`: a prefeitura tem máquina com navegador antigo, e o build
 * moderno do pdf.js exige recursos recentes (ex.: `Promise.withResolvers`).
 */

export interface PaginaPdf {
  /** Tamanho da página vista (rotação aplicada), em pontos. */
  larguraPt: number;
  alturaPt: number;
  /** Desenha a página no canvas, na escala dada (1 = 1 ponto por px CSS). */
  desenhar(canvas: HTMLCanvasElement, escala: number): Promise<void>;
}

export interface DocumentoPdf {
  numPaginas: number;
  pagina(numero: number): Promise<PaginaPdf>;
  fechar(): void;
}

type PdfJs = typeof import("pdfjs-dist/legacy/build/pdf.mjs");
type TarefaDeDesenho = { cancel(): void; promise: Promise<void> };

let pdfjs: Promise<PdfJs> | null = null;
// O pdf.js recusa dois `render()` no mesmo canvas ao mesmo tempo — acontece ao
// trocar de página ou redimensionar no meio de um desenho. O anterior é
// cancelado antes de começar o próximo.
const desenhoEmCurso = new WeakMap<HTMLCanvasElement, TarefaDeDesenho>();

function carregarPdfJs(): Promise<PdfJs> {
  pdfjs ??= import("pdfjs-dist/legacy/build/pdf.mjs").then((m) => {
    // O webpack do Next emite o worker como arquivo estático e devolve a URL.
    m.GlobalWorkerOptions.workerSrc = new URL(
      "pdfjs-dist/legacy/build/pdf.worker.min.mjs",
      import.meta.url,
    ).toString();
    return m;
  });
  return pdfjs;
}

export async function abrirPdf(url: string): Promise<DocumentoPdf> {
  const lib = await carregarPdfJs();
  // Mesma origem (atrás do nginx): o cookie de sessão vai junto.
  const tarefa = lib.getDocument({ url, withCredentials: true });
  const doc = await tarefa.promise;
  return {
    numPaginas: doc.numPages,
    async pagina(numero) {
      const page = await doc.getPage(numero);
      const base = page.getViewport({ scale: 1 });
      return {
        larguraPt: base.width,
        alturaPt: base.height,
        async desenhar(canvas, escala) {
          const anterior = desenhoEmCurso.get(canvas);
          if (anterior) {
            anterior.cancel();
            await anterior.promise.catch(() => undefined);
          }
          const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
          const viewport = page.getViewport({ scale: escala * dpr });
          canvas.width = Math.floor(viewport.width);
          canvas.height = Math.floor(viewport.height);
          canvas.style.width = `${Math.floor(viewport.width / dpr)}px`;
          canvas.style.height = `${Math.floor(viewport.height / dpr)}px`;
          const tarefa = page.render({ canvas, viewport });
          desenhoEmCurso.set(canvas, tarefa);
          try {
            await tarefa.promise;
          } finally {
            if (desenhoEmCurso.get(canvas) === tarefa) desenhoEmCurso.delete(canvas);
          }
        },
      };
    },
    fechar() {
      void tarefa.destroy();
    },
  };
}
