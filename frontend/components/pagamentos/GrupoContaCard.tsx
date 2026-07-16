"use client";

import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

import { fmtMoeda } from "./format";

interface GrupoContaCardProps {
  nomeConta: string;
  disponivel: string;
  abaixoMinimo?: boolean;
  /** Soma (número) dos itens selecionados deste grupo — 0 esconde o bloco "Σ selecionado". */
  somaSelecionada: number;
  groupChecked: boolean;
  onToggleGroup: () => void;
  toggleGroupDisabled?: boolean;
  children: ReactNode;
  className?: string;
}

/**
 * Card de grupo por conta, compartilhado pelas tabs Despesa/Pagamento da tela
 * de Autorizações: cabeçalho com nome da conta, disponível em destaque, Σ
 * selecionado ao vivo e barra fina de consumo (verde/âmbar/vermelho). Os
 * children são as linhas (fornecedor/valor/etc.), que variam por tab.
 */
export function GrupoContaCard({
  nomeConta,
  disponivel,
  abaixoMinimo,
  somaSelecionada,
  groupChecked,
  onToggleGroup,
  toggleGroupDisabled,
  children,
  className,
}: GrupoContaCardProps) {
  const disponivelNum = Number(disponivel) || 0;
  const pct =
    disponivelNum > 0
      ? (somaSelecionada / disponivelNum) * 100
      : somaSelecionada > 0
        ? 100
        : 0;
  const excede = pct > 100;
  const alerta = pct >= 80;

  const barColor = excede ? "bg-danger" : alerta ? "bg-warning" : "bg-success";

  return (
    <div className={cn("overflow-hidden rounded-lg border border-border bg-surface-1", className)}>
      <div className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
        <Checkbox
          checked={groupChecked}
          onChange={onToggleGroup}
          disabled={toggleGroupDisabled}
          aria-label={`Selecionar todos os itens de ${nomeConta}`}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <p className="truncate font-semibold text-foreground" title={nomeConta}>
              {nomeConta}
            </p>
            {abaixoMinimo && <Badge intent="warning">Abaixo do mínimo</Badge>}
          </div>
          <div className="mt-1.5 h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full", barColor)}
              style={{ width: `${Math.min(pct, 100)}%` }}
            />
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className="text-xs text-muted-foreground">Disponível</p>
          <p className="whitespace-nowrap text-base font-semibold tabular-nums text-foreground">
            {fmtMoeda(disponivel)}
          </p>
        </div>
        {somaSelecionada > 0 && (
          <div className="shrink-0 text-right">
            <p className="text-xs text-muted-foreground">Σ selecionado</p>
            <p
              className={cn(
                "whitespace-nowrap text-sm font-semibold tabular-nums",
                excede ? "text-danger-soft-foreground" : "text-foreground",
              )}
            >
              {fmtMoeda(somaSelecionada)}
            </p>
          </div>
        )}
      </div>
      <div className="divide-y divide-border">{children}</div>
    </div>
  );
}
