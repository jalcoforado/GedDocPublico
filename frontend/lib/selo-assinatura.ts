/**
 * Geometria do selo da assinatura posicionada (SI-68).
 *
 * A posição vai ao backend como o canto SUPERIOR ESQUERDO do quadrado, em
 * fração (0–1) da página como ela aparece na tela — já girada, origem no canto
 * superior esquerdo. O backend (`services/pdf_selo_assinatura.py`) converte
 * para pontos do PDF.
 *
 * O tamanho do selo em pontos é o MESMO do backend: mude os dois juntos.
 * `backend/tests/test_si68_selo_assinatura.py` reprova se divergirem.
 */

export const SELO_LARGURA_PT = 200;
export const SELO_ALTURA_PT = 62;

/** Margem do selo para a borda na posição inicial (meia polegada). */
const MARGEM_INICIAL_PT = 36;

export interface PosicaoSelo {
  pagina: number;
  x: number;
  y: number;
}

export interface TamanhoPagina {
  /** Largura e altura da página vista, em pontos (viewport do pdf.js, escala 1). */
  larguraPt: number;
  alturaPt: number;
}

/** Fração da página que o quadrado ocupa. */
export function fracaoDoSelo(p: TamanhoPagina): { largura: number; altura: number } {
  return {
    largura: Math.min(SELO_LARGURA_PT / p.larguraPt, 1),
    altura: Math.min(SELO_ALTURA_PT / p.alturaPt, 1),
  };
}

/** Mantém o quadrado inteiro dentro da página (o backend faz o mesmo). */
export function limitarPosicao(x: number, y: number, p: TamanhoPagina): { x: number; y: number } {
  const f = fracaoDoSelo(p);
  const lim = (v: number, max: number) => Math.min(Math.max(v, 0), Math.max(max, 0));
  return { x: lim(x, 1 - f.largura), y: lim(y, 1 - f.altura) };
}

/** Canto inferior direito, acima do rodapé do carimbo: onde costuma ir a
 *  assinatura num ofício. */
export function posicaoInicial(p: TamanhoPagina): { x: number; y: number } {
  const f = fracaoDoSelo(p);
  return limitarPosicao(
    1 - f.largura - MARGEM_INICIAL_PT / p.larguraPt,
    1 - f.altura - MARGEM_INICIAL_PT / p.alturaPt,
    p,
  );
}

/**
 * Posição do quadrado quando o ponteiro está em (`clientX`, `clientY`),
 * segurando o quadrado no ponto `pega` (fração do próprio quadrado, 0–1).
 */
export function posicaoDoPonteiro(
  clientX: number,
  clientY: number,
  area: { left: number; top: number; width: number; height: number },
  p: TamanhoPagina,
  pega: { x: number; y: number } = { x: 0.5, y: 0.5 },
): { x: number; y: number } {
  if (area.width <= 0 || area.height <= 0) return limitarPosicao(0, 0, p);
  const f = fracaoDoSelo(p);
  const x = (clientX - area.left) / area.width - pega.x * f.largura;
  const y = (clientY - area.top) / area.height - pega.y * f.altura;
  return limitarPosicao(x, y, p);
}

/** Passo das setas do teclado: 1% da página, 5% com Shift. */
export function moverComTeclado(
  tecla: string,
  shift: boolean,
  atual: { x: number; y: number },
  p: TamanhoPagina,
): { x: number; y: number } | null {
  const passo = shift ? 0.05 : 0.01;
  const delta: Record<string, [number, number]> = {
    ArrowLeft: [-passo, 0],
    ArrowRight: [passo, 0],
    ArrowUp: [0, -passo],
    ArrowDown: [0, passo],
  };
  const d = delta[tecla];
  if (!d) return null;
  return limitarPosicao(atual.x + d[0], atual.y + d[1], p);
}
