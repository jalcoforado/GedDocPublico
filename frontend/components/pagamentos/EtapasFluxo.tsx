"use client";

import type { SituacaoTramitacao } from "@/lib/api";
import {
  AUTORIZADA,
  CANCELADA,
  ETAPA_POR_TRAMITACAO,
  ETAPAS,
  INDEFERIDA_AUTORIDADE,
  REJEITADA_GESTOR,
  type EtapaFluxo,
} from "@/components/pagamentos/situacoes";
import { cn } from "@/lib/utils";

interface EtapasFluxoProps {
  tramitacao: SituacaoTramitacao;
}

/**
 * Stepper das cinco etapas do fluxo de pagamento.
 * Marca a etapa atual, as concluídas, as futuras, ajustes e terminais.
 */
export function EtapasFluxo({ tramitacao }: EtapasFluxoProps) {
  const etapaAtual = ETAPA_POR_TRAMITACAO[tramitacao];
  const etapaAtualIdx = ETAPAS.findIndex((e) => e.key === etapaAtual);

  const _isAjuste = tramitacao.startsWith("AJUSTE_");
  const terminais: SituacaoTramitacao[] = [REJEITADA_GESTOR, INDEFERIDA_AUTORIDADE, CANCELADA];
  const _isTerminal = terminais.includes(tramitacao);

  const getEstado = (idx: number): "concluida" | "atual" | "futura" | "ajuste" | "encerrada" => {
    // Ajuste pendente volta para unidade
    if (_isAjuste && idx === 0) return "ajuste";

    // Terminal (rejeitado, indeferido, cancelado)
    if (_isTerminal) {
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
      className="flex items-center gap-2"
    >
      {ETAPAS.map((etapa, idx) => {
        const estado = getEstado(idx);
        const isLast = idx === ETAPAS.length - 1;

        return (
          <div
            key={etapa.key}
            className={cn("flex items-center", !isLast && "flex-1")}
          >
            <div
              data-testid={`etapa-${etapa.key}`}
              data-estado={estado}
              className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold",
                estado === "atual" &&
                  "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200",
                estado === "concluida" &&
                  "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-200",
                estado === "futura" &&
                  "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
                estado === "ajuste" &&
                  "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-200",
                estado === "encerrada" &&
                  "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200"
              )}
            >
              {idx + 1}
            </div>
            <span className="ml-2 hidden text-sm font-medium sm:inline">
              {etapa.curto}
            </span>
            {!isLast && (
              <div
                className={cn(
                  "mx-2 h-px flex-1",
                  idx < etapaAtualIdx
                    ? "bg-green-300 dark:bg-green-700"
                    : "bg-gray-300 dark:bg-gray-600"
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
