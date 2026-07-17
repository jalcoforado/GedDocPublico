import * as React from "react";

import { cn } from "@/lib/utils";

interface FilterBarProps {
  children: React.ReactNode;
  className?: string;
  /** ARIA label/description da barra; default "Filtros". */
  ariaLabel?: string;
}

interface FilterBarGroupProps {
  /** Label opcional acima do controle, em microcaps. */
  label?: string;
  /** Slot do controle (Select, Combobox, segmented…). */
  children: React.ReactNode;
  /** className extra. */
  className?: string;
}

interface FilterBarActionsProps {
  children: React.ReactNode;
  className?: string;
}

/**
 * Barra de filtros responsiva. Sem lógica — só layout. Substitui o
 * padrão de jogar 4-5 controles dentro do `actions` do PageHeader,
 * que vira lista vertical em telas menores e empurra o conteúdo
 * para fora da dobra.
 *
 * Uso típico:
 * ```tsx
 * <FilterBar>
 *   <FilterBar.Group label="Unidade"><UnidadePicker … /></FilterBar.Group>
 *   <FilterBar.Group label="Período"><Segmented … /></FilterBar.Group>
 *   <FilterBar.Actions><Button>Exportar</Button></FilterBar.Actions>
 * </FilterBar>
 * ```
 */
export function FilterBar({ children, className, ariaLabel }: FilterBarProps) {
  return (
    <div
      role="region"
      aria-label={ariaLabel ?? "Filtros"}
      className={cn(
        "flex flex-wrap items-end gap-3 rounded-card border border-border bg-surface-1 p-3 shadow-xs",
        className,
      )}
    >
      {children}
    </div>
  );
}

function FilterBarGroup({ label, children, className }: FilterBarGroupProps) {
  return (
    <div className={cn("min-w-0", className)}>
      {label && (
        <div className="mb-1 text-xs uppercase tracking-wide text-foreground-subtle">
          {label}
        </div>
      )}
      {children}
    </div>
  );
}

function FilterBarActions({ children, className }: FilterBarActionsProps) {
  return (
    <div className={cn("ml-auto flex items-end gap-2", className)}>
      {children}
    </div>
  );
}

FilterBar.Group = FilterBarGroup;
FilterBar.Actions = FilterBarActions;
