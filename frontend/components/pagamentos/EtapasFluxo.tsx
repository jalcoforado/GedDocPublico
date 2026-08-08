"use client";

import { Check, ChevronRight, Reply, X } from "lucide-react";

import type { SituacaoTramitacao } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  CANCELADA,
  ETAPA_INFO,
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

const ESTADO_CLASSES: Record<Estado, { icone: string; card: string; conector: string }> = {
  concluida: {
    icone: "bg-success text-success-foreground",
    card: "border-success/40 bg-success-soft/30",
    conector: "text-success",
  },
  atual: {
    icone: "bg-info text-info-foreground",
    card: "border-info bg-info-soft/50 shadow-md ring-1 ring-info/30",
    conector: "text-border",
  },
  futura: {
    icone: "bg-muted text-muted-foreground",
    card: "border-border bg-surface-2",
    conector: "text-border",
  },
  ajuste: {
    icone: "bg-warning text-warning-foreground",
    card: "border-warning/50 bg-warning-soft/40",
    conector: "text-border",
  },
  encerrada: {
    icone: "bg-danger text-danger-foreground",
    card: "border-danger/50 bg-danger-soft/40",
    conector: "text-border",
  },
};

/**
 * Mini mapa do fluxo de pagamento: um cartão por etapa (papel responsável +
 * ícone), com a etapa atual expandida mostrando o que ela faz e as decisões
 * possíveis ali. Ajuste e estados terminais também expandem, com a
 * explicação correspondente no lugar das decisões.
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
      className="flex flex-col gap-2 sm:flex-row sm:items-stretch sm:gap-0"
    >
      {ETAPAS.map((etapa, idx) => {
        const estado = getEstado(idx);
        const classes = ESTADO_CLASSES[estado];
        const info = ETAPA_INFO[etapa.key];
        const Icon = info.icon;
        const isLast = idx === ETAPAS.length - 1;
        const expandida = estado === "atual" || estado === "ajuste" || estado === "encerrada";

        const descricao =
          estado === "encerrada"
            ? "Processo encerrado nesta etapa."
            : estado === "ajuste"
              ? "Ajuste solicitado — aguarda correção e reenvio."
              : info.descricao;

        const decisoes = estado === "atual" ? info.decisoes : [];

        return (
          <div key={etapa.key} className="contents">
            <div className="min-w-0 sm:flex-1">
              <div
                data-testid={`etapa-${etapa.key}`}
                data-estado={estado}
                className={cn(
                  "flex h-full flex-col gap-2 rounded-card border p-3 transition-all duration-base",
                  classes.card,
                )}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={cn(
                      "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
                      classes.icone,
                    )}
                  >
                    {estado === "concluida" && <Check className="h-4 w-4" aria-hidden="true" />}
                    {estado === "encerrada" && <X className="h-4 w-4" aria-hidden="true" />}
                    {estado === "ajuste" && <Reply className="h-4 w-4" aria-hidden="true" />}
                    {(estado === "atual" || estado === "futura") && (
                      <Icon className="h-4 w-4" aria-hidden="true" />
                    )}
                  </div>
                  <span
                    className={cn(
                      "text-sm font-semibold",
                      estado === "futura" ? "text-foreground-muted" : "text-foreground",
                    )}
                  >
                    {etapa.label}
                  </span>
                </div>

                {expandida && (
                  <div className="pl-12">
                    <p className="text-xs text-foreground-muted">{descricao}</p>
                    {decisoes.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {decisoes.map((decisao) => (
                          <Badge key={decisao.label} intent={decisao.intent} icon={decisao.icon}>
                            {decisao.label}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {!isLast && (
              <div className="hidden shrink-0 items-center justify-center px-1 sm:flex">
                <ChevronRight className={cn("h-4 w-4", classes.conector)} aria-hidden="true" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
