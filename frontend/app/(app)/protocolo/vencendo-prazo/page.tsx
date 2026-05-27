"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Archive, CalendarClock, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { temporalidadeApi, type Temporalidade } from "@/lib/api";

function fmtDate(s: string | null) {
  if (!s) return "—";
  try {
    return new Date(s + "T00:00:00").toLocaleDateString("pt-BR");
  } catch {
    return s;
  }
}

function diasAteFim(fim: string | null): number | null {
  if (!fim) return null;
  const d = new Date(fim + "T00:00:00").getTime();
  return Math.round((d - Date.now()) / (1000 * 60 * 60 * 24));
}

export default function VencendoPrazoPage() {
  const [dias, setDias] = useState(365);
  const [incluirPermanentes, setIncluirPermanentes] = useState(false);

  const reportQ = useQuery({
    queryKey: ["vencendo-prazo", { dias, incluir_permanentes: incluirPermanentes }],
    queryFn: () =>
      temporalidadeApi.vencendoPrazo({
        dias,
        incluir_permanentes: incluirPermanentes,
      }),
  });

  const items: Temporalidade[] = reportQ.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        icon={CalendarClock}
        title="Processos vencendo prazo de guarda"
        description="Lista os processos cuja fase intermediária da temporalidade documental termina dentro da janela escolhida. Use pra planejar eliminação ou transferência ao arquivo permanente."
      />

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-card p-4 shadow-xs">
        <div className="w-44">
          <Label htmlFor="dias-select" className="text-xs">
            Janela
          </Label>
          <Select
            id="dias-select"
            value={dias}
            onChange={(e) => setDias(Number(e.target.value))}
          >
            <option value={180}>Próximos 6 meses</option>
            <option value={365}>Próximos 12 meses</option>
            <option value={730}>Próximos 2 anos</option>
            <option value={1825}>Próximos 5 anos</option>
            <option value={3650}>Próximos 10 anos</option>
          </Select>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={incluirPermanentes}
            onChange={(e) => setIncluirPermanentes(e.target.checked)}
            className="h-4 w-4 accent-brand"
          />
          Incluir destino &ldquo;Guarda permanente&rdquo;
        </label>
        <div className="ml-auto text-sm text-foreground-muted">
          {reportQ.isLoading ? (
            <Loader2 className="inline h-4 w-4 animate-spin" />
          ) : (
            <span>
              <strong className="text-foreground">{items.length}</strong>{" "}
              processo{items.length === 1 ? "" : "s"} na janela
            </span>
          )}
        </div>
      </div>

      <section className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
        {reportQ.isLoading && (
          <div className="p-6 text-sm text-foreground-muted">
            <Loader2 className="mr-1 inline h-4 w-4 animate-spin" /> Calculando
            temporalidades…
          </div>
        )}
        {!reportQ.isLoading && items.length === 0 && (
          <EmptyState
            icon={CalendarClock}
            title="Nada vencendo na janela"
            description="Aumente o intervalo no seletor acima para ver prazos mais distantes."
            className="border-0 bg-transparent"
          />
        )}
        {items.length > 0 && (
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-left text-xs font-semibold uppercase tracking-wider text-foreground-muted">
              <tr>
                <th className="px-3 py-2">Processo</th>
                <th className="px-3 py-2">Classe CCD</th>
                <th className="px-3 py-2">Fim fase corrente</th>
                <th className="px-3 py-2">Fim fase intermediária</th>
                <th className="px-3 py-2">Restantes</th>
                <th className="px-3 py-2">Destino</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {items.map((t) => {
                const restantes = diasAteFim(t.fim_fase_intermediaria);
                const urgent = restantes !== null && restantes < 365;
                return (
                  <tr key={t.id_processo} className="hover:bg-surface-2">
                    <td className="px-3 py-2">
                      <Link
                        href={`/processos/${t.id_processo}`}
                        className="font-mono font-semibold text-primary hover:underline"
                      >
                        {t.numero_processo}
                      </Link>
                    </td>
                    <td className="px-3 py-2">
                      {t.classe_codigo && (
                        <span className="mr-1 rounded bg-surface-3 px-1.5 py-0.5 font-mono text-xs text-foreground-muted">
                          {t.classe_codigo}
                        </span>
                      )}
                      {t.classe_nome ?? "—"}
                    </td>
                    <td className="px-3 py-2 text-foreground-muted">
                      {fmtDate(t.fim_fase_corrente)}
                    </td>
                    <td className="px-3 py-2">{fmtDate(t.fim_fase_intermediaria)}</td>
                    <td className="px-3 py-2">
                      {restantes === null ? (
                        "—"
                      ) : (
                        <span
                          className={
                            urgent
                              ? "font-semibold text-warning"
                              : "text-foreground-muted"
                          }
                        >
                          {restantes < 0
                            ? `vencido há ${-restantes}d`
                            : `${restantes}d`}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {t.destino_final === "GUARDA_PERMANENTE" ? (
                        <Badge intent="success" icon={Archive}>
                          Guarda permanente
                        </Badge>
                      ) : (
                        <Badge intent="warning" icon={AlertTriangle}>
                          Eliminação
                        </Badge>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      {items.length > 0 && (
        <p className="text-xs text-foreground-muted">
          Cálculo aproximado (1 ano = 365d) a partir de{" "}
          <code>data_recepcao</code> ou <code>data_hora_abertura</code> do processo.
          Para arquivamento real, validar com o arquivista da unidade.
        </p>
      )}
    </div>
  );
}
