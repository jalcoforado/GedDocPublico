import {
  AlertCircle,
  Ban,
  Calendar,
  Check,
  CheckCheck,
  Clock,
  Flag,
  List,
  Loader,
  Lock,
  Minus,
  Pencil,
  type LucideIcon,
  Reply,
  Send,
  SplitSquareHorizontal,
  Undo2,
  Wallet,
  X,
} from "lucide-react";

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
  icon: LucideIcon;
}

export const TRAMITACAO_ROTULO: Record<SituacaoTramitacao, Rotulo> = {
  RASCUNHO: {
    label: "Rascunho",
    intent: "neutral",
    icon: Pencil,
  },
  AGUARDANDO_GESTOR: {
    label: "Aguardando o gestor da pasta",
    intent: "warning",
    icon: Clock,
  },
  AJUSTE_GESTOR: {
    label: "Ajuste solicitado pelo gestor",
    intent: "warning",
    icon: Reply,
  },
  AGUARDANDO_VALIDACAO: {
    label: "Aguardando validação financeira",
    intent: "warning",
    icon: Clock,
  },
  AJUSTE_VALIDACAO: {
    label: "Ajuste solicitado pela unidade financeira",
    intent: "warning",
    icon: Reply,
  },
  AGUARDANDO_AUTORIDADE: {
    label: "Aguardando a autoridade competente",
    intent: "warning",
    icon: Clock,
  },
  AJUSTE_AUTORIDADE: {
    label: "Ajuste solicitado pela autoridade",
    intent: "warning",
    icon: Reply,
  },
  AUTORIZADA: {
    label: "Autorizada para pagamento",
    intent: "success",
    icon: Check,
  },
  REJEITADA_GESTOR: {
    label: "Rejeitada pelo gestor",
    intent: "danger",
    icon: X,
  },
  INDEFERIDA_AUTORIDADE: {
    label: "Indeferida pela autoridade",
    intent: "danger",
    icon: X,
  },
  CANCELADA: { label: "Cancelada", intent: "neutral", icon: Ban },
};

export const FILA_ROTULO: Record<SituacaoFila, Rotulo> = {
  NAO_REGISTRADA: { label: "Não registrada", intent: "neutral", icon: Minus },
  REGISTRADA: { label: "Registrada", intent: "info", icon: List },
  BLOQUEADA: { label: "Bloqueada", intent: "danger", icon: Lock },
  ELEGIVEL: {
    label: "Elegível para pagamento",
    intent: "success",
    icon: Check,
  },
  AGUARDANDO_DISPONIBILIDADE: {
    label: "Aguardando disponibilidade financeira",
    intent: "warning",
    icon: Wallet,
  },
  EXCECAO_AUTORIZADA: {
    label: "Exceção autorizada",
    intent: "warning",
    icon: Flag,
  },
  CONCLUIDA: { label: "Concluída", intent: "success", icon: Check },
  RETIRADA: { label: "Retirada da fila", intent: "neutral", icon: Minus },
};

export const PAGAMENTO_ROTULO: Record<SituacaoPagamento, Rotulo> = {
  NAO_INICIADA: { label: "Não iniciado", intent: "neutral", icon: Minus },
  PROGRAMADA: { label: "Programado", intent: "info", icon: Calendar },
  ENVIADA_BANCO: { label: "Enviado ao banco", intent: "info", icon: Send },
  EM_PROCESSAMENTO: {
    label: "Em processamento",
    intent: "warning",
    icon: Loader,
  },
  PAGA_PARCIAL: {
    label: "Pago parcialmente",
    intent: "warning",
    icon: SplitSquareHorizontal,
  },
  PAGA: { label: "Pago", intent: "success", icon: Check },
  FALHOU: { label: "Falhou no banco", intent: "danger", icon: AlertCircle },
  CANCELADA: { label: "Cancelado", intent: "neutral", icon: Ban },
  ESTORNADA: { label: "Estornado", intent: "danger", icon: Undo2 },
  CONCILIADA: { label: "Conciliado", intent: "success", icon: CheckCheck },
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
