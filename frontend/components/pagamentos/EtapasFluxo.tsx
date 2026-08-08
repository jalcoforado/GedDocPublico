"use client";

import { Check, Reply, X } from "lucide-react";

import type { SituacaoTramitacao } from "@/lib/api";
import {
  AUTORIZADA,
  CANCELADA,
  ETAPA_POR_TRAMITACAO,
  ETAPAS,
  INDEFERIDA_AUTORIDADE,
  REJEITADA_GESTOR,
} from "@/components/pagamentos/situacoes";
import { cn } from "@/lib/utils";

interface EtapasFluxoProps {
  tramitacao: SituacaoTramitacao;
}

type Estado = "concluida" | "atual" | "futura" | "ajuste" | "encerrada";

const ESTADO_CLASSES: Record<Estado, { badge: string; linha: string }> = {
  concluida: {
    badge: "bg-success-soft text-success-soft-foreground",
    linha: "bg-success",
  },
  atual: {
    badge: "bg-info-soft text-info-soft-foreground ring-2 ring-info/40",
    linha: "bg-muted",
  },
  futura: {
    badge: "bg-muted text-muted-foreground",
    linha: "bg-muted",
  },
  ajuste: {
    badge: "bg-warning-soft text-warning-soft-foreground",
    linha: "bg-muted",
  },
  encerrada: {
    badge: "bg-danger-soft text-danger-soft-foreground",
    linha: "bg-muted",
  },
};

/**
 * Stepper das cinco etapas do fluxo de pagamento.
 * Marca a etapa atual, as concluídas, as futuras, ajustes e terminais.
 */
export function EtapasFluxo({ tramitacao }: EtapasFluxoProps) {
  const etapaAtual = ETAPA_POR_TRAMITACAO[tramitacao];
  const etapaAtualIdx = ETAPAS.findIndex((e) => e.key === etapaAtual);

  const isAjuste = tramitacao.startsWith("AJUSTE_");
  const terminais: SituacaoTramitacao[] = [REJEITADA_GESTOR, INDEFERIDA_AUTORIDADE, CANCELADA];
  const isTerminal = terminais.includes(tramitacao);

  const getEstado = (idx: number): Estado => {
    // Ajuste pendente volta para unidade
    if (isAjuste && idx === 0) return "ajuste";

    // Terminal (rejeitado, indeferido, cancelado)
    if (isTerminal) {
      if (idx === etapaAtualIdx) return "encerrada";
      if (idx < etapaAtualIdx) return "concluida";
      return "futura";
    }

    // Normal: rascunho, aguardando, autorizada
    if (idx === etapaAtualIdx) return "atual";
    if (idx < etapaAtualIdx) return "concluida";
    return "futura";
  };

  return (
    <div
      aria-label="Etapas do fluxo de pagamento"
      className="flex items-center"
    >
      {ETAPAS.map((etapa, idx) => {
        const estado = getEstado(idx);
        const classes = ESTADO_CLASSES[estado];
        const isLast = idx === ETAPAS.length - 1;

        return (
          <div
            key={etapa.key}
            className={cn("flex items-center", !isLast && "flex-1")}
          >
            <div className="flex flex-col items-center gap-1.5">
              <div
                data-testid={`etapa-${etapa.key}`}
                data-estado={estado}
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold transition-colors duration-base",
                  classes.badge,
                )}
              >
                {estado === "concluida" && <Check className="h-4 w-4" aria-hidden="true" />}
                {estado === "encerrada" && <X className="h-4 w-4" aria-hidden="true" />}
                {estado === "ajuste" && <Reply className="h-4 w-4" aria-hidden="true" />}
                {(estado === "atual" || estado === "futura") && idx + 1}
              </div>
              <span
                className={cn(
                  "hidden text-xs font-medium sm:inline",
                  estado === "atual" ? "text-foreground" : "text-foreground-muted",
                )}
              >
                {etapa.curto}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  "mx-2 h-0.5 flex-1 rounded-full transition-colors duration-base",
                  classes.linha,
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
