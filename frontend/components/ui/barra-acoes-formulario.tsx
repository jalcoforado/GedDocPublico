import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Rodapé fixo dos formulários longos: o que falta (ou "rascunho salvo") à
 * esquerda, os botões à direita, sempre à vista enquanto se rola. Nasceu no
 * formulário de abertura de processo; virou componente em 2026-11-10.
 *
 * Ordem dos botões, da esquerda para a direita: Cancelar (ghost) → ação
 * secundária (secondary, ex.: "Salvar como rascunho") → ação principal
 * (primary, o verbo do formulário: "Abrir processo", "Criar solicitação").
 */
export function BarraAcoesFormulario({
  status,
  children,
  className,
}: {
  /** Texto curto à esquerda: o que falta, ou o estado do rascunho. */
  status?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "sticky bottom-0 z-sticky -mx-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-border bg-surface-1/95 px-4 py-3 shadow-[0_-4px_12px_-6px_hsl(var(--foreground)/0.15)] backdrop-blur-md",
        "sm:mx-0 sm:rounded-xl sm:border",
        className,
      )}
    >
      <div className="min-w-0 text-xs text-foreground-muted" aria-live="polite">
        {status}
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}
