"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  Download,
  Inbox,
  ScrollText,
  SearchX,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { fmtData } from "@/components/pagamentos/format";
import { rotuloTipoServico, TIPOS_SERVICO } from "@/components/transporte/rotulos";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Carregando } from "@/components/ui/carregando";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SkeletonKpi } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type AlvaraKPIsResponse,
  type AlvaraRelatorioItem,
  type AlvaraRelatorioListResponse,
} from "@/lib/api";

type StatusAlvara = AlvaraRelatorioItem["status"];

// Mesma situação, mesma cor da lista de alvarás: vencido é `danger` lá
// ("Expirado") e aqui.
const STATUS: Record<
  StatusAlvara,
  { label: string; intent: "success" | "danger" | "warning" | "neutral" }
> = {
  ativo: { label: "Ativo", intent: "success" },
  vencido: { label: "Vencido", intent: "danger" },
  a_renovar_30d: { label: "A renovar (30 dias)", intent: "warning" },
  indefinido: { label: "Sem validade", intent: "neutral" },
};

interface Filters {
  tipo_servico?: string;
  id_permissionario?: number;
  status?: StatusAlvara;
  limit: number;
  offset: number;
}

const FILTROS_INICIAIS: Filters = { limit: 50, offset: 0 };

/** "em 20 dias", "vence hoje", "venceu há 17 dias" — no lugar do "-17d". */
function prazo(dias: number | null): string {
  if (dias === null) return "—";
  if (dias === 0) return "vence hoje";
  if (dias < 0) return `venceu há ${-dias} ${dias === -1 ? "dia" : "dias"}`;
  return `em ${dias} ${dias === 1 ? "dia" : "dias"}`;
}

export default function RelatorioPage() {
  const { toast } = useToast();

  const [filters, setFilters] = useState<Filters>(FILTROS_INICIAIS);
  const filtrando = Boolean(filters.tipo_servico || filters.status || filters.id_permissionario);

  // KPIs
  const { data: kpis, isLoading: kpisLoading } = useQuery<AlvaraKPIsResponse>({
    queryKey: ["/transporte-regulado/alvaras/relatorio/kpis"],
    queryFn: () => api.alvaras.relatorio.kpis(),
  });

  // Relatório com filtros
  const { data: relatorio, isLoading: relatorioLoading } =
    useQuery<AlvaraRelatorioListResponse>({
      queryKey: ["/transporte-regulado/alvaras/relatorio", filters],
      queryFn: () => api.alvaras.relatorio.list(filters),
    });

  const handleExportCsv = () => {
    try {
      const url = api.alvaras.relatorio.exportCsv({
        tipo_servico: filters.tipo_servico,
        id_permissionario: filters.id_permissionario,
        status: filters.status,
      });
      const link = document.createElement("a");
      link.href = url;
      link.click();
      toast({ message: "CSV exportado com sucesso!", intent: "success" });
    } catch {
      toast({ message: "Erro ao exportar CSV", intent: "error" });
    }
  };

  const handleFilterChange = (key: "tipo_servico" | "status", value: string | undefined) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value || undefined,
      offset: 0,
    }));
  };

  const limpar = () => setFilters(FILTROS_INICIAIS);

  return (
    <div className="space-y-4">
      <PageHeader
        icon={BarChart3}
        title="Relatório de alvarás"
        description="Situação dos alvarás do transporte regulado e o que vence nos próximos 30 dias."
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Relatório de alvarás" },
        ]}
        actions={
          <Button
            variant="secondary"
            onClick={handleExportCsv}
            disabled={!relatorio || relatorio.alvaras.length === 0}
          >
            <Download className="mr-1 h-4 w-4" aria-hidden="true" />
            Exportar CSV
          </Button>
        }
      />

      {kpisLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <SkeletonKpi key={i} />
          ))}
        </div>
      ) : kpis ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard label="Total de alvarás" value={kpis.total_alvaras} icon={ScrollText} />
          <KpiCard label="Ativos" value={kpis.ativos} icon={CheckCircle2} intent="success" />
          <KpiCard label="Vencidos" value={kpis.vencidos} icon={AlertTriangle} intent="danger" />
          <KpiCard
            label="A renovar (30 dias)"
            value={kpis.a_renovar_30d}
            icon={Clock}
            intent="warning"
          />
        </div>
      ) : null}

      <FilterBar ariaLabel="Filtros do relatório">
        <FilterBar.Group label="Tipo de serviço" className="w-full sm:w-56">
          <Select
            aria-label="Tipo de serviço"
            value={filters.tipo_servico || ""}
            onChange={(e) => handleFilterChange("tipo_servico", e.target.value)}
          >
            <option value="">Todos</option>
            {TIPOS_SERVICO.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        <FilterBar.Group label="Situação" className="w-full sm:w-56">
          <Select
            aria-label="Situação"
            value={filters.status || ""}
            onChange={(e) => handleFilterChange("status", e.target.value)}
          >
            <option value="">Todas</option>
            {(Object.keys(STATUS) as StatusAlvara[]).map((s) => (
              <option key={s} value={s}>
                {STATUS[s].label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        {filtrando && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={limpar}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {relatorioLoading ? (
        <Carregando className="py-8 text-center text-foreground-muted" />
      ) : !relatorio || relatorio.alvaras.length === 0 ? (
        <EmptyState
          icon={filtrando ? SearchX : Inbox}
          title="Nenhum alvará encontrado"
          description={
            filtrando
              ? "Nenhum alvará corresponde aos filtros aplicados."
              : "Os alvarás cadastrados aparecem aqui, com a situação de cada um."
          }
          action={
            filtrando ? (
              <Button variant="secondary" onClick={limpar}>
                Limpar filtros
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <Table>
            <THead>
              <TR>
                <TH>Número</TH>
                <TH>Tipo de serviço</TH>
                <TH>Situação</TH>
                <TH>Validade</TH>
                <TH>Vencimento</TH>
              </TR>
            </THead>
            <TBody>
              {relatorio.alvaras.map((alvara) => {
                const st = STATUS[alvara.status] ?? {
                  label: alvara.status,
                  intent: "neutral" as const,
                };
                return (
                  <TR key={alvara.id}>
                    <TD className="font-mono font-medium">
                      <Link
                        href={`/m/transporte/alvaras/${alvara.id}`}
                        className="text-primary hover:underline"
                      >
                        {alvara.numero_alvara}
                      </Link>
                    </TD>
                    <TD>{rotuloTipoServico(alvara.tipo_servico)}</TD>
                    <TD>
                      <Badge intent={st.intent}>{st.label}</Badge>
                    </TD>
                    <TD className="tabular-nums">{fmtData(alvara.data_validade)}</TD>
                    <TD className="text-foreground-muted">{prazo(alvara.dias_para_vencimento)}</TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>

          <div className="flex flex-col items-start justify-between gap-2 text-sm text-foreground-muted sm:flex-row sm:items-center">
            <span className="tabular-nums">
              {relatorio.total} {relatorio.total === 1 ? "alvará" : "alvarás"}
            </span>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={filters.offset === 0}
                onClick={() =>
                  setFilters((prev) => ({
                    ...prev,
                    offset: Math.max(0, prev.offset - prev.limit),
                  }))
                }
              >
                Anterior
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={filters.offset + filters.limit >= relatorio.total}
                onClick={() =>
                  setFilters((prev) => ({
                    ...prev,
                    offset: prev.offset + prev.limit,
                  }))
                }
              >
                Próxima
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
