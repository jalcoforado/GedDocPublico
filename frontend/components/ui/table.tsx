"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

interface TableProps extends React.TableHTMLAttributes<HTMLTableElement> {
  /** Cards-like (default) — borda + radius + bg-surface-1.
   *  flat — sem borda externa, pra usar dentro de outros containers. */
  variant?: "card" | "flat";
}

export function Table({ className, variant = "card", ...props }: TableProps) {
  if (variant === "flat") {
    return (
      <div className="overflow-x-auto">
        <table className={cn("w-full text-sm", className)} {...props} />
      </div>
    );
  }
  return (
    <div className="overflow-hidden overflow-x-auto rounded-table border border-border bg-surface-1 shadow-table">
      <table className={cn("w-full text-sm", className)} {...props} />
    </div>
  );
}

export function THead(props: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className="sticky top-0 z-[1] bg-surface-2/95 text-left text-xs font-semibold uppercase tracking-wide text-foreground-muted shadow-table-header backdrop-blur-sm"
      {...props}
    />
  );
}

export function TBody(props: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <tbody
      className="divide-y divide-border [&>tr:nth-child(even)]:bg-surface-2/30"
      {...props}
    />
  );
}

interface TRProps extends React.HTMLAttributes<HTMLTableRowElement> {
  /** Linha destacada (ex: selecionada, atual). */
  highlighted?: boolean;
  /** Click handler — adiciona cursor-pointer */
  onClickRow?: () => void;
}

export function TR({ className, highlighted, onClickRow, onClick, ...props }: TRProps) {
  const handleClick = onClick || (onClickRow ? () => onClickRow() : undefined);
  return (
    <tr
      onClick={handleClick}
      // Linha clicável é operável por teclado (fatia 2.7): entra no Tab e
      // ativa com Enter/Espaço — antes era mouse-only.
      tabIndex={handleClick ? 0 : undefined}
      onKeyDown={
        handleClick
          ? (e) => {
              if (e.target !== e.currentTarget) return; // controles internos seguem seus próprios atalhos
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleClick(e as unknown as React.MouseEvent<HTMLTableRowElement>);
              }
            }
          : undefined
      }
      className={cn(
        "min-h-[var(--table-row-h)] transition-colors duration-fast",
        "hover:bg-surface-2",
        highlighted && "bg-brand/5 hover:bg-brand/10 dark:bg-brand/15 dark:hover:bg-brand/20",
        handleClick &&
          "cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
        className,
      )}
      {...props}
    />
  );
}

interface THProps extends React.ThHTMLAttributes<HTMLTableCellElement> {
  /** Coluna ordenável. */
  sortable?: boolean;
  /** Estado atual de ordenação dessa coluna. */
  sortState?: "asc" | "desc" | null;
  onSortToggle?: () => void;
}

export function TH({
  className,
  sortable,
  sortState,
  onSortToggle,
  children,
  ...props
}: THProps) {
  // density-aware padding via CSS var
  const pad = "py-[var(--density-pad-y)] px-[var(--density-pad-x)]";
  if (!sortable) {
    return (
      <th className={cn(pad, className)} {...props}>
        {children}
      </th>
    );
  }
  const Icon =
    sortState === "asc"
      ? ArrowUp
      : sortState === "desc"
        ? ArrowDown
        : ArrowUpDown;
  return (
    <th
      // aria-sort pertence ao th (fatia 2.7) — no botão interno, leitor de
      // tela não o associava à coluna.
      aria-sort={
        sortState === "asc" ? "ascending" : sortState === "desc" ? "descending" : "none"
      }
      className={cn(pad, "p-0", className)}
      {...props}
    >
      <button
        type="button"
        onClick={onSortToggle}
        className={cn(
          "flex w-full items-center gap-1 text-left",
          pad,
          "transition-colors duration-fast hover:bg-muted/60 hover:text-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
          sortState && "text-foreground",
        )}
      >
        <span>{children}</span>
        <Icon
          className={cn(
            "h-3 w-3 shrink-0 transition-opacity",
            sortState ? "opacity-100 text-brand" : "opacity-40",
          )}
          aria-hidden="true"
        />
      </button>
    </th>
  );
}

export function TD({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      className={cn("py-[var(--density-pad-y)] px-[var(--density-pad-x)]", className)}
      {...props}
    />
  );
}

interface SkeletonRowProps {
  /** Número de colunas da tabela — uma célula skeleton por coluna. */
  cols: number;
  className?: string;
}

/**
 * Linha de carregamento (fatia 2.7): mesma altura da linha real (token
 * `--density-row-h`, respeita o modo compacto) para a tabela não "pular"
 * quando os dados chegam. `aria-hidden`: esqueleto é acabamento visual,
 * não conteúdo.
 */
export function SkeletonRow({ cols, className }: SkeletonRowProps) {
  return (
    <tr aria-hidden="true" className={cn("h-[var(--density-row-h)]", className)}>
      {Array.from({ length: cols }, (_, i) => (
        <TD key={i}>
          <div className="h-3 w-full max-w-[10rem] animate-pulse rounded bg-surface-3" />
        </TD>
      ))}
    </tr>
  );
}
