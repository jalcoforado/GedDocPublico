"use client";

import { Check, CircleAlert } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export interface EtapaRoteiro {
  /** Id da `SectionCard` da etapa (âncora). */
  id: string;
  titulo: string;
  /** Campos obrigatórios da etapa que ainda faltam: rótulo + id do controle. */
  faltando: { rotulo: string; campoId: string }[];
  /** Etapa só com campos opcionais: nunca "pendente", mas também não "feita". */
  opcional?: boolean;
}

/**
 * Formulário longo + roteiro ao lado. Em telas largas o formulário fica numa
 * coluna de leitura (≤ 48rem) e o roteiro ocupa o espaço que sobrava em
 * branco; em telas estreitas o roteiro some (a barra de ações diz o que
 * falta).
 */
export function LayoutFormulario({
  roteiro,
  children,
}: {
  roteiro?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,48rem)_15rem]">
      <div className="min-w-0 space-y-4">{children}</div>
      {roteiro && (
        <aside className="hidden xl:block">
          <div className="sticky top-24">{roteiro}</div>
        </aside>
      )}
    </div>
  );
}

function irPara(id: string, focar = false) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  if (focar) el.focus({ preventScroll: true });
}

/**
 * O mapa do formulário: as etapas com o estado de cada uma (feita ✓ ou o
 * que falta) e, embaixo, a lista do que ainda impede de enviar — cada item
 * leva ao campo. Responde "falta muito?" sem precisar rolar a tela inteira.
 */
export function RoteiroFormulario({ etapas, titulo = "Etapas" }: { etapas: EtapaRoteiro[]; titulo?: string }) {
  const obrigatorias = etapas.filter((e) => !e.opcional);
  const feitas = obrigatorias.filter((e) => e.faltando.length === 0).length;
  const pendencias = etapas.flatMap((e) => e.faltando);
  const pct = obrigatorias.length ? Math.round((feitas / obrigatorias.length) * 100) : 100;

  return (
    <nav aria-label="Roteiro do formulário" className="space-y-4 rounded-card border border-border bg-surface-1 p-4 shadow-card">
      <div>
        <div className="flex items-baseline justify-between text-xs">
          <span className="font-semibold uppercase tracking-wide text-foreground-subtle">{titulo}</span>
          <span className="tabular-nums text-foreground-muted">
            {feitas} de {obrigatorias.length}
          </span>
        </div>
        <div
          className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          aria-label="Etapas obrigatórias concluídas"
        >
          <div
            className="h-full rounded-full bg-success transition-[width] duration-slow ease-out-expo motion-reduce:transition-none"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <ol className="space-y-1">
        {etapas.map((e, i) => {
          const feita = !e.opcional && e.faltando.length === 0;
          return (
            <li key={e.id}>
              <button
                type="button"
                onClick={() => irPara(e.id)}
                className="-mx-1.5 flex w-full items-center gap-2.5 rounded-md px-1.5 py-1.5 text-left text-sm transition-colors duration-fast hover:bg-muted"
              >
                <span
                  className={cn(
                    "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold tabular-nums",
                    feita
                      ? "bg-success text-success-foreground"
                      : e.faltando.length > 0
                        ? "border border-warning bg-warning-soft text-warning-soft-foreground"
                        : "border border-border-strong text-foreground-muted",
                  )}
                  aria-hidden="true"
                >
                  {feita ? <Check className="h-3 w-3" /> : i + 1}
                </span>
                <span className={cn("min-w-0 flex-1 truncate", feita ? "text-foreground-muted" : "text-foreground")}>
                  {e.titulo}
                </span>
                <span className="sr-only">
                  {feita ? "— concluída" : e.faltando.length > 0 ? `— faltam ${e.faltando.length}` : "— opcional"}
                </span>
                {e.opcional && <span className="text-[11px] text-foreground-subtle">opcional</span>}
              </button>
            </li>
          );
        })}
      </ol>

      {pendencias.length > 0 ? (
        <div className="border-t border-border pt-3">
          <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-foreground">
            <CircleAlert className="h-3.5 w-3.5 text-warning-soft-foreground" aria-hidden="true" />
            Falta preencher
          </p>
          <ul className="space-y-0.5">
            {pendencias.map((p) => (
              <li key={p.campoId}>
                <button
                  type="button"
                  onClick={() => irPara(p.campoId, true)}
                  className="-mx-1.5 w-full rounded px-1.5 py-1 text-left text-xs text-foreground-muted underline-offset-2 transition-colors duration-fast hover:bg-muted hover:text-foreground hover:underline"
                >
                  {p.rotulo}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="flex items-center gap-1.5 border-t border-border pt-3 text-xs font-medium text-success-soft-foreground">
          <Check className="h-3.5 w-3.5" aria-hidden="true" />
          Tudo pronto para enviar.
        </p>
      )}
    </nav>
  );
}

/**
 * Texto do status da barra de ações a partir do roteiro: "Falta: Manifestante
 * e Assunto." — a versão de bolso do roteiro, que aparece também no celular.
 */
export function resumoDoQueFalta(etapas: EtapaRoteiro[]): string | null {
  const nomes = etapas.flatMap((e) => e.faltando.map((f) => f.rotulo));
  if (nomes.length === 0) return null;
  if (nomes.length === 1) return `Falta: ${nomes[0]}.`;
  if (nomes.length <= 3) return `Falta: ${nomes.slice(0, -1).join(", ")} e ${nomes.at(-1)}.`;
  return `Faltam ${nomes.length} campos obrigatórios.`;
}
