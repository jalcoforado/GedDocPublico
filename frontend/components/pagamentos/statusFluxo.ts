/**
 * Status e configurações visuais para o fluxo de pagamentos (F1, Tarefa 7+).
 */

import type { SituacaoTramitacao } from "@/lib/api";

export interface StatusConfig {
  label: string;
  intent: "neutral" | "info" | "warning" | "success" | "danger";
  descricao: string;
}

export const SITUACAO_TRAMITACAO_CONFIG: Record<SituacaoTramitacao, StatusConfig> = {
  RASCUNHO: {
    label: "Rascunho",
    intent: "neutral",
    descricao: "Solicitação em elaboração",
  },
  AGUARDANDO_GESTOR: {
    label: "Aguardando gestor",
    intent: "warning",
    descricao: "Aguardando decisão do gestor",
  },
  AJUSTE_GESTOR: {
    label: "Ajuste solicitado",
    intent: "warning",
    descricao: "Gestor solicitou ajustes",
  },
  AGUARDANDO_VALIDACAO: {
    label: "Aguardando validação",
    intent: "warning",
    descricao: "Aguardando validação",
  },
  AJUSTE_VALIDACAO: {
    label: "Ajuste solicitado",
    intent: "warning",
    descricao: "Validador solicitou ajustes",
  },
  AGUARDANDO_AUTORIDADE: {
    label: "Aguardando autoridade",
    intent: "warning",
    descricao: "Aguardando autorização final",
  },
  AJUSTE_AUTORIDADE: {
    label: "Ajuste solicitado",
    intent: "warning",
    descricao: "Autoridade solicitou ajustes",
  },
  AUTORIZADA: {
    label: "Autorizada",
    intent: "success",
    descricao: "Solicitação aprovada e autorizada",
  },
  REJEITADA_GESTOR: {
    label: "Rejeitada",
    intent: "danger",
    descricao: "Rejeitada pelo gestor",
  },
  INDEFERIDA_AUTORIDADE: {
    label: "Indeferida",
    intent: "danger",
    descricao: "Indeferida pela autoridade",
  },
  CANCELADA: {
    label: "Cancelada",
    intent: "danger",
    descricao: "Solicitação cancelada",
  },
};

/** Etapas do fluxo para o stepper */
export const ETAPAS_FLUXO = [
  { etapa: "rascunho", label: "Rascunho" },
  { etapa: "gestor", label: "Gestor" },
  { etapa: "validacao", label: "Validação" },
  { etapa: "autoridade", label: "Autoridade" },
  { etapa: "concluido", label: "Concluído" },
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

/** Determina se a situação é uma que aguarda decisão */
export function aguardandoDecisao(situacao: SituacaoTramitacao): boolean {
  return [
    "AGUARDANDO_GESTOR",
    "AGUARDANDO_VALIDACAO",
    "AGUARDANDO_AUTORIDADE",
  ].includes(situacao);
}

/** Determina se a situação é uma solicitação de ajuste */
export function solicitaAjuste(situacao: SituacaoTramitacao): boolean {
  return [
    "AJUSTE_GESTOR",
    "AJUSTE_VALIDACAO",
    "AJUSTE_AUTORIDADE",
  ].includes(situacao);
}
