"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  Download,
  Eye,
  FileText,
  Lock,
  Pause,
} from "lucide-react";
import Link from "next/link";
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
import { useAssuntosAll } from "@/lib/assuntos";
import {
  api,
  NIVEL_SIGILO_LABEL,
  relatorioCsvUrl,
  relatorioPdfUrl,
  type RelatorioFiltroInput,
} from "@/lib/api";

function fmtDateTime(s: string) {
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

export default function RelatoriosPage() {
  const [draft, setDraft] = useState<RelatorioFiltroInput>({});
  const [applied, setApplied] = useState<RelatorioFiltroInput>({});

  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const assuntosQ = useAssuntosAll();
  const tiposQ = useQuery({
    queryKey: ["tipos-processo"],
    queryFn: () => api.tiposProcesso.list(),
  });

  const relQ = useQuery({
    queryKey: ["relatorio-processos", applied],
    queryFn: () => api.relatorios.processos(applied),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-primary">Relatórios</h1>
      <RelatoriosNav />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-lg font-semibold text-foreground">
          Processos por unidade/período
        </h2>
        <div className="flex flex-wrap gap-2">
          <a
            href={relatorioCsvUrl(applied)}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-muted px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Download className="h-4 w-4" aria-hidden="true" /> CSV
          </a>
          <a
            href={relatorioPdfUrl(applied)}
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
              <Label htmlFor="unidade">Unidade (proprietária ou local atual)</Label>
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
              <Label htmlFor="assunto">Assunto</Label>
              <Select
                id="assunto"
                value={draft.id_assunto ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    id_assunto: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              >
                <option value="">Todos</option>
                {assuntosQ.data?.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.assunto.length > 60 ? a.assunto.slice(0, 60) + "…" : a.assunto}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex items-center gap-2 md:pt-6">
              <Checkbox
                id="ativos"
                checked={!!draft.apenas_ativos}
                onChange={(e) => setDraft({ ...draft, apenas_ativos: e.target.checked })}
              />
              <Label htmlFor="ativos" className="!mb-0">
                Apenas ativos
              </Label>
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
            <div className="flex flex-wrap items-end gap-2 md:col-span-2">
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

      {relQ.isLoading && (
        <p className="text-sm text-muted-foreground">Carregando relatório...</p>
      )}
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
          {relQ.data.nome_unidade && (
            <p className="text-sm text-muted-foreground">
              Filtro: <b>{relQ.data.nome_unidade}</b>
            </p>
          )}

          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <TotalCard label="Total" value={relQ.data.totais.total} />
            <TotalCard label="Ativos" value={relQ.data.totais.ativos} />
            <TotalCard label="Inativos" value={relQ.data.totais.inativos} />
            <TotalCard label="Sigilosos" value={relQ.data.totais.sigilosos} />
            <TotalCard label="Externos" value={relQ.data.totais.externos} />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Por tipo de processo</CardTitle>
              </CardHeader>
              <CardContent>
                <BreakdownTable rows={relQ.data.por_tipo_processo} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Por unidade proprietária</CardTitle>
              </CardHeader>
              <CardContent>
                <BreakdownTable rows={relQ.data.por_unidade_proprietaria} />
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Processos ({relQ.data.processos.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <THead>
                  <TR>
                    <TH>Número</TH>
                    <TH>Aberto em</TH>
                    <TH>Manifestante</TH>
                    <TH>Tipo</TH>
                    <TH>Unid. propr.</TH>
                    <TH>Local atual</TH>
                    <TH>Status</TH>
                  </TR>
                </THead>
                <TBody>
                  {relQ.data.processos.length === 0 && (
                    <TR>
                      <TD colSpan={7} className="text-center text-muted-foreground">
                        Nenhum processo no recorte.
                      </TD>
                    </TR>
                  )}
                  {relQ.data.processos.map((p) => (
                    <TR key={p.id}>
                      <TD>
                        <Link
                          href={`/m/protocolo/processos/${p.id}`}
                          className="font-mono text-xs text-primary hover:underline"
                        >
                          {p.numero_processo}
                        </Link>
                      </TD>
                      <TD className="text-xs tabular-nums">{fmtDateTime(p.data_hora_abertura)}</TD>
                      <TD className="text-sm">{p.manifestante ?? "—"}</TD>
                      <TD className="text-sm">{p.tipo_processo ?? "—"}</TD>
                      <TD className="text-sm">{p.unidade_proprietaria ?? "—"}</TD>
                      <TD className="text-sm">{p.local_atual ?? "—"}</TD>
                      <TD>
                        <div className="flex flex-wrap gap-1">
                          {p.ativo ? (
                            <Badge intent="success" icon={CheckCircle2}>Ativo</Badge>
                          ) : (
                            <Badge intent="neutral" icon={Pause}>Inativo</Badge>
                          )}
                          {!p.publico && (
                            <Badge intent="warning" icon={Lock}>
                              {NIVEL_SIGILO_LABEL[p.nivel_sigilo]}
                            </Badge>
                          )}
                          {p.externo && <Badge intent="info" icon={Eye}>Externo</Badge>}
                        </div>
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

function TotalCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-border bg-card p-3 text-center">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="text-2xl font-bold text-primary tabular-nums">{value}</div>
    </div>
  );
}

function BreakdownTable({
  rows,
}: {
  rows: { label: string; count: number; pct: number }[];
}) {
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">Sem dados.</p>;
  }
  return (
    <Table>
      <THead>
        <TR>
          <TH>Item</TH>
          <TH className="text-right">Qtd</TH>
          <TH className="text-right">%</TH>
        </TR>
      </THead>
      <TBody>
        {rows.map((r) => (
          <TR key={r.label}>
            <TD>{r.label}</TD>
            <TD className="text-right tabular-nums">{r.count}</TD>
            <TD className="text-right tabular-nums">{r.pct.toFixed(1)}%</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
