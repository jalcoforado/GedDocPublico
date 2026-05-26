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
    <div className="overflow-hidden overflow-x-auto rounded-lg border border-border bg-surface-1 shadow-xs">
      <table className={cn("w-full text-sm", className)} {...props} />
    </div>
  );
}

export function THead(props: React.HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className="sticky top-0 z-[1] bg-surface-2/95 text-left text-[11px] font-semibold uppercase tracking-wider text-foreground-muted backdrop-blur-sm"
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
  return (
    <tr
      onClick={onClick || (onClickRow ? () => onClickRow() : undefined)}
      className={cn(
        "transition-colors duration-fast",
        "hover:bg-muted/50",
        highlighted && "bg-brand/5 hover:bg-brand/10 dark:bg-brand/15 dark:hover:bg-brand/20",
        (onClick || onClickRow) && "cursor-pointer",
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
    <th className={cn(pad, "p-0", className)} {...props}>
      <button
        type="button"
        onClick={onSortToggle}
        aria-sort={
          sortState === "asc" ? "ascending" : sortState === "desc" ? "descending" : "none"
        }
        className={cn(
          "flex w-full items-center gap-1 text-left",
          pad,
          "transition-colors duration-fast hover:text-foreground",
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
