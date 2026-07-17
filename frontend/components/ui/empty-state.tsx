import { LucideIcon } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: React.ReactNode;
  /** Slot pra botões de ação (ex: "Criar primeiro X"). */
  action?: React.ReactNode;
  className?: string;
}

/**
 * Empty state padronizado pra listas vazias. Inclui ícone grande sutil,
 * título + descrição, e slot pra ação primária. Mais identitário que
 * "Nenhum registro" jogado num <td>.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-card border border-dashed border-border bg-surface-1 p-10 text-center",
        className,
      )}
    >
      {Icon && (
        <div
          aria-hidden="true"
          className="
            relative inline-flex h-14 w-14 items-center justify-center rounded-full
            bg-gradient-to-br from-brand/10 via-brand/5 to-accent/10
            text-brand dark:text-brand-light
          "
        >
          <Icon className="h-7 w-7" aria-hidden="true" />
        </div>
      )}
      <div className="max-w-md space-y-1">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        {description && (
          <p className="text-sm text-foreground-muted">{description}</p>
        )}
      </div>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
