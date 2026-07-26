import type { StatusDebito } from "@/lib/api";

export type BadgeIntent = "neutral" | "warning" | "info" | "success" | "danger";

// Fonte única de verdade dos 16 status do pedido (Especificação v2.0 seção 13).
export const DEBITO_STATUS_BADGE: Record<StatusDebito, { intent: BadgeIntent; label: string }> = {
  RASCUNHO: { intent: "neutral", label: "Rascunho" },
  EM_VALIDACAO: { intent: "warning", label: "Em validação" },
  DEVOLVIDO: { intent: "warning", label: "Devolvido" },
  VALIDADO: { intent: "info", label: "Validado" },
  ENVIADO_SECRETARIO: { intent: "info", label: "Enviado pelo secretário" },
  AGUARDANDO_AUTORIZACAO: { intent: "warning", label: "Aguardando autorização" },
  AUTORIZADO: { intent: "info", label: "Autorizado e reservado" },
  ENVIADO_TESOURARIA: { intent: "info", label: "Enviado à tesouraria" },
  EM_PROCESSAMENTO: { intent: "warning", label: "Em processamento" },
  PAGO_PARCIAL: { intent: "warning", label: "Pago parcial" },
  PAGO: { intent: "success", label: "Pago" },
  CONCILIADO: { intent: "success", label: "Conciliado" },
  REJEITADO: { intent: "danger", label: "Rejeitado" },
  SUSPENSO: { intent: "warning", label: "Suspenso" },
  CANCELADO: { intent: "danger", label: "Cancelado" },
  ESTORNADO: { intent: "danger", label: "Estornado" },
};

// Abas de filtro da lista de contas a pagar (principais etapas do rito).
export const DEBITO_STATUS_TABS: { value: StatusDebito | ""; label: string }[] = [
  { value: "", label: "Todos" },
  { value: "RASCUNHO", label: "Rascunho" },
  { value: "EM_VALIDACAO", label: "Em validação" },
  { value: "VALIDADO", label: "Validado" },
  { value: "ENVIADO_SECRETARIO", label: "Aguardando autorização" },
  { value: "AUTORIZADO", label: "Autorizado" },
  { value: "ENVIADO_TESOURARIA", label: "Na tesouraria" },
  { value: "PAGO_PARCIAL", label: "Pago parcial" },
  { value: "PAGO", label: "Pago" },
  { value: "SUSPENSO", label: "Suspenso" },
  { value: "REJEITADO", label: "Rejeitado" },
  { value: "CANCELADO", label: "Cancelado" },
];
