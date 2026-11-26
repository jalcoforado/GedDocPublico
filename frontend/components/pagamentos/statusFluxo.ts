/**
 * Índice de etapa (0-4) para agrupamento/contagem no resumo da listagem de
 * solicitações. Rótulos e cores visuais vivem em `situacoes.ts` — este
 * arquivo existia com um segundo conjunto de rótulos/cores duplicado e
 * divergente (ex: CANCELADA como "danger" aqui vs "neutral" lá); removido
 * para não haver duas fontes de verdade.
 */

import type { SituacaoTramitacao } from "@/lib/api";

/** Situações de cada etapa, por índice. É o inverso de `getEtapaIndex` —
 *  e a fonte dele: a tela de Solicitações manda estas listas ao servidor ao
 *  filtrar por etapa, e `__tests__/pagamentos-solicitacoes-pagina.test.tsx`
 *  confere que os dois não divergem. */
export const SITUACOES_POR_ETAPA: SituacaoTramitacao[][] = [
  ["RASCUNHO"],
  ["AGUARDANDO_GESTOR", "AJUSTE_GESTOR", "REJEITADA_GESTOR"],
  ["AGUARDANDO_VALIDACAO", "AJUSTE_VALIDACAO"],
  ["AGUARDANDO_AUTORIDADE", "AJUSTE_AUTORIDADE", "INDEFERIDA_AUTORIDADE"],
  ["AUTORIZADA", "CANCELADA"],
];

/** Mapeia SituacaoTramitacao para índice da etapa */
export function getEtapaIndex(situacao: SituacaoTramitacao): number {
  if (situacao === "RASCUNHO") return 0;
  if (["AGUARDANDO_GESTOR", "AJUSTE_GESTOR", "REJEITADA_GESTOR"].includes(situacao)) return 1;
  if (["AGUARDANDO_VALIDACAO", "AJUSTE_VALIDACAO"].includes(situacao)) return 2;
  if (["AGUARDANDO_AUTORIDADE", "AJUSTE_AUTORIDADE", "INDEFERIDA_AUTORIDADE"].includes(situacao)) return 3;
  if (["AUTORIZADA", "CANCELADA"].includes(situacao)) return 4;
  return 0;
}
