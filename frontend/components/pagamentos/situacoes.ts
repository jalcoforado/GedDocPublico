import type {
  SituacaoFila,
  SituacaoPagamento,
  SituacaoTramitacao,
} from "@/lib/api";

export type Intent =
  | "neutral"
  | "warning"
  | "info"
  | "success"
  | "danger";

// Constantes de estado para uso em lógica condicional
export const RASCUNHO = "RASCUNHO" as const;
export const AGUARDANDO_GESTOR = "AGUARDANDO_GESTOR" as const;
export const AJUSTE_GESTOR = "AJUSTE_GESTOR" as const;
export const AGUARDANDO_VALIDACAO = "AGUARDANDO_VALIDACAO" as const;
export const AJUSTE_VALIDACAO = "AJUSTE_VALIDACAO" as const;
export const AGUARDANDO_AUTORIDADE = "AGUARDANDO_AUTORIDADE" as const;
export const AJUSTE_AUTORIDADE = "AJUSTE_AUTORIDADE" as const;
export const AUTORIZADA = "AUTORIZADA" as const;
export const REJEITADA_GESTOR = "REJEITADA_GESTOR" as const;
export const INDEFERIDA_AUTORIDADE = "INDEFERIDA_AUTORIDADE" as const;
export const CANCELADA = "CANCELADA" as const;

/** Um rótulo tem SEMPRE texto e ícone — status que se distingue só por cor é
 *  inacessível (spec §13 do pedido). */
export interface Rotulo {
  label: string;
  intent: Intent;
  icone: string;
}

export const TRAMITACAO_ROTULO: Record<SituacaoTramitacao, Rotulo> = {
  RASCUNHO: {
    label: "Rascunho",
    intent: "neutral",
    icone: "pencil",
  },
  AGUARDANDO_GESTOR: {
    label: "Aguardando o gestor da pasta",
    intent: "warning",
    icone: "clock",
  },
  AJUSTE_GESTOR: {
    label: "Ajuste solicitado pelo gestor",
    intent: "warning",
    icone: "reply",
  },
  AGUARDANDO_VALIDACAO: {
    label: "Aguardando validação financeira",
    intent: "warning",
    icone: "clock",
  },
  AJUSTE_VALIDACAO: {
    label: "Ajuste solicitado pela unidade financeira",
    intent: "warning",
    icone: "reply",
  },
  AGUARDANDO_AUTORIDADE: {
    label: "Aguardando a autoridade competente",
    intent: "warning",
    icone: "clock",
  },
  AJUSTE_AUTORIDADE: {
    label: "Ajuste solicitado pela autoridade",
    intent: "warning",
    icone: "reply",
  },
  AUTORIZADA: {
    label: "Autorizada para pagamento",
    intent: "success",
    icone: "check",
  },
  REJEITADA_GESTOR: {
    label: "Rejeitada pelo gestor",
    intent: "danger",
    icone: "x",
  },
  INDEFERIDA_AUTORIDADE: {
    label: "Indeferida pela autoridade",
    intent: "danger",
    icone: "x",
  },
  CANCELADA: { label: "Cancelada", intent: "neutral", icone: "ban" },
};

export const FILA_ROTULO: Record<SituacaoFila, Rotulo> = {
  NAO_REGISTRADA: { label: "Não registrada", intent: "neutral", icone: "minus" },
  REGISTRADA: { label: "Registrada", intent: "info", icone: "list" },
  BLOQUEADA: { label: "Bloqueada", intent: "danger", icone: "lock" },
  ELEGIVEL: {
    label: "Elegível para pagamento",
    intent: "success",
    icone: "check",
  },
  AGUARDANDO_DISPONIBILIDADE: {
    label: "Aguardando disponibilidade financeira",
    intent: "warning",
    icone: "wallet",
  },
  EXCECAO_AUTORIZADA: {
    label: "Exceção autorizada",
    intent: "warning",
    icone: "flag",
  },
  CONCLUIDA: { label: "Concluída", intent: "success", icone: "check" },
  RETIRADA: { label: "Retirada da fila", intent: "neutral", icone: "minus" },
};

export const PAGAMENTO_ROTULO: Record<SituacaoPagamento, Rotulo> = {
  NAO_INICIADA: { label: "Não iniciado", intent: "neutral", icone: "minus" },
  PROGRAMADA: { label: "Programado", intent: "info", icone: "calendar" },
  ENVIADA_BANCO: { label: "Enviado ao banco", intent: "info", icone: "send" },
  EM_PROCESSAMENTO: {
    label: "Em processamento",
    intent: "warning",
    icone: "loader",
  },
  PAGA_PARCIAL: {
    label: "Pago parcialmente",
    intent: "warning",
    icone: "split",
  },
  PAGA: { label: "Pago", intent: "success", icone: "check" },
  FALHOU: { label: "Falhou no banco", intent: "danger", icone: "alert-circle" },
  CANCELADA: { label: "Cancelado", intent: "neutral", icone: "ban" },
  ESTORNADA: { label: "Estornado", intent: "danger", icone: "undo-2" },
  CONCILIADA: { label: "Conciliado", intent: "success", icone: "check-check" },
};

export type EtapaFluxo =
  | "UNIDADE"
  | "GESTOR"
  | "VALIDACAO"
  | "AUTORIDADE"
  | "TESOURARIA";

export const ETAPAS: { key: EtapaFluxo; label: string; curto: string }[] = [
  { key: "UNIDADE", label: "Unidade setorial", curto: "Unidade" },
  { key: "GESTOR", label: "Gestor da pasta", curto: "Gestor" },
  { key: "VALIDACAO", label: "Validação financeira", curto: "Validação" },
  {
    key: "AUTORIDADE",
    label: "Autoridade competente",
    curto: "Autoridade",
  },
  { key: "TESOURARIA", label: "Tesouraria", curto: "Tesouraria" },
];

/** Espelha `ETAPA_POR_TRAMITACAO` de `services/pagamentos_estados.py`.
 *  Divergir daqui faz o stepper acender a etapa errada. */
export const ETAPA_POR_TRAMITACAO: Record<SituacaoTramitacao, EtapaFluxo> = {
  RASCUNHO: "UNIDADE",
  AGUARDANDO_GESTOR: "GESTOR",
  AJUSTE_GESTOR: "UNIDADE",
  AGUARDANDO_VALIDACAO: "VALIDACAO",
  AJUSTE_VALIDACAO: "UNIDADE",
  AGUARDANDO_AUTORIDADE: "AUTORIDADE",
  AJUSTE_AUTORIDADE: "UNIDADE",
  AUTORIZADA: "TESOURARIA",
  REJEITADA_GESTOR: "GESTOR",
  INDEFERIDA_AUTORIDADE: "AUTORIDADE",
  CANCELADA: "UNIDADE",
};
