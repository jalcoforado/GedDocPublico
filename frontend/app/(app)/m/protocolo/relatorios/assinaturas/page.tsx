"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, Download, FileText, XCircle } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { FiltrosDoRelatorio } from "@/components/relatorios/FiltrosDoRelatorio";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Carregando } from "@/components/ui/carregando";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import {
  api,
  assinaturasCsvUrl,
  assinaturasPdfUrl,
  type AssinaturasFiltroInput,
  type StatusSolicitacaoAssin,
} from "@/lib/api";
import {
  ROTA_RELATORIOS,
  filtroDaUrl,
  filtroParaUrl,
  fmtDataHora as fmtDateTime,
  fmtMinutos as fmtMin,
  recorteComum,
  type FiltroDaUrl,
} from "@/lib/relatorios";

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

/**
 * Assinaturas (SI-34) — o "ver lista" da seção Assinaturas da página de
 * relatórios. O recorte comum (período, unidade, assunto, tipo — sobre o
 * processo de cada pedido) vem da URL; situação, solicitante e assinante são
 * filtros próprios desta tela.
 */
export default function RelatorioAssinaturasPage() {
  const router = useRouter();
  const pathname = usePathname();
  const busca = useSearchParams().toString();
  const filtro = useMemo(() => filtroDaUrl(new URLSearchParams(busca)), [busca]);
  const dataBase = filtro.data_base === "conclusao" ? "conclusao" : "pedido";
  const [proprios, setProprios] = useState<
    Pick<AssinaturasFiltroInput, "status" | "id_solicitante" | "id_assinante">
  >({});
  const consulta: AssinaturasFiltroInput = { ...recorteComum(filtro), data_base: dataBase, ...proprios };

  function irPara(f: FiltroDaUrl) {
    router.replace(`${pathname}${filtroParaUrl(f)}`, { scroll: false });
  }

  const usuariosQ = useQuery({
    queryKey: ["usuarios-list-relatorio"],
    // Teto de GET /usuarios é 100 (routers/usuarios.py); 200 dava 422.
    queryFn: () => api.usuarios.list({ page_size: 100 }),
  });

  const relQ = useQuery({
    queryKey: ["relatorio-assinaturas", busca, proprios],
    queryFn: () => api.relatorios.assinaturas(consulta),
  });

  const num = (v: string) => (v ? Number(v) : undefined);

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[
          { label: "Relatórios", href: `${ROTA_RELATORIOS}${filtroParaUrl(recorteComum(filtro))}` },
          { label: "Assinaturas" },
        ]}
        title="Assinaturas"
        description="Pedidos de assinatura do período: quem pediu, quem assina, o que está pendente e quanto tempo levou."
        actions={
          <div className="flex flex-wrap gap-2">
            <a
              href={assinaturasCsvUrl(consulta)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-muted px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Download className="h-4 w-4" aria-hidden="true" /> CSV
            </a>
            <a
              href={assinaturasPdfUrl(consulta)}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-3 text-xs font-medium text-primary-foreground transition-colors hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <FileText className="h-4 w-4" aria-hidden="true" /> PDF
            </a>
          </div>
        }
      />

      <FiltrosDoRelatorio
        valor={recorteComum(filtro)}
        onAplicar={(f) => irPara({ ...f, data_base: filtro.data_base })}
      />

      <Card>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <div>
              <Label htmlFor="ass-data-base">Período conta pela data do</Label>
              <Select
                id="ass-data-base"
                value={dataBase}
                onChange={(e) => irPara({ ...filtro, data_base: e.target.value as "pedido" | "conclusao" })}
              >
                <option value="pedido">pedido</option>
                <option value="conclusao">conclusão</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="status">Situação</Label>
              <Select
                id="status"
                value={proprios.status ?? ""}
                onChange={(e) =>
                  setProprios({
                    ...proprios,
                    status: e.target.value ? (e.target.value as StatusSolicitacaoAssin) : undefined,
                  })
                }
              >
                <option value="">Todas</option>
                <option value="pendente">Pendente</option>
                <option value="concluida">Concluída</option>
                <option value="cancelada">Cancelada</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="solicitante">Solicitante</Label>
              <Select
                id="solicitante"
                value={proprios.id_solicitante ?? ""}
                onChange={(e) => setProprios({ ...proprios, id_solicitante: num(e.target.value) })}
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
                value={proprios.id_assinante ?? ""}
                onChange={(e) => setProprios({ ...proprios, id_assinante: num(e.target.value) })}
              >
                <option value="">Todos</option>
                {usuariosQ.data?.items.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nome}
                  </option>
                ))}
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {relQ.data && (
        <ul className="space-y-0.5 text-xs text-muted-foreground" aria-label="Recorte do relatório">
          {relQ.data.descricao_filtros.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      )}

      {relQ.isLoading && <Carregando className="text-sm text-muted-foreground" />}
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
              <CardTitle>
                {relQ.data.cortado
                  ? `Solicitações (as ${relQ.data.solicitacoes.length} mais recentes de ${relQ.data.totais.total}; os totais contam todas — use o CSV)`
                  : `Solicitações (${relQ.data.solicitacoes.length})`}
              </CardTitle>
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
