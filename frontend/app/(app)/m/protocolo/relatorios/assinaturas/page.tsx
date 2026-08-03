"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, Download, FileText, XCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { RelatoriosNav } from "@/components/RelatoriosNav";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import {
  api,
  assinaturasCsvUrl,
  assinaturasPdfUrl,
  type AssinaturasFiltroInput,
  type StatusSolicitacaoAssin,
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

function statusBadge(status: StatusSolicitacaoAssin) {
  switch (status) {
    case "pendente":
      return (
        <Badge intent="warning" icon={Clock}>
          Pendente
        </Badge>
      );
    case "concluida":
      return (
        <Badge intent="success" icon={CheckCircle2}>
          Concluída
        </Badge>
      );
    case "cancelada":
      return (
        <Badge intent="neutral" icon={XCircle}>
          Cancelada
        </Badge>
      );
  }
}

export default function RelatorioAssinaturasPage() {
  const [draft, setDraft] = useState<AssinaturasFiltroInput>({});
  const [applied, setApplied] = useState<AssinaturasFiltroInput>({});

  const usuariosQ = useQuery({
    queryKey: ["usuarios-list-relatorio"],
    queryFn: () => api.usuarios.list({ page_size: 200 }),
  });

  const relQ = useQuery({
    queryKey: ["relatorio-assinaturas", applied],
    queryFn: () => api.relatorios.assinaturas(applied),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-primary">Relatórios</h1>
      <RelatoriosNav />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold text-foreground">
          Assinaturas — pendências, conclusões e tempo
        </h2>
        <div className="flex flex-wrap gap-2">
          <a
            href={assinaturasCsvUrl(applied)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-muted px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Download className="h-4 w-4" aria-hidden="true" /> CSV
          </a>
          <a
            href={assinaturasPdfUrl(applied)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground transition-colors hover:bg-aprimora-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <FileText className="h-4 w-4" aria-hidden="true" /> PDF
          </a>
        </div>
      </div>

      <Card>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <div>
              <Label htmlFor="status">Status</Label>
              <Select
                id="status"
                value={draft.status ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    status: e.target.value
                      ? (e.target.value as StatusSolicitacaoAssin)
                      : undefined,
                  })
                }
              >
                <option value="">Todos</option>
                <option value="pendente">Pendente</option>
                <option value="concluida">Concluída</option>
                <option value="cancelada">Cancelada</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="solicitante">Solicitante</Label>
              <Select
                id="solicitante"
                value={draft.id_solicitante ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    id_solicitante: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              >
                <option value="">Todos</option>
                {usuariosQ.data?.items.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nome}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="assinante">Assinante</Label>
              <Select
                id="assinante"
                value={draft.id_assinante ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    id_assinante: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              >
                <option value="">Todos</option>
                {usuariosQ.data?.items.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nome}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="desde">Iniciada desde</Label>
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
              <Label htmlFor="ate">Iniciada até</Label>
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
            <div className="flex flex-wrap items-end gap-2 md:col-span-3">
              <Button onClick={() => setApplied({ ...draft })}>Gerar relatório</Button>
              <Button
                variant="ghost"
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
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <StatCard label="Total" value={String(relQ.data.totais.total)} />
            <StatCard
              label="Pendentes"
              value={String(relQ.data.totais.pendentes)}
              tone="warning"
            />
            <StatCard
              label="Concluídas"
              value={String(relQ.data.totais.concluidas)}
              tone="success"
            />
            <StatCard label="Canceladas" value={String(relQ.data.totais.canceladas)} />
            <StatCard
              label="Tempo médio de conclusão"
              value={fmtMin(relQ.data.totais.minutos_medio_conclusao)}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Por assinante</CardTitle>
              </CardHeader>
              <CardContent>
                {relQ.data.por_assinante.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Sem dados.</p>
                ) : (
                  <Table>
                    <THead>
                      <TR>
                        <TH>Assinante</TH>
                        <TH className="text-right">Pendentes</TH>
                        <TH className="text-right">Concluídas</TH>
                        <TH className="text-right">Tempo médio</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {relQ.data.por_assinante.map((a) => (
                        <TR key={a.id_assinante}>
                          <TD>{a.nome ?? `#${a.id_assinante}`}</TD>
                          <TD className="text-right tabular-nums">
                            {a.pendentes > 0 ? (
                              <span className="font-semibold text-warning-soft-foreground">
                                {a.pendentes}
                              </span>
                            ) : (
                              a.pendentes
                            )}
                          </TD>
                          <TD className="text-right tabular-nums">{a.concluidas}</TD>
                          <TD className="text-right tabular-nums">{fmtMin(a.minutos_medio)}</TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Por solicitante</CardTitle>
              </CardHeader>
              <CardContent>
                {relQ.data.por_solicitante.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Sem dados.</p>
                ) : (
                  <Table>
                    <THead>
                      <TR>
                        <TH>Solicitante</TH>
                        <TH className="text-right">Total</TH>
                        <TH className="text-right">Pend.</TH>
                        <TH className="text-right">Conc.</TH>
                        <TH className="text-right">Canc.</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {relQ.data.por_solicitante.map((s) => (
                        <TR key={s.id_solicitante}>
                          <TD>{s.nome ?? `#${s.id_solicitante}`}</TD>
                          <TD className="text-right tabular-nums">{s.total}</TD>
                          <TD className="text-right tabular-nums">{s.pendentes}</TD>
                          <TD className="text-right tabular-nums">{s.concluidas}</TD>
                          <TD className="text-right tabular-nums">{s.canceladas}</TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Solicitações ({relQ.data.solicitacoes.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <THead>
                  <TR>
                    <TH>Processo</TH>
                    <TH>Solicitante</TH>
                    <TH>Status</TH>
                    <TH>Iniciada</TH>
                    <TH>Tempo</TH>
                    <TH>Assinantes</TH>
                    <TH>Anexos</TH>
                  </TR>
                </THead>
                <TBody>
                  {relQ.data.solicitacoes.length === 0 && (
                    <TR>
                      <TD colSpan={7} className="text-center text-muted-foreground">
                        Nenhuma solicitação no recorte.
                      </TD>
                    </TR>
                  )}
                  {relQ.data.solicitacoes.map((s) => (
                    <TR key={s.id}>
                      <TD>
                        <Link
                          href={`/m/protocolo/processos/${s.id_processo}`}
                          className="font-mono text-xs text-primary hover:underline"
                        >
                          {s.numero_processo ?? `#${s.id_processo}`}
                        </Link>
                      </TD>
                      <TD className="text-sm">{s.nome_solicitante ?? "—"}</TD>
                      <TD>{statusBadge(s.status)}</TD>
                      <TD className="text-xs tabular-nums">{fmtDateTime(s.dt_inicio)}</TD>
                      <TD className="text-xs tabular-nums">{fmtMin(s.minutos_decorridos)}</TD>
                      <TD className="text-xs">
                        <span className="tabular-nums">
                          {s.qtd_assinantes_concluidos}/{s.qtd_assinantes}
                        </span>
                        <div className="text-xs text-muted-foreground">
                          {s.assinantes_resumo.join(" · ")}
                        </div>
                      </TD>
                      <TD className="text-xs tabular-nums">
                        {s.qtd_anexos_assinados}/{s.qtd_anexos}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
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
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "warning" | "success";
}) {
  const color =
    tone === "warning"
      ? "text-warning-soft-foreground"
      : tone === "success"
        ? "text-success-soft-foreground"
        : "text-primary";
  return (
    <div className="rounded-md border border-border bg-card p-3 text-center">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={"text-xl font-bold tabular-nums " + color}>{value}</div>
    </div>
  );
}
