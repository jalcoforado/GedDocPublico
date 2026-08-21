import { AlertCircle, AlertTriangle, CheckCircle2, Info } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

type Intent = "info" | "success" | "warning" | "danger";

interface AlertProps {
  intent?: Intent;
  /** Linha de título em negrito acima do corpo. */
  title?: string;
  children: React.ReactNode;
  className?: string;
}

const ICONS: Record<Intent, React.ComponentType<{ className?: string }>> = {
  info: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: AlertCircle,
};

const STYLES: Record<Intent, string> = {
  info: "bg-info-soft text-info-soft-foreground border-info/30",
  success: "bg-success-soft text-success-soft-foreground border-success/30",
  warning: "bg-warning-soft text-warning-soft-foreground border-warning/30",
  danger: "bg-danger-soft text-danger-soft-foreground border-danger/30",
};

/**
 * Alerta inline (UX-02 fatia 2.5) — substitui as variantes manuais de
 * "caixinha colorida" espalhadas pelas telas. `danger` é `role="alert"`
 * (anúncio imediato em leitor de tela); os demais são conteúdo estático —
 * live region em aviso informativo só gera ruído.
 */
export function Alert({ intent = "info", title, children, className }: AlertProps) {
  const Icon = ICONS[intent];
  return (
    <div
      data-intent={intent}
      role={intent === "danger" ? "alert" : undefined}
      className={cn(
        "flex items-start gap-3 rounded-lg border px-4 py-3 text-sm",
        STYLES[intent],
        className,
      )}
    >
      <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        <div className={cn(title && "mt-0.5")}>{children}</div>
      </div>
    </div>
  );
}
