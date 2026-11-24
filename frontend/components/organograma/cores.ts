/**
 * Cores do heatmap do organograma (lista e diagrama).
 *
 * Os tokens do globals.css são triplas HSL cruas ("226 26% 11%"), então a cor
 * só vale embrulhada: `hsl(var(--token))`. Antes o heatmap era um
 * `hsl(hue, 60%, 92%)` fixo — pastel claro que, no tema escuro, apagava o
 * texto claro do nó. Os degraus "soft" de sucesso/alerta/perigo já têm versão
 * escura, e o `color-mix` faz a passagem contínua entre eles.
 */

const BAIXO = "hsl(var(--success-soft))";
const MEIO = "hsl(var(--warning-soft))";
const ALTO = "hsl(var(--danger-soft))";

/** Fundo do nó para um valor normalizado de 0 (baixo) a 1 (máximo). */
export function corDoCalor(normalizado: number): string {
  const n = Math.max(0, Math.min(1, normalizado));
  if (n <= 0.5) {
    const p = Math.round((n / 0.5) * 100);
    return `color-mix(in srgb, ${MEIO} ${p}%, ${BAIXO})`;
  }
  const p = Math.round(((n - 0.5) / 0.5) * 100);
  return `color-mix(in srgb, ${ALTO} ${p}%, ${MEIO})`;
}

/** Faixa da legenda: a mesma escala do nó, do baixo ao alto. */
export const LEGENDA_DO_CALOR = `linear-gradient(to right, ${BAIXO}, ${MEIO}, ${ALTO})`;
