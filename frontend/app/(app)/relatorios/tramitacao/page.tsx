"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronDown, ChevronUp, Download, FileText } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { RelatoriosNav } from "@/components/RelatoriosNav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  api,
  tramitacaoCsvUrl,
  tramitacaoPdfUrl,
  type RelatorioFiltroInput,
  type TramitacaoEtapa,
  type TramitacaoProcesso,
} from "@/lib/api";

function fmtDateTime(s: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

function fmtDate(s: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("pt-BR");
}

function fmtMin(m: number | null): string {
  if (m === null || m === undefined) return "—";
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  if (h < 24) return `${h}h ${String(rem).padStart(2, "0")}min`;
  const d = Math.floor(h / 24);
  const rh = h % 24;
  return `${d}d ${rh}h`;
}

export default function RelatorioTramitacaoPage() {
  const router = useRouter();
  const toast = useToast();
  const [draft, setDraft] = useState<RelatorioFiltroInput>({});
  const [applied, setApplied] = useState<RelatorioFiltroInput>({});

  const gerarBg = useMutation({
    mutationFn: () => api.jobs.relatorioTramitacao(applied),
    onSuccess: () => {
      toast.success("Relatório enfileirado em background.");
      router.push("/jobs");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const tiposQ = useQuery({
    queryKey: ["tipos-processo"],
    queryFn: () => api.tiposProcesso.list(),
  });

  const relQ = useQuery({
    queryKey: ["relatorio-tramitacao", applied],
    queryFn: () => api.relatorios.tramitacao(applied),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-primary">Relatórios</h1>
      <RelatoriosNav />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold text-foreground">
          Tramitação (tempo em cada unidade + atrasos)
        </h2>
        <div className="flex flex-wrap gap-2">
          <a
            href={tramitacaoCsvUrl(applied)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-muted px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Download className="h-4 w-4" aria-hidden="true" /> CSV
          </a>
          <a
            href={tramitacaoPdfUrl(applied)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground transition-colors hover:bg-aprimora-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <FileText className="h-4 w-4" aria-hidden="true" /> PDF
          </a>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => gerarBg.mutate()}
            disabled={gerarBg.isPending}
            title="Gera o PDF em background — útil para recortes grandes"
          >
            {gerarBg.isPending ? "Enfileirando..." : "Gerar em background"}
          </Button>
        </div>
      </div>

      <Card>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <div>
              <Label htmlFor="unidade">Unidade</Label>
              <Select
                id="unidade"
                value={draft.id_unidade ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    id_unidade: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              >
                <option value="">Todas</option>
                {unidadesQ.data?.items.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.unidade_trabalho}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="tipo">Tipo de processo</Label>
              <Select
                id="tipo"
                value={draft.id_tipo_processo ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    id_tipo_processo: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              >
                <option value="">Todos</option>
                {tiposQ.data?.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.tipo_processo}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="desde">Aberto desde</Label>
              <Input
                id="desde"
                type="date"
                value={draft.desde?.slice(0, 10) ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    desde: e.target.value ? `${e.target.value}T00:00:00` : undefined,
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="ate">Aberto até</Label>
              <Input
                id="ate"
                type="date"
                value={draft.ate?.slice(0, 10) ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    ate: e.target.value ? `${e.target.value}T23:59:59` : undefined,
                  })
                }
              />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="ativos"
                checked={!!draft.apenas_ativos}
                onChange={(e) => setDraft({ ...draft, apenas_ativos: e.target.checked })}
              />
              <Label htmlFor="ativos" className="!mb-0">
                Apenas ativos
              </Label>
            </div>
            <div className="md:col-span-3 flex items-end gap-2">
              <Button onClick={() => setApplied({ ...draft })}>Gerar relatório</Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setDraft({});
                  setApplied({});
                }}
              >
                Limpar
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {relQ.isLoading && <p className="text-sm text-muted-foreground">Carregando...</p>}
      {relQ.error && (
        <div
          role="alert"
          className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
        >
          {relQ.error instanceof Error ? relQ.error.message : "Erro ao gerar relatório"}
        </div>
      )}

      {relQ.data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <StatCard label="Processos" value={String(relQ.data.qtd_processos)} />
            <StatCard
              label="Com atraso"
              value={String(relQ.data.qtd_processos_com_atraso)}
              danger={relQ.data.qtd_processos_com_atraso > 0}
            />
            <StatCard
              label="Tempo médio por processo"
              value={fmtMin(relQ.data.minutos_medio_por_processo)}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Tempo por unidade</CardTitle>
            </CardHeader>
            <CardContent>
              {relQ.data.por_unidade.length === 0 ? (
                <p className="text-sm text-muted-foreground">Sem dados.</p>
              ) : (
                <Table>
                  <THead>
                    <TR>
                      <TH>Unidade</TH>
                      <TH className="text-right">Passagens</TH>
                      <TH className="text-right">Atrasos</TH>
                      <TH className="text-right">Tempo total</TH>
                      <TH className="text-right">Tempo médio</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {relQ.data.por_unidade.map((u, i) => (
                      <TR key={`${u.id_unidade ?? "null"}-${i}`}>
                        <TD>{u.unidade ?? "—"}</TD>
                        <TD className="text-right tabular-nums">{u.qtd_passagens}</TD>
                        <TD className="text-right tabular-nums">
                          {u.qtd_atrasos > 0 ? (
                            <span className="font-semibold text-danger">{u.qtd_atrasos}</span>
                          ) : (
                            u.qtd_atrasos
                          )}
                        </TD>
                        <TD className="text-right tabular-nums">{fmtMin(u.minutos_total)}</TD>
                        <TD className="text-right tabular-nums">{fmtMin(u.minutos_medio)}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Processos ({relQ.data.processos.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {relQ.data.processos.length === 0 ? (
                <p className="text-sm text-muted-foreground">Nenhum processo no recorte.</p>
              ) : (
                <div className="space-y-3">
                  {relQ.data.processos.map((p) => (
                    <ProcessoTramitacaoCard key={p.id} p={p} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  danger = false,
}: {
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <div className="rounded-md border border-border bg-card p-3 text-center">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className={"text-xl font-bold tabular-nums " + (danger ? "text-danger" : "text-primary")}
      >
        {value}
      </div>
    </div>
  );
}

function ProcessoTramitacaoCard({ p }: { p: TramitacaoProcesso }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-border bg-card">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/processos/${p.id}`}
              onClick={(e) => e.stopPropagation()}
              className="font-mono text-sm text-primary hover:underline"
            >
              {p.numero_processo}
            </Link>
            {p.teve_atraso && (
              <Badge intent="danger" icon={AlertTriangle}>
                {p.qtd_atrasos} atraso(s)
              </Badge>
            )}
            {!p.ativo && <Badge intent="neutral">Inativo</Badge>}
          </div>
          <div className="text-xs text-muted-foreground">
            {p.manifestante ?? "—"} · {p.assunto ?? "—"}
          </div>
        </div>
        <div className="hidden gap-6 text-xs text-muted-foreground md:flex">
          <Stat label="encs" value={String(p.qtd_encaminhamentos)} />
          <Stat label="unidades" value={String(p.qtd_unidades_visitadas)} />
          <Stat label="total" value={fmtMin(p.minutos_total)} />
          <Stat
            label="em aberto"
            value={p.minutos_em_andamento > 0 ? fmtMin(p.minutos_em_andamento) : "—"}
          />
          <Stat label="local" value={p.local_atual ?? "—"} />
        </div>
        {open ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        )}
      </button>
      {open && p.etapas.length > 0 && (
        <div className="border-t border-border px-4 py-3">
          <EtapasTimeline etapas={p.etapas} />
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-center">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="font-medium text-foreground tabular-nums">{value}</div>
    </div>
  );
}

function EtapasTimeline({ etapas }: { etapas: TramitacaoEtapa[] }) {
  return (
    <div className="space-y-2">
      {etapas.map((e, i) => (
        <div
          key={i}
          className={
            "rounded border-l-2 pl-3 py-1 " +
            (e.atrasou
              ? "border-danger bg-danger-soft"
              : e.saiu_em === null
              ? "border-success bg-success-soft"
              : "border-border bg-muted")
          }
        >
          <div className="flex items-baseline justify-between">
            <span className="font-medium text-foreground">{e.unidade ?? "—"}</span>
            <span className="text-xs text-muted-foreground">
              {e.minutos_no_local !== null
                ? fmtMin(e.minutos_no_local)
                : e.saiu_em === null
                ? "em andamento"
                : "—"}
            </span>
          </div>
          <div className="grid grid-cols-1 gap-x-4 text-xs text-muted-foreground md:grid-cols-3">
            <span>chegou: {fmtDateTime(e.chegou_em)}</span>
            <span>saiu: {fmtDateTime(e.saiu_em)}</span>
            <span>
              prazo: {fmtDate(e.prazo_estipulado)}
              {e.atrasou && (
                <span className="ml-1 font-semibold text-danger">ATRASO</span>
              )}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
