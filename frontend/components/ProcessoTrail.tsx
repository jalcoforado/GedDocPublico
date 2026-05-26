"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Building2, Clock, MapPin, XCircle } from "lucide-react";

import { processosApi, type TrailStep } from "@/lib/api";
import { cn } from "@/lib/utils";

function fmtData(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

function StepCard({ step }: { step: TrailStep }) {
  return (
    <div
      className={cn(
        "min-w-[140px] flex-shrink-0 rounded-md border px-3 py-2 text-xs",
        step.atual
          ? "border-primary bg-primary/10"
          : step.cancelado
            ? "border-dashed border-muted-foreground bg-muted/40 opacity-60"
            : "border-border bg-card",
      )}
      title={
        step.cancelado
          ? "Encaminhamento cancelado"
          : step.atual
            ? "Localização atual"
            : "Visitado"
      }
    >
      <div className="flex items-center gap-1">
        <Building2
          className={cn(
            "h-3.5 w-3.5 shrink-0",
            step.atual ? "text-primary" : "text-muted-foreground",
          )}
          aria-hidden="true"
        />
        <span className="truncate font-semibold">
          {step.unidade_sigla ?? step.unidade_nome}
        </span>
        {step.cancelado && (
          <XCircle className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
        )}
      </div>
      {step.unidade_sigla && (
        <div className="truncate text-[10px] text-muted-foreground">
          {step.unidade_nome}
        </div>
      )}
      <div className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground">
        <Clock className="h-3 w-3" aria-hidden="true" />
        <span className="tabular-nums">{fmtData(step.data)}</span>
      </div>
      {step.atual && (
        <div className="mt-1 inline-flex items-center gap-1 rounded bg-primary/20 px-1.5 py-0.5 text-[10px] font-medium text-primary">
          <MapPin className="h-3 w-3" aria-hidden="true" />
          ATUAL
        </div>
      )}
    </div>
  );
}

export function ProcessoTrail({ processoId }: { processoId: number }) {
  const q = useQuery({
    queryKey: ["processo-trail", processoId],
    queryFn: () => processosApi.trail(processoId),
  });

  if (q.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando trajeto…</p>;
  }
  if (q.error) {
    return (
      <p className="text-sm text-danger-soft-foreground">
        Erro: {(q.error as Error).message}
      </p>
    );
  }
  const steps = q.data ?? [];
  if (steps.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">Sem trajeto registrado.</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <div className="flex items-center gap-2 pb-2">
        {steps.map((step, i) => (
          <div key={step.ordem} className="flex items-center gap-2">
            <StepCard step={step} />
            {i < steps.length - 1 && (
              <ArrowRight
                className="h-4 w-4 shrink-0 text-muted-foreground"
                aria-hidden="true"
              />
            )}
          </div>
        ))}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {steps.length} {steps.length === 1 ? "passo" : "passos"} no trajeto · setas
        seguem a ordem cronológica.
      </p>
    </div>
  );
}
