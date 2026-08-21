"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { cn } from "@/lib/utils";

interface PaginationProps {
  /** 1-based, como o Paginated<T> do backend. */
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  /** Presente → aparece o seletor de itens por página; trocar volta à página 1. */
  onPageSizeChange?: (pageSize: number) => void;
  pageSizeOptions?: number[];
  className?: string;
}

/**
 * Paginação padrão (UX-02 fatia 2.5), alinhada ao contrato Paginated<T>
 * (page/page_size/total). Anterior/Próxima + intervalo visível + page-size
 * opcional.
 */
export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
  className,
}: PaginationProps) {
  const totalPaginas = Math.max(1, Math.ceil(total / pageSize));
  const inicio = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const fim = Math.min(page * pageSize, total);
  const sizeId = React.useId();

  return (
    <nav
      aria-label="Paginação"
      className={cn("flex flex-wrap items-center justify-between gap-3 text-sm", className)}
    >
      <span className="tabular-nums text-foreground-muted">
        {total === 0 ? "0 de 0" : `${inicio}–${fim} de ${total}`}
      </span>
      <div className="flex items-center gap-3">
        {onPageSizeChange && (
          <label htmlFor={sizeId} className="flex items-center gap-2 text-foreground-muted">
            Por página
            <Select
              id={sizeId}
              value={String(pageSize)}
              onChange={(e) => {
                onPageSizeChange(Number(e.target.value));
                onPageChange(1);
              }}
              className="h-9 w-auto py-1 text-sm"
            >
              {pageSizeOptions.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </Select>
          </label>
        )}
        <div className="flex items-center gap-1">
          <Button
            variant="secondary"
            size="sm"
            aria-label="Página anterior"
            disabled={total === 0 || page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            Anterior
          </Button>
          <Button
            variant="secondary"
            size="sm"
            aria-label="Próxima página"
            disabled={total === 0 || page >= totalPaginas}
            onClick={() => onPageChange(page + 1)}
          >
            Próxima
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        </div>
      </div>
    </nav>
  );
}
