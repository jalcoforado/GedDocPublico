"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export interface ItemDoRanking {
  chave: string | number;
  rotulo: React.ReactNode;
  /** Valor que dimensiona a barra (a maior barra = o maior valor da lista). */
  valor: number;
  /** O valor como o usuário lê ("3d 4h", "12"). */
  valorTexto: string;
  /** Linha fina abaixo do rótulo ("14 passagens · 3 atrasos"). */
  detalhe?: React.ReactNode;
  /** Pinta a barra de alerta (ex.: unidade com atraso). */
  alerta?: boolean;
}

/**
 * Ranking em barras horizontais — "quem está no topo e por quanto".
 *
 * Lista e não gráfico de verdade de propósito: o rótulo (nome de unidade,
 * nome de pessoa) é longo e precisa ser lido inteiro, e cada linha carrega
 * um detalhe que um eixo não comporta. A barra só dá a proporção.
 *
 * Mostra `limite` itens e um botão para ver o resto — num município com
 * dezenas de unidades, a pergunta é "onde para", e a resposta está no topo.
 */
export function RankingEmBarras({
  itens,
  limite = 8,
  rotuloDoValor,
  vazio,
}: {
  itens: ItemDoRanking[];
  limite?: number;
  /** Nome do que o número mede, lido pelo leitor de tela ("tempo médio"). */
  rotuloDoValor: string;
  vazio: React.ReactNode;
}) {
  const [todos, setTodos] = React.useState(false);
  if (itens.length === 0) return <>{vazio}</>;
  const max = Math.max(...itens.map((i) => i.valor), 1);
  const visiveis = todos ? itens : itens.slice(0, limite);
  return (
    <div>
      <ol className="space-y-3">
        {visiveis.map((i, pos) => (
          <li key={i.chave} className="grid grid-cols-[1.5rem_minmax(0,1fr)_auto] items-start gap-x-3">
            <span className="pt-0.5 text-right text-xs font-medium tabular-nums text-muted-foreground">
              {pos + 1}
            </span>
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-foreground">{i.rotulo}</div>
              <div
                className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted"
                role="presentation"
              >
                <div
                  className={cn("h-full rounded-full", i.alerta ? "bg-danger" : "bg-primary")}
                  style={{ width: `${Math.max(2, (i.valor / max) * 100)}%` }}
                />
              </div>
              {i.detalhe && (
                <div className="mt-1 text-xs text-muted-foreground">{i.detalhe}</div>
              )}
            </div>
            <span className="pt-0.5 text-sm font-semibold tabular-nums text-foreground">
              <span className="sr-only">{rotuloDoValor}: </span>
              {i.valorTexto}
            </span>
          </li>
        ))}
      </ol>
      {itens.length > limite && (
        <button
          type="button"
          onClick={() => setTodos((t) => !t)}
          className="mt-4 text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
        >
          {todos ? "Mostrar só os primeiros" : `Ver todos os ${itens.length}`}
        </button>
      )}
    </div>
  );
}
