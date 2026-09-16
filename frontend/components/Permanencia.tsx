"use client";

import { Clock, Hourglass } from "lucide-react";

import type { PermanenciaNo, PermanenciaProcesso } from "@/lib/api";
import { formatarDuracao } from "@/lib/duracao";
import { cn } from "@/lib/utils";

/**
 * Exibição da permanência (F1).
 *
 * A distinção que estes componentes existem para tornar visível: **fila** é
 * tempo esperando alguém receber, **análise** é tempo com quem já recebeu.
 * São gargalos diferentes, com donos diferentes, e a soma dos dois esconde
 * qual dos dois é o problema.
 *
 * Os ícones não são decoração: a ampulheta (fila) e o relógio (análise) são o
 * que distingue os dois à distância numa lista longa, antes de o olho chegar
 * ao texto. Mas nunca aparecem sozinhos — `aria-label` e o texto visível
 * carregam o sentido, porque forma e cor não são lidas por leitor de tela nem
 * percebidas por quem não distingue as cores usadas.
 */

const ROTULO: Record<PermanenciaNo["natureza"], string> = {
  espera: "na fila",
  analise: "em análise",
  encerrado: "após o arquivamento",
};

export function PermanenciaNoBadge({
  p,
  className,
}: {
  p: PermanenciaNo;
  className?: string;
}) {
  // Trecho posterior ao arquivamento com o processo parado: o backend devolve
  // zero de propósito (ninguém está segurando nada). Exibir "0 min" só
  // ocuparia espaço afirmando o óbvio.
  if (p.natureza === "encerrado" && p.segundos === 0) return null;

  const Icone = p.natureza === "espera" ? Hourglass : Clock;
  const duracao = formatarDuracao(p.segundos);
  const texto = `${ROTULO[p.natureza]} ${duracao}${p.aberto ? " (em curso)" : ""}`;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs tabular-nums",
        p.natureza === "espera"
          ? "bg-warning-soft text-warning-soft-foreground"
          : "bg-muted text-muted-foreground",
        className,
      )}
      // O texto visível já diz tudo; o label existe para que o leitor de tela
      // não leia "ampulheta na fila 2 h" com o ícone no meio.
      aria-label={texto}
    >
      <Icone aria-hidden className="h-3 w-3 shrink-0" />
      <span aria-hidden>{texto}</span>
    </span>
  );
}

/**
 * O agregado, para o topo do processo.
 *
 * `total_ativo` vem separado de fila e análise de propósito: é a soma dos
 * dois, e mostrar os três deixa a decomposição óbvia sem obrigar ninguém a
 * fazer a conta.
 */
export function PermanenciaResumo({
  p,
  className,
}: {
  p: PermanenciaProcesso;
  className?: string;
}) {
  if (p.tramitacoes === 0 && p.total_ativo_segundos === 0) return null;

  return (
    <div
      className={cn("flex flex-wrap items-center gap-x-4 gap-y-1 text-xs", className)}
    >
      <span className="text-muted-foreground">
        Tempo ativo{" "}
        <b className="text-foreground tabular-nums">
          {formatarDuracao(p.total_ativo_segundos)}
        </b>
        {p.em_curso && <span className="text-muted-foreground"> (em curso)</span>}
      </span>
      <span className="inline-flex items-center gap-1 text-muted-foreground">
        <Hourglass aria-hidden className="h-3 w-3 shrink-0" />
        Fila{" "}
        <b className="text-foreground tabular-nums">
          {formatarDuracao(p.espera_segundos)}
        </b>
      </span>
      <span className="inline-flex items-center gap-1 text-muted-foreground">
        <Clock aria-hidden className="h-3 w-3 shrink-0" />
        Análise{" "}
        <b className="text-foreground tabular-nums">
          {formatarDuracao(p.analise_segundos)}
        </b>
      </span>
      <span className="text-muted-foreground">
        {p.tramitacoes === 1 ? "1 tramitação" : `${p.tramitacoes} tramitações`}
      </span>
    </div>
  );
}
