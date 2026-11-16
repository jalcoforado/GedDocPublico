import {
  Archive,
  ArrowDownToLine,
  ArrowUpFromLine,
  FileSearch,
  FolderInput,
  type LucideIcon,
  PenLine,
  Send,
  Undo2,
} from "lucide-react";

import type { CaixaProcesso } from "@/lib/api";

/** Tela de Processos — o caminho que as caixas recortam. */
export const ROTA_PROCESSOS = "/m/protocolo/processos";

/**
 * As caixas de trabalho, na ordem do layout de referência (protótipo Figma
 * "Sistema - Aprimora"). Fonte única da ordem e dos rótulos: as abas da tela
 * de Processos (`components/protocolo/AbasCaixas.tsx`) saem daqui, e a tela
 * valida o `?caixa=` da URL contra esta lista.
 *
 * `rotulo` é o nome completo (título da tela, painel, leitor de tela);
 * `rotuloCurto` é o da aba, onde as nove precisam caber lado a lado a 1280px.
 */
export const CAIXAS: {
  caixa: CaixaProcesso;
  rotulo: string;
  rotuloCurto: string;
  icone: LucideIcon;
}[] = [
  { caixa: "entrada", rotulo: "Caixa de entrada", rotuloCurto: "Entrada", icone: ArrowDownToLine },
  { caixa: "saida", rotulo: "Caixa de saída", rotuloCurto: "Saída", icone: ArrowUpFromLine },
  // O que enviei e o destino recusou: fica logo depois da saída, de onde veio.
  { caixa: "recusados", rotulo: "Recusados", rotuloCurto: "Recusados", icone: Undo2 },
  { caixa: "analise", rotulo: "Análise", rotuloCurto: "Análise", icone: FileSearch },
  { caixa: "externos", rotulo: "Externos", rotuloCurto: "Externos", icone: FolderInput },
  // Documento esperando a MINHA assinatura — a mesma regra da tela "Para
  // assinar" (`assinaturas.listar_minhas_pendentes`), daí o nome curto igual.
  {
    caixa: "aguardando_assinatura",
    rotulo: "Aguardando assinatura",
    rotuloCurto: "Para assinar",
    icone: PenLine,
  },
  // Documento que EU mandei para outros assinarem.
  {
    caixa: "enviado_para_assinatura",
    rotulo: "Enviado para assinatura",
    rotuloCurto: "Enviados p/ assinar",
    icone: Send,
  },
  { caixa: "arquivados", rotulo: "Arquivados", rotuloCurto: "Arquivados", icone: Archive },
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
