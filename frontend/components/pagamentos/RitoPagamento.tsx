"use client";

import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

export type PassoRito = "solicitar" | "aprovar" | "autorizar" | "liberar" | "pagar";

const PASSOS: { key: PassoRito; label: string }[] = [
  { key: "solicitar", label: "Solicitar" },
  { key: "aprovar", label: "Aprovar" },
  { key: "autorizar", label: "Autorizar despesa" },
  { key: "liberar", label: "Liberar pagamento" },
  { key: "pagar", label: "Pagar" },
];

interface RitoPagamentoProps {
  /** Passo correspondente à tela atual (aceso na cor da marca). */
  atual?: PassoRito;
  /** Passos concluídos (ex.: refletindo o status do débito) — exibem check. */
  concluidos?: string[];
}

/**
 * Assinatura visual do módulo Pagamentos: os 5 atos do rito da Lei 4.320/64
 * (Solicitar → Aprovar → Autorizar despesa → Liberar pagamento → Pagar) como
 * uma linha discreta de wayfinding. Sem animação.
 */
export function RitoPagamento({ atual, concluidos = [] }: RitoPagamentoProps) {
  return (
    <ol aria-label="Rito do pagamento" className="flex items-center">
      {PASSOS.map((passo, idx) => {
        const isAtual = passo.key === atual;
        const isConcluido = !isAtual && concluidos.includes(passo.key);
        const isLast = idx === PASSOS.length - 1;

        return (
          <li
            key={passo.key}
            className={cn("flex items-center", !isLast && "flex-1")}
          >
            <div className="flex items-center gap-1.5 sm:gap-2" title={passo.label}>
              <span
                aria-hidden="true"
                className={cn(
                  "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold leading-none",
                  isAtual && "bg-brand/12 text-brand dark:bg-brand/25 dark:text-brand-light",
                  isConcluido && "bg-muted text-foreground-subtle",
                  !isAtual && !isConcluido && "bg-muted text-foreground-subtle",
                )}
              >
                {isConcluido ? <Check className="h-3 w-3" aria-hidden="true" /> : idx + 1}
              </span>
              <span
                className={cn(
                  "hidden whitespace-nowrap text-xs font-medium sm:inline",
                  isAtual
                    ? "text-brand dark:text-brand-light"
                    : "text-foreground-subtle",
                )}
              >
                {passo.label}
              </span>
              <span className="sr-only sm:hidden">{passo.label}</span>
            </div>
            {!isLast && (
              <span aria-hidden="true" className="mx-2 h-px flex-1 bg-border sm:mx-3" />
            )}
          </li>
        );
      })}
    </ol>
  );
}
