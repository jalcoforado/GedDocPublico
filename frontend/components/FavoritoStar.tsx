"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Star } from "lucide-react";

import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

/**
 * F5 — acompanhamento pessoal. Botão simples de alternância; não exige
 * `require_permission("processo", "atualizar")` (backend espelha isso):
 * favoritar é preferência de quem está lendo, não uma escrita no processo.
 *
 * Aceita `{ id, favorito }` estrutural — serve tanto o item da listagem
 * quanto o detalhe, sem exigir o `ProcessoDetail` inteiro.
 */
export function FavoritoStar({
  processo,
  size = "md",
}: {
  processo: { id: number; favorito: boolean };
  size?: "sm" | "md";
}) {
  const qc = useQueryClient();
  const toast = useToast();

  const m = useMutation({
    mutationFn: () =>
      processo.favorito
        ? api.processos.desfavoritar(processo.id)
        : api.processos.favoritar(processo.id),
    onSuccess: (atualizado) => {
      qc.setQueryData(["processo", processo.id], atualizado);
      qc.invalidateQueries({ queryKey: ["processos"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <button
      type="button"
      onClick={() => m.mutate()}
      disabled={m.isPending}
      aria-pressed={processo.favorito}
      aria-label={processo.favorito ? "Remover dos favoritos" : "Adicionar aos favoritos"}
      title={processo.favorito ? "Remover dos favoritos" : "Adicionar aos favoritos"}
      className={cn(
        "inline-flex items-center justify-center rounded-button transition-colors duration-fast",
        size === "sm" ? "h-6 w-6" : "h-9 w-9",
        "hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        "disabled:pointer-events-none disabled:opacity-50",
      )}
    >
      <Star
        className={cn(
          size === "sm" ? "h-3.5 w-3.5" : "h-5 w-5",
          processo.favorito
            ? "fill-warning text-warning"
            : "text-foreground-muted",
        )}
        aria-hidden="true"
      />
    </button>
  );
}
