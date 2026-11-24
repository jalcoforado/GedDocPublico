/**
 * Cores dos gráficos (recharts / xyflow). Única ponte entre os tokens do
 * globals.css e as bibliotecas de gráfico — o `design:check` deixa este
 * arquivo na allowlist justamente para tela nenhuma escolher cor de série.
 *
 * Os valores são `hsl(var(--token))`: trocam sozinhos no tema escuro e com a
 * identidade do município, sem a tela saber de tema.
 */

/** Séries categóricas, na ordem de uso. Mais de seis séries: agrupe em "Outros". */
export const SERIES = [
  "hsl(var(--grafico-1))",
  "hsl(var(--grafico-2))",
  "hsl(var(--grafico-3))",
  "hsl(var(--grafico-4))",
  "hsl(var(--grafico-5))",
  "hsl(var(--grafico-6))",
] as const;

export function corDaSerie(i: number): string {
  return SERIES[i % SERIES.length];
}

/** Papéis fixos: entrada × saída, meta, e o "chão" do gráfico. */
export const GRAFICO = {
  /** Série única ou principal. */
  principal: "hsl(var(--grafico-1))",
  /** Comparação com a principal (período anterior, outra unidade). */
  secundaria: "hsl(var(--grafico-2))",
  positivo: "hsl(var(--success))",
  negativo: "hsl(var(--danger))",
  alerta: "hsl(var(--warning))",
  grade: "hsl(var(--border))",
  eixo: "hsl(var(--foreground-subtle))",
  texto: "hsl(var(--foreground))",
  cursor: "hsl(var(--muted))",
} as const;

/** Props comuns de eixo (recharts): texto pequeno, discreto, sem linha. */
export const EIXO = {
  tick: { fill: "hsl(var(--foreground-subtle))", fontSize: 11 },
  axisLine: false,
  tickLine: false,
} as const;
