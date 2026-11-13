import type { CSSProperties } from "react";

import { GRAFICO, corDaSerie } from "@/lib/chart-theme";

/**
 * Cores do diagrama de workflow (xyflow), para o diagrama de leitura, o editor
 * e a legenda falarem a mesma língua.
 *
 * O xyflow pinta por `style` inline e SVG, que não leem classe do Tailwind:
 * por isso `hsl(var(--token))`, que troca sozinho no tema escuro. Antes era
 * hex e `var(--card)` com hex de reserva — o token é um trio HSL, então `var(--card)` puro
 * era cor inválida: o nó ficava sem fundo e, no escuro, o "Concluído" (fundo
 * verde-claro fixo) ganhava texto claro do tema e sumia.
 */
const token = (nome: string) => `hsl(var(--${nome}))`;

export const COR_WF = {
  borda: token("border"),
  fundo: token("card"),
  texto: token("card-foreground"),
  inicial: token("info"),
  final: token("success"),
  finalFundo: token("success-soft"),
  atual: token("primary"),
  atualFundo: "hsl(var(--primary) / 0.12)",
  selecionado: token("warning"),
  selecionadoFundo: token("warning-soft"),
  transicao: GRAFICO.eixo,
  /** Transição com condição: a 4ª série da paleta (roxo), como era antes. */
  condicao: corDaSerie(3),
  rotuloFundo: token("surface-1"),
  rotuloTexto: GRAFICO.texto,
} as const;

/** Borda e fundo do nó conforme o papel. Ordem: atual/selecionado > final > inicial. */
export function estiloDoNo(papel: {
  atual?: boolean;
  selecionado?: boolean;
  final?: boolean;
  inicial?: boolean;
}): { border: string; background: string } {
  if (papel.atual) return { border: `2px solid ${COR_WF.atual}`, background: COR_WF.atualFundo };
  if (papel.selecionado) {
    return { border: `2px solid ${COR_WF.selecionado}`, background: COR_WF.selecionadoFundo };
  }
  if (papel.final) return { border: `2px solid ${COR_WF.final}`, background: COR_WF.finalFundo };
  if (papel.inicial) return { border: `2px dashed ${COR_WF.inicial}`, background: COR_WF.fundo };
  return { border: `1px solid ${COR_WF.borda}`, background: COR_WF.fundo };
}

/** Rótulo da transição: caixa e texto do tema, não a caixa branca fixa. */
export const ROTULO_TRANSICAO = {
  labelStyle: { fontSize: 11, fill: COR_WF.rotuloTexto },
  labelBgStyle: { fill: COR_WF.rotuloFundo, fillOpacity: 0.95 },
} as const;

/**
 * Variáveis do próprio xyflow (pontos do fundo, botões de zoom, texto do nó)
 * apontadas para os tokens. Vai no `style` do <ReactFlow>.
 */
export const TEMA_XYFLOW = {
  "--xy-node-color": COR_WF.texto,
  "--xy-background-pattern-color": token("border-strong"),
  "--xy-edge-label-background-color": COR_WF.rotuloFundo,
  "--xy-edge-label-color": COR_WF.rotuloTexto,
  "--xy-controls-button-background-color": token("surface-1"),
  "--xy-controls-button-background-color-hover": token("muted"),
  "--xy-controls-button-color": token("foreground"),
  "--xy-controls-button-color-hover": token("foreground"),
  "--xy-controls-button-border-color": token("border"),
} as CSSProperties;
