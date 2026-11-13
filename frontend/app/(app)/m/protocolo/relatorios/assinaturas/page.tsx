"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, FileSignature, Inbox, Timer, XCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AcoesDoFiltro, RelatorioCabecalho, temFiltro } from "@/components/protocolo/RelatorioCabecalho";
import { RankingEmBarras } from "@/components/protocolo/RankingEmBarras";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Carregando } from "@/components/ui/carregando";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { Input } from "@/components/ui/input";
import { KpiCard } from "@/components/ui/kpi-card";
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
import { useFiltroNaUrl } from "@/lib/filtro-na-url";

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
  // Médias chegam fracionadas (123.4 min); sem arredondar saía "2h 03.4min".
  m = Math.round(m);
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
  // Filtro aplicado mora na URL: recarregar, voltar ou mandar o link reabre o mesmo recorte.
  const [applied, aplicar] = useFiltroNaUrl<AssinaturasFiltroInput>();
  const [draft, setDraft] = useState<AssinaturasFiltroInput>(applied);
  useEffect(() => setDraft(applied), [applied]);

  const usuariosQ = useQuery({
    queryKey: ["usuarios-list-relatorio"],
    // Teto de GET /usuarios é 100 (routers/usuarios.py); 200 dava 422.
    queryFn: () => api.usuarios.list({ page_size: 100 }),
  });

  const relQ = useQuery({
    queryKey: ["relatorio-assinaturas", applied],
    queryFn: () => api.relatorios.assinaturas(applied),
  });

  return (
    <div className="space-y-4">
      <RelatorioCabecalho
        subtitulo="Assinaturas — pendências, conclusões e tempo"
        csvUrl={assinaturasCsvUrl(applied)}
        pdfUrl={assinaturasPdfUrl(applied)}
      />

      <FilterBar>
        <div className="w-full sm:w-40">
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
        <div className="w-full sm:w-52">
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
        <div className="w-full sm:w-52">
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
        <div className="w-full sm:w-40">
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
        <div className="w-full sm:w-40">
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
        <AcoesDoFiltro
          filtrado={temFiltro(draft) || temFiltro(applied)}
          onGerar={() => aplicar({ ...draft })}
          onLimpar={() => {
            setDraft({});
            aplicar({});
          }}
        />
      </FilterBar>

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
            {/* Mesmos ícones e cores dos selos de status da tabela abaixo. */}
            <KpiCard label="Total" value={relQ.data.totais.total} icon={FileSignature} />
            <KpiCard
              label="Pendentes"
              value={relQ.data.totais.pendentes}
              icon={Clock}
              intent="warning"
            />
            <KpiCard
              label="Concluídas"
              value={relQ.data.totais.concluidas}
              icon={CheckCircle2}
              intent="success"
            />
            <KpiCard label="Canceladas" value={relQ.data.totais.canceladas} icon={XCircle} />
            <KpiCard
              label="Tempo médio de conclusão"
              value={fmtMin(relQ.data.totais.minutos_medio_conclusao)}
              icon={Timer}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Com quem estão as assinaturas pendentes?</CardTitle>
                <CardDescription>
                  Assinantes pelo número de assinaturas que ainda esperam por eles.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <RankingEmBarras
                  rotuloDoValor="pendentes"
                  vazio={
                    <EmptyState
                      icon={CheckCircle2}
                      title="Ninguém com assinatura pendente"
                      className="p-6"
                    />
                  }
                  itens={relQ.data.por_assinante
                    .filter((a) => a.pendentes > 0)
                    .sort((a, b) => b.pendentes - a.pendentes)
                    .map((a) => ({
                      chave: a.id_assinante,
                      rotulo: a.nome ?? `#${a.id_assinante}`,
                      valor: a.pendentes,
                      valorTexto: String(a.pendentes),
                      detalhe: (
                        <>
                          {a.concluidas} {a.concluidas === 1 ? "concluída" : "concluídas"}
                          {a.concluidas > 0 &&
                            ` · assina em ${fmtMin(Math.round(a.minutos_medio))} em média`}
                        </>
                      ),
                    }))}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Por solicitante</CardTitle>
              </CardHeader>
              <CardContent>
                {relQ.data.por_solicitante.length === 0 ? (
                  <EmptyState icon={Inbox} title="Sem dados no recorte" className="p-6" />
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
              {relQ.data.solicitacoes.length === 0 ? (
                <EmptyState
                  icon={Inbox}
                  title="Nenhuma solicitação no recorte"
                  description="Ajuste os filtros acima e gere o relatório de novo."
                />
              ) : (
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
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

