/**
 * Helpers puros de microcopy/intent para badges. SEM JSX. Quem renderiza
 * é o `<Badge>` ou similar — esta camada centraliza a tradução
 * status backend → (intent, label, ícone).
 *
 * Princípios:
 *  - Funções puras (zero I/O, zero side-effect, fáceis de testar).
 *  - Modos "servidor" e "cidadao" recebem labels distintos (D-CIDADAO
 *    do PR 5b: linguagem cuidadosa para o portal público).
 *  - Não infere status novo. Apenas mapeia o que o backend já mandou.
 *  - Pode retornar `null` quando não há badge a exibir (ex: prazo
 *    "sem_previsao" no portal do cidadão).
 */

import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  type LucideIcon,
} from "lucide-react";

import type {
  ChecklistItem,
  PrazoCidadao,
  PrazoInfo,
  StatusPrazo,
  StatusPrazoCidadao,
} from "@/lib/api";

export type BadgeIntent =
  | "neutral"
  | "success"
  | "danger"
  | "warning"
  | "info"
  | "brand";

export type BadgeModo = "servidor" | "cidadao";

export interface BadgeSpec {
  intent: BadgeIntent;
  label: string;
  icon?: LucideIcon;
}

// =============================================================================
// Status do processo (ativo / encerrado)
// =============================================================================

/**
 * Badge de status macro do processo. Não substitui o badge de prazo
 * (esse é separado, ver `prazoBadge`).
 *
 * Modo cidadão: "Em andamento" / "Concluído". Modo servidor:
 * "Em tramitação" / "Encerrado". Cor de encerrado intencionalmente
 * `info` (não `neutral`) — D-LINGUAGEM-ENCERRADO permite a cor em
 * contexto de processo concluído.
 */
export function statusProcessoBadge(
  p: { ativo: boolean },
  modo: BadgeModo,
): BadgeSpec {
  if (p.ativo) {
    return {
      intent: "success",
      label: modo === "cidadao" ? "Em andamento" : "Em tramitação",
      icon: Clock,
    };
  }
  return {
    intent: "info",
    label: modo === "cidadao" ? "Concluído" : "Encerrado",
    icon: CheckCircle2,
  };
}

// =============================================================================
// Prazo (PR 5b)
// =============================================================================

const PRAZO_ADMIN: Record<StatusPrazo, BadgeSpec | null> = {
  sem_prazo: null,
  dentro_do_prazo: {
    intent: "success",
    label: "Dentro do prazo",
    icon: Clock,
  },
  vencendo: {
    intent: "warning",
    label: "Vencendo",
    icon: AlertTriangle,
  },
  atrasado: {
    intent: "danger",
    label: "Atrasado",
    icon: AlertCircle,
  },
  concluido_no_prazo: {
    intent: "success",
    label: "Concluído no prazo",
    icon: CheckCircle2,
  },
  concluido_atrasado: {
    intent: "warning",
    label: "Concluído com atraso",
    icon: CheckCircle2,
  },
};

const PRAZO_CIDADAO: Record<StatusPrazoCidadao, BadgeSpec | null> = {
  // Omitidos por D-CIDADAO: redundantes com badge "Em andamento"/"Concluído".
  sem_previsao: null,
  concluido: null,
  dentro_da_previsao: {
    intent: "info",
    label: "Dentro da previsão",
    icon: Clock,
  },
  proximo_do_prazo: {
    intent: "warning",
    label: "Próximo do prazo",
    icon: AlertTriangle,
  },
  fora_da_previsao: {
    intent: "danger",
    label: "Fora da previsão",
    icon: AlertCircle,
  },
};

/**
 * Badge de prazo. Retorna `null` quando não há nada a exibir.
 *
 * Modo "servidor" enriquece o label com dias restantes/atraso quando
 * disponível; modo "cidadao" NUNCA expõe contagem em dias (D-CIDADAO).
 */
export function prazoBadge(
  prazo: PrazoInfo | PrazoCidadao,
  modo: BadgeModo,
): BadgeSpec | null {
  if (modo === "cidadao") {
    const p = prazo as PrazoCidadao;
    return PRAZO_CIDADAO[p.status];
  }

  const p = prazo as PrazoInfo;
  const base = PRAZO_ADMIN[p.status];
  if (!base) return null;

  // Enriquece label com contagem de dias, quando aplicável.
  if (p.status === "dentro_do_prazo" && p.dias_restantes !== null) {
    return { ...base, label: `${base.label} (${p.dias_restantes} d.)` };
  }
  if (p.status === "vencendo" && p.dias_restantes !== null) {
    return { ...base, label: `${base.label} (${p.dias_restantes} d.)` };
  }
  if (p.status === "atrasado" && p.dias_atraso !== null) {
    return {
      ...base,
      label: `Atrasado em ${p.dias_atraso} d.`,
    };
  }
  return base;
}

// =============================================================================
// Documentos do checklist
// =============================================================================

/**
 * Badge de um item do checklist documental. Linguagem unificada
 * cidadão/servidor (não precisa do `modo`).
 *
 *  - enviado → "Enviado" (success, ícone Check)
 *  - pendente obrigatório → "Obrigatório · pendente" (warning)
 *  - pendente opcional → "Opcional · pendente" (neutral)
 */
export function documentoBadge(item: ChecklistItem): BadgeSpec {
  if (item.enviado) {
    return { intent: "success", label: "Enviado", icon: Check };
  }
  return item.obrigatorio
    ? { intent: "warning", label: "Obrigatório · pendente" }
    : { intent: "neutral", label: "Opcional · pendente" };
}
