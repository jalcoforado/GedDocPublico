"use client";

import { BarChart3, Lightbulb } from "lucide-react";
import type { ReactNode } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { cn } from "@/lib/utils";

/**
 * Moldura canônica de gráfico: cabeçalho, corpo e **rodapé de leitura**.
 *
 * Padrão trazido do DS V2 do ianalisys (`shell/components/ui/chart-card.tsx`),
 * reescrito nos tokens do Aprimora. O que foi portado é a ANATOMIA, não a
 * identidade visual: o Aprimora é white-label e cada prefeitura troca as
 * cores (ver `lib/chart-theme.ts`), então cravar a paleta de uma marca aqui
 * marcaria todo município com a identidade de outra empresa e quebraria o
 * tema escuro.
 *
 * O rodapé `insight` é a parte que muda a tela de "dado" para "leitura": um
 * gráfico que não diz o que significa transfere ao leitor o trabalho de
 * interpretar — e em painel de gestão é justamente aí que cada um lê uma
 * coisa. O texto precisa sair do PRÓPRIO dado (uma concentração, uma
 * proporção, uma ausência); frase genérica é pior que rodapé nenhum, porque
 * ocupa o lugar onde o leitor espera informação.
 */
export function GraficoCard({
  titulo,
  subtitulo,
  acao,
  insight,
  vazio,
  vazioTitulo = "Sem dados no período",
  vazioDescricao = "Tente um período maior ou outros filtros.",
  children,
  className,
}: {
  titulo: string;
  /** Contexto curto: período, medida, dica de interação. */
  subtitulo?: ReactNode;
  /** Slot à direita do cabeçalho — ordenação, filtro, link. */
  acao?: ReactNode;
  /** Leitura curta do que o gráfico mostra. Derive do dado; não escreva frase pronta. */
  insight?: ReactNode;
  vazio?: boolean;
  vazioTitulo?: string;
  vazioDescricao?: string;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "overflow-hidden rounded-card border border-border bg-surface-1 shadow-card",
        "transition-shadow duration-base hover:shadow-card-hover",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3 px-5 pb-3 pt-4">
        <div className="min-w-0 flex-1">
          <h3 className="font-display text-base font-semibold leading-tight text-foreground">
            {titulo}
          </h3>
          {subtitulo && (
            <p className="mt-0.5 text-xs leading-relaxed text-foreground-subtle">{subtitulo}</p>
          )}
        </div>
        {acao && <div className="shrink-0">{acao}</div>}
      </div>

      <div className="px-5 pb-4">
        {vazio ? (
          <EmptyState icon={BarChart3} title={vazioTitulo} description={vazioDescricao} />
        ) : (
          children
        )}
      </div>

      {insight && !vazio && (
        <div className="flex items-start gap-2 border-t border-border bg-surface-2/40 px-5 py-3">
          <Lightbulb
            className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning-soft-foreground"
            aria-hidden="true"
          />
          <p className="text-xs leading-relaxed text-foreground-muted">{insight}</p>
        </div>
      )}
    </section>
  );
}
