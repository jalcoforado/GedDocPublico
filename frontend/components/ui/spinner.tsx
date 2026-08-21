import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

interface SpinnerProps {
  /** Anunciado a leitores de tela; não aparece visualmente. */
  label?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

const SIZES = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-8 w-8",
};

/**
 * Indicador de carregamento (UX-02 fatia 2.5) — o substituto padrão do
 * "Carregando…" textual. `role="status"` anuncia o rótulo uma vez sem
 * poluir a tela.
 */
export function Spinner({ label = "Carregando", size = "md", className }: SpinnerProps) {
  return (
    <span role="status" aria-label={label} className={cn("inline-flex", className)}>
      <Loader2 className={cn("animate-spin text-foreground-muted", SIZES[size])} aria-hidden="true" />
    </span>
  );
}
