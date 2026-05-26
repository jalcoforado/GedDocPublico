"use client";

import { Search } from "lucide-react";

import { useCommandPalette } from "@/components/CommandPalette";
import { cn } from "@/lib/utils";

/** Trigger do Command Palette no Header. Visual de "campo de busca" pra não
 *  confundir o usuário, mas ao clicar/teclar abre a paleta (Ctrl+K). */
export function BuscaGlobal() {
  const cmd = useCommandPalette();
  return (
    <button
      type="button"
      onClick={() => cmd?.open()}
      aria-label="Buscar (Ctrl+K)"
      className={cn(
        "group relative flex h-9 w-full max-w-md items-center gap-2 rounded-md border border-border bg-surface-1 px-3 text-sm",
        "text-foreground-subtle transition-colors duration-fast",
        "hover:border-border-strong hover:bg-muted hover:text-foreground-muted",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      <Search className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span className="flex-1 text-left">Buscar processos, usuários, comandos…</span>
      <span className="ml-auto hidden items-center gap-0.5 sm:flex">
        <kbd className="inline-flex items-center rounded border border-border bg-muted px-1 py-0.5 font-mono text-[9px] text-foreground-muted">
          Ctrl
        </kbd>
        <kbd className="inline-flex items-center rounded border border-border bg-muted px-1 py-0.5 font-mono text-[9px] text-foreground-muted">
          K
        </kbd>
      </span>
    </button>
  );
}
