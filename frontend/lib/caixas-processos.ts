import {
  Archive,
  ArrowDownToLine,
  ArrowUpFromLine,
  FileSearch,
  FolderInput,
  type LucideIcon,
  PenLine,
  Send,
} from "lucide-react";

import type { CaixaProcesso } from "@/lib/api";

/** Tela de Processos — o caminho que as caixas recortam. */
export const ROTA_PROCESSOS = "/m/protocolo/processos";

/**
 * As caixas de trabalho, na ordem do layout de referência (protótipo Figma
 * "Sistema - Aprimora"). Fonte única da ordem e dos rótulos: o menu lateral
 * monta os subitens de "Processos" daqui, e a tela valida o `?caixa=` da URL
 * contra esta lista.
 */
export const CAIXAS: { caixa: CaixaProcesso; rotulo: string; icone: LucideIcon }[] = [
  { caixa: "entrada", rotulo: "Caixa de entrada", icone: ArrowDownToLine },
  { caixa: "saida", rotulo: "Caixa de saída", icone: ArrowUpFromLine },
  { caixa: "analise", rotulo: "Análise", icone: FileSearch },
  { caixa: "externos", rotulo: "Externos", icone: FolderInput },
  { caixa: "aguardando_assinatura", rotulo: "Aguardando assinatura", icone: PenLine },
  { caixa: "enviado_para_assinatura", rotulo: "Enviado para assinatura", icone: Send },
  { caixa: "arquivados", rotulo: "Arquivados", icone: Archive },
];

export function caixaDaUrl(valor: string | null): CaixaProcesso | undefined {
  return CAIXAS.find((c) => c.caixa === valor)?.caixa;
}

export function rotuloDaCaixa(caixa: CaixaProcesso): string {
  return CAIXAS.find((c) => c.caixa === caixa)?.rotulo ?? caixa;
}

/**
 * Abrir uma caixa é uma visão NOVA, não um filtro a mais: o link carrega só a
 * caixa e `ativos=0`, descartando busca, assunto e período. É o que mantém a
 * promessa do menu — o número ao lado do rótulo é o total da lista que abre.
 * Somar a caixa aos filtros em curso quebraria essa conta em silêncio.
 */
export function hrefDaCaixa(caixa: CaixaProcesso | undefined, base = ROTA_PROCESSOS): string {
  return caixa ? `${base}?caixa=${caixa}&ativos=0` : `${base}?ativos=0`;
}
