"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Clock,
  FileSpreadsheet,
  FileText,
  Layers,
  ShieldAlert,
  TimerOff,
  TrendingUp,
} from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/ui/page-header";
import { UnidadePicker } from "@/components/UnidadePicker";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { KpiCard } from "@/components/ui/kpi-card";
import { SkeletonKpi } from "@/components/ui/skeleton";
import {
  dashboardApi,
  dashboardExportCsvUrl,
  dashboardExportPdfUrl,
  servicosApi,
  type ApiError,
  type DashboardKpis,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const PERIODOS = [
  { value: 7, label: "7 dias" },
  { value: 30, label: "30 dias" },
  { value: 90, label: "90 dias" },
  { value: 365, label: "1 ano" },
];

const PIE_COLORS = ["#2563eb", "#16a34a", "#f59e0b", "#a855f7", "#ef4444"];

function fmtNum(n: number | null | undefined, decimals = 0): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("pt-BR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtPct(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `${n.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

function fmtDia(s: string): string {
  const d = new Date(s);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}


export default function DashboardPage() {
  const [periodo, setPeriodo] = useState<number>(30);
  const [idUnidade, setIdUnidade] = useState<number | null>(null);
  // PR 5a — filtros novos
  const [idServico, setIdServico] = useState<number | null>(null);
  const [incluirLegado, setIncluirLegado] = useState<boolean>(true);

  const servicosQ = useQuery({
    queryKey: ["dashboard-servicos-filter"],
    queryFn: () => servicosApi.list(false),
    staleTime: 5 * 60_000,
  });

  const exportParams = {
    periodo,
    id_unidade: idUnidade ?? undefined,
    id_servico: idServico ?? undefined,
    incluir_legado: incluirLegado,
  };

  const q = useQuery({
    queryKey: [
      "dashboard-kpis",
      { periodo, idUnidade, idServico, incluirLegado },
    ],
    queryFn: () =>
      dashboardApi.kpis({
        periodo,
        id_unidade: idUnidade ?? undefined,
        id_servico: idServico ?? undefined,
        incluir_legado: incluirLegado,
      }),
    refetchInterval: 60_000,
    retry: (failureCount, error) => {
      // 403 não tem retry — usuário sem permissão precisa ver feedback agora.
      if ((error as ApiError)?.status === 403) return false;
      return failureCount < 2;
    },
  });

  if (q.isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-20 animate-pulse rounded-xl bg-surface-2/40" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonKpi key={i} />
          ))}
        </div>
        <div className="h-64 animate-pulse rounded-lg bg-surface-2/40" />
        {/* PR 5a — skeleton do ranking por serviço */}
        <div
          className="h-48 animate-pulse rounded-lg bg-surface-2/40"
          data-testid="dashboard-ranking-skeleton"
        />
      </div>
    );
  }

  // PR 5a — D-PERMISSAO: 403 explícito.
  if (q.error && (q.error as ApiError)?.status === 403) {
    return (
      <div
        className="rounded-lg border border-danger/40 bg-danger-soft p-6 text-sm text-danger-soft-foreground"
        data-testid="dashboard-403"
      >
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 flex-none" aria-hidden="true" />
          <div>
            <p className="font-semibold">Sem permissão para o dashboard</p>
            <p className="mt-1 text-xs opacity-90">
              Solicite ao administrador municipal a permissão{" "}
              <code className="rounded bg-surface-1 px-1 py-0.5">dashboard</code>{" "}
              no seu grupo de acesso.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (q.error || !q.data) {
    return (
      <div className="rounded-lg border border-danger/40 bg-danger-soft p-4 text-sm text-danger-soft-foreground">
        Erro ao carregar dashboard: {(q.error as Error)?.message ?? "sem dados"}
      </div>
    );
  }

  const d: DashboardKpis = q.data;

  return (
    <div className="space-y-6">
      <PageHeader
        variant="hero"
        icon={TrendingUp}
        title="Dashboard executivo"
        description="Visão consolidada da operação. Filtre por unidade, serviço e período; compare com o período anterior e exporte quando precisar."
        actions={
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-64">
              <div className="mb-1 text-[10px] uppercase tracking-wide text-foreground-subtle">
                Unidade
              </div>
              <UnidadePicker
                value={idUnidade}
                onChange={setIdUnidade}
                placeholder="Todas as unidades"
              />
            </div>
            <div className="w-64">
              <div className="mb-1 text-[10px] uppercase tracking-wide text-foreground-subtle">
                Serviço
              </div>
              <select
                value={idServico ?? ""}
                onChange={(e) =>
                  setIdServico(e.target.value ? Number(e.target.value) : null)
                }
                className="h-10 w-full rounded-md border border-border bg-surface-1 px-3 text-sm text-foreground"
                aria-label="Filtrar por serviço"
                data-testid="dashboard-filtro-servico"
              >
                <option value="">Todos os serviços</option>
                {(servicosQ.data ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nome}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wide text-foreground-subtle">
                Legado
              </div>
              <label className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-md border border-border bg-surface-1 px-3 text-xs text-foreground">
                <input
                  type="checkbox"
                  checked={incluirLegado}
                  onChange={(e) => setIncluirLegado(e.target.checked)}
                  disabled={idServico !== null}
                  data-testid="dashboard-toggle-legado"
                  aria-label="Incluir processos legados (sem serviço)"
                  className="h-4 w-4"
                />
                <span>Incluir legado</span>
              </label>
            </div>
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wide text-foreground-subtle">
                Período
              </div>
              <div className="flex rounded-md border border-border bg-surface-1 p-0.5">
                {PERIODOS.map((p) => (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => setPeriodo(p.value)}
                    className={cn(
                      "h-10 rounded px-3 text-xs font-medium transition-colors duration-fast",
                      periodo === p.value
                        ? "bg-brand text-primary-foreground shadow-sm"
                        : "text-foreground-muted hover:bg-muted",
                    )}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wide text-foreground-subtle">
                Exportar
              </div>
              <div className="flex gap-1">
                <a
                  href={dashboardExportPdfUrl(exportParams, false)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-10 items-center gap-1.5 rounded-md border border-border-strong bg-surface-1 px-3 text-xs font-medium text-foreground transition-colors duration-fast hover:bg-muted"
                  title="Baixar PDF"
                >
                  <FileText className="h-3.5 w-3.5" aria-hidden="true" />
                  PDF
                </a>
                <a
                  href={dashboardExportCsvUrl(exportParams)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-10 items-center gap-1.5 rounded-md border border-border-strong bg-surface-1 px-3 text-xs font-medium text-foreground transition-colors duration-fast hover:bg-muted"
                  title="Baixar CSV"
                >
                  <FileSpreadsheet className="h-3.5 w-3.5" aria-hidden="true" />
                  CSV
                </a>
              </div>
            </div>
          </div>
        }
      />

      {/* KPI cards (Fase 18) — preservados byte-a-byte */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Abertos no período"
          value={fmtNum(d.volume.abertos_periodo)}
          hint={`${d.volume.externos_periodo} externos · ${d.volume.sigilosos_periodo} sigilosos`}
          icon={FileText}
          current={d.volume.abertos_periodo}
          previous={d.comparativo.abertos_anterior}
        />
        <KpiCard
          label="Ativos agora"
          value={fmtNum(d.volume.ativos_hoje)}
          hint="snapshot hoje (sem comparativo)"
          icon={TrendingUp}
        />
        <KpiCard
          label="Concluídos no período"
          value={fmtNum(d.conclusao.arquivados_periodo)}
          hint={
            d.conclusao.taxa_conclusao_pct !== null
              ? `Taxa: ${fmtPct(d.conclusao.taxa_conclusao_pct)}`
              : undefined
          }
          icon={CheckCircle2}
          intent="success"
          current={d.conclusao.arquivados_periodo}
          previous={d.comparativo.arquivados_anterior}
        />
        <KpiCard
          label="Tempo médio"
          value={
            d.conclusao.tempo_medio_dias !== null
              ? `${fmtNum(d.conclusao.tempo_medio_dias, 1)}d`
              : "—"
          }
          hint="abertura → conclusão"
          icon={Clock}
          current={d.conclusao.tempo_medio_dias}
          previous={d.comparativo.tempo_medio_dias_anterior}
          lowerIsBetter
        />
        <KpiCard
          label="SLA pendentes"
          value={fmtNum(d.sla.pendentes)}
          hint="alertas não resolvidos (snapshot)"
          icon={AlertTriangle}
          intent={d.sla.pendentes > 0 ? "warning" : "default"}
        />
        <KpiCard
          label="SLA resolvidos"
          value={fmtNum(d.sla.resolvidos_periodo)}
          hint="no período"
          icon={CheckCircle2}
          intent="success"
          current={d.sla.resolvidos_periodo}
          previous={d.comparativo.sla_resolvidos_anterior}
        />
      </div>

      {/* PR 5a — KPIs documental + complementação. PR 5a-fix: card extra
          para `sem_documentos_exigidos`, separado de `checklist_completo`. */}
      <div
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
        data-testid="dashboard-pr5a-kpis"
      >
        <KpiCard
          label="Checklist pendente"
          value={fmtNum(d.documental.checklist_pendente)}
          hint="obrigatórios não enviados"
          icon={Layers}
          intent={d.documental.checklist_pendente > 0 ? "warning" : "default"}
        />
        <KpiCard
          label="Checklist completo"
          value={fmtNum(d.documental.checklist_completo)}
          hint="todos os obrigatórios enviados"
          icon={CheckCircle2}
          intent="success"
        />
        <KpiCard
          label="Sem documentos exigidos"
          value={fmtNum(d.documental.sem_documentos_exigidos)}
          hint="serviço sem obrigatórios aplicáveis"
          icon={Layers}
        />
        <KpiCard
          label="Complementações abertas"
          value={fmtNum(d.complementacao.abertas_agora)}
          hint={`${d.complementacao.processos_com_aberta_agora} processo(s)`}
          icon={AlertTriangle}
          intent={d.complementacao.abertas_agora > 0 ? "warning" : "default"}
        />
        <KpiCard
          label="Tempo médio de resposta"
          value={
            d.complementacao.tempo_medio_resposta_dias !== null
              ? `${fmtNum(d.complementacao.tempo_medio_resposta_dias, 1)}d`
              : "—"
          }
          hint="cidadão → respondida"
          icon={Clock}
        />
      </div>

      {/* PR 5b — Bloco prazos end-to-end. D-NOME: NÃO é "sla" (workflow). */}
      <div
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
        data-testid="dashboard-pr5b-prazos"
      >
        <KpiCard
          label="Dentro do prazo"
          value={fmtNum(d.prazos.dentro_do_prazo)}
          hint="snapshot — em andamento"
          icon={Clock}
          intent={d.prazos.dentro_do_prazo > 0 ? "success" : "default"}
        />
        <KpiCard
          label="Vencendo"
          value={fmtNum(d.prazos.vencendo)}
          hint="restam ≤ 20% do prazo"
          icon={AlertTriangle}
          intent={d.prazos.vencendo > 0 ? "warning" : "default"}
        />
        <KpiCard
          label="Atrasado"
          value={fmtNum(d.prazos.atrasado)}
          hint="snapshot — em andamento"
          icon={AlertCircle}
          intent={d.prazos.atrasado > 0 ? "danger" : "default"}
        />
        <KpiCard
          label="Sem prazo"
          value={fmtNum(d.prazos.sem_prazo)}
          hint="legado ou serviço sem prazo"
          icon={TimerOff}
        />
        <KpiCard
          label="% no prazo"
          value={fmtPct(d.prazos.percentual_no_prazo)}
          hint="snapshot — exclui sem prazo"
          icon={TrendingUp}
          intent={
            d.prazos.percentual_no_prazo !== null &&
            d.prazos.percentual_no_prazo >= 80
              ? "success"
              : d.prazos.percentual_no_prazo !== null &&
                  d.prazos.percentual_no_prazo < 50
                ? "danger"
                : "default"
          }
        />
        <KpiCard
          label="Concluídos no prazo"
          value={fmtNum(d.prazos.concluido_no_prazo_periodo)}
          hint="arquivados no período"
          icon={CheckCircle2}
          intent="success"
        />
        <KpiCard
          label="Concluídos com atraso"
          value={fmtNum(d.prazos.concluido_atrasado_periodo)}
          hint="arquivados no período"
          icon={CheckCircle2}
          intent={
            d.prazos.concluido_atrasado_periodo > 0 ? "warning" : "default"
          }
        />
        <KpiCard
          label="Tempo médio de atraso"
          value={
            d.prazos.tempo_medio_atraso_dias !== null
              ? `${fmtNum(d.prazos.tempo_medio_atraso_dias, 1)}d`
              : "—"
          }
          hint="andamento + concluídos atrasados"
          icon={CalendarClock}
        />
      </div>

      {/* Série temporal */}
      <Card>
        <CardHeader>
          <CardTitle>Processos abertos por dia</CardTitle>
        </CardHeader>
        <CardContent>
          {d.serie_temporal.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhum processo no período.
            </p>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={d.serie_temporal.map((s) => ({
                    dia: fmtDia(s.dia),
                    count: s.count,
                  }))}
                  margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="dia" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="hsl(213 53% 25%)"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Breakdowns lado a lado */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Por tipo de processo (top 5)</CardTitle>
          </CardHeader>
          <CardContent>
            {d.por_tipo.length === 0 ? (
              <p className="text-sm text-muted-foreground">Sem dados.</p>
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={d.por_tipo}
                      dataKey="count"
                      nameKey="label"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      label={(entry: { label: string }) => entry.label}
                    >
                      {d.por_tipo.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Por unidade (top 10)</CardTitle>
          </CardHeader>
          <CardContent>
            {d.por_unidade.length === 0 ? (
              <p className="text-sm text-muted-foreground">Sem dados.</p>
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={d.por_unidade}
                    layout="vertical"
                    margin={{ top: 5, right: 20, left: 80, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                    <YAxis
                      dataKey="label"
                      type="category"
                      width={120}
                      tick={{ fontSize: 11 }}
                    />
                    <Tooltip />
                    <Bar dataKey="count" fill="hsl(213 53% 25%)" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Por assunto (top 10)</CardTitle>
        </CardHeader>
        <CardContent>
          {d.por_assunto.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sem dados.</p>
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={d.por_assunto}
                  layout="vertical"
                  margin={{ top: 5, right: 20, left: 80, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis
                    dataKey="label"
                    type="category"
                    width={160}
                    tick={{ fontSize: 11 }}
                  />
                  <Tooltip />
                  <Bar dataKey="count" fill="#16a34a" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* PR 5a — ranking por serviço */}
      <Card data-testid="dashboard-ranking-servicos">
        <CardHeader>
          <CardTitle>Por serviço (top 10)</CardTitle>
        </CardHeader>
        <CardContent>
          {d.por_servico.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Sem dados no período.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-border text-left text-xs uppercase tracking-wide text-foreground-muted">
                  <tr>
                    <th className="py-2 pr-4 font-medium">Serviço</th>
                    <th className="py-2 pr-4 text-right font-medium tabular-nums">
                      Processos
                    </th>
                    <th className="py-2 pr-4 text-right font-medium tabular-nums">
                      Compl. abertas
                    </th>
                    <th className="py-2 pr-4 text-right font-medium tabular-nums">
                      Compl. respondidas
                    </th>
                    <th className="py-2 pr-4 text-right font-medium tabular-nums">
                      Pendente
                    </th>
                    <th className="py-2 pr-4 text-right font-medium tabular-nums">
                      Parcial
                    </th>
                    <th className="py-2 pr-4 text-right font-medium tabular-nums">
                      Completo
                    </th>
                    {/* PR 5a-fix */}
                    <th
                      className="py-2 pr-4 text-right font-medium tabular-nums"
                      title="Processos sem obrigatórios aplicáveis"
                    >
                      S/Docs
                    </th>
                    {/* PR 5b */}
                    <th
                      className="py-2 text-right font-medium tabular-nums"
                      title="Processos NÃO concluídos com prazo vencido"
                    >
                      Atrasados
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {d.por_servico.map((it) => {
                    const legado = it.id_servico === null;
                    return (
                      <tr
                        key={`${it.id_servico ?? "legado"}`}
                        className={cn(
                          "border-b border-border/60 last:border-0",
                          legado && "bg-warning-soft/30",
                        )}
                        data-testid={
                          legado
                            ? "dashboard-ranking-legado"
                            : "dashboard-ranking-item"
                        }
                      >
                        <td className="py-2 pr-4">
                          {legado ? (
                            <span className="italic text-warning-soft-foreground">
                              {it.nome} — legado
                            </span>
                          ) : (
                            it.nome
                          )}
                        </td>
                        <td className="py-2 pr-4 text-right tabular-nums">
                          {fmtNum(it.count)}
                        </td>
                        <td className="py-2 pr-4 text-right tabular-nums">
                          {fmtNum(it.complementacoes_abertas)}
                        </td>
                        <td className="py-2 pr-4 text-right tabular-nums">
                          {fmtNum(it.complementacoes_respondidas_periodo)}
                        </td>
                        <td className="py-2 pr-4 text-right tabular-nums">
                          {fmtNum(it.checklist_pendente)}
                        </td>
                        <td className="py-2 pr-4 text-right tabular-nums">
                          {fmtNum(it.checklist_parcial)}
                        </td>
                        <td className="py-2 pr-4 text-right tabular-nums">
                          {fmtNum(it.checklist_completo)}
                        </td>
                        <td className="py-2 pr-4 text-right tabular-nums">
                          {fmtNum(it.sem_documentos_exigidos)}
                        </td>
                        {/* PR 5b */}
                        <td
                          className={cn(
                            "py-2 text-right tabular-nums",
                            it.atrasados > 0 && "font-semibold text-danger",
                          )}
                        >
                          {fmtNum(it.atrasados)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
