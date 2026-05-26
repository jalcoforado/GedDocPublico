"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileSpreadsheet,
  FileText,
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
  Legend,
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

  const q = useQuery({
    queryKey: ["dashboard-kpis", { periodo, idUnidade }],
    queryFn: () =>
      dashboardApi.kpis({
        periodo,
        id_unidade: idUnidade ?? undefined,
      }),
    refetchInterval: 60_000,
  });

  if (q.isLoading) {
    // Skeleton de KPIs em grid 4 cols + skeletons abaixo
    return (
      <div className="space-y-6">
        <div className="h-20 animate-pulse rounded-xl bg-surface-2/40" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonKpi key={i} />
          ))}
        </div>
        <div className="h-64 animate-pulse rounded-lg bg-surface-2/40" />
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
        description="Visão consolidada da operação. Compare com o período anterior, filtre por unidade e exporte quando precisar."
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
                  href={dashboardExportPdfUrl(
                    { periodo, id_unidade: idUnidade ?? undefined },
                    false,
                  )}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-10 items-center gap-1.5 rounded-md border border-border-strong bg-surface-1 px-3 text-xs font-medium text-foreground transition-colors duration-fast hover:bg-muted"
                  title="Baixar PDF"
                >
                  <FileText className="h-3.5 w-3.5" aria-hidden="true" />
                  PDF
                </a>
                <a
                  href={dashboardExportCsvUrl({
                    periodo,
                    id_unidade: idUnidade ?? undefined,
                  })}
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

      {/* KPI cards */}
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
    </div>
  );
}
