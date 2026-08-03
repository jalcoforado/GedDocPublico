"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3, Download, Inbox, TrendingDown, TrendingUp } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type AlvaraKPIsResponse,
  type AlvaraRelatorioListResponse,
  type Permissionario,
  type TipoServico,
} from "@/lib/api";

const TIPOS: { value: TipoServico; label: string }[] = [
  { value: "taxi", label: "Táxi" },
  { value: "mototaxi", label: "Mototáxi" },
  { value: "transporte_escolar", label: "Transporte escolar" },
  { value: "motofrete", label: "Motofrete" },
  { value: "transporte_distrital", label: "Transporte distrital" },
  { value: "aplicativo", label: "Aplicativo" },
  { value: "outro", label: "Outro" },
];

const STATUS_LABELS: Record<string, string> = {
  ativo: "Ativo",
  vencido: "Vencido",
  a_renovar_30d: "A renovar (30d)",
  indefinido: "Indefinido",
};

const STATUS_COLORS: Record<string, string> = {
  ativo: "bg-green-100 text-green-800",
  vencido: "bg-red-100 text-red-800",
  a_renovar_30d: "bg-yellow-100 text-yellow-800",
  indefinido: "bg-gray-100 text-gray-800",
};

interface Filters {
  tipo_servico?: string;
  id_permissionario?: number;
  status?: "ativo" | "vencido" | "a_renovar_30d" | "indefinido";
  limit: number;
  offset: number;
}

function KPICard({ label, value, icon: Icon, color }: any) {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">{label}</p>
          <p className="text-3xl font-bold">{value}</p>
        </div>
        <Icon className={`h-8 w-8 ${color}`} />
      </div>
    </div>
  );
}

export default function RelatorioPage() {
  const { toast } = useToast();

  const [filters, setFilters] = useState<Filters>({
    limit: 50,
    offset: 0,
  });

  // KPIs
  const { data: kpis, isLoading: kpisLoading } = useQuery<AlvaraKPIsResponse>({
    queryKey: ["/transporte-regulado/alvaras/relatorio/kpis"],
    queryFn: () => api.alvaras.relatorio.kpis(),
  });

  // Relatório com filtros
  const { data: relatorio, isLoading: relatarioLoading } =
    useQuery<AlvaraRelatorioListResponse>({
      queryKey: [
        "/transporte-regulado/alvaras/relatorio",
        filters,
      ],
      queryFn: () => api.alvaras.relatorio.list(filters),
    });

  const handleExportCsv = () => {
    try {
      const url = api.alvaras.relatorio.exportCsv({
        tipo_servico: filters.tipo_servico,
        id_permissionario: filters.id_permissionario,
        status: filters.status as any,
      });
      const link = document.createElement("a");
      link.href = url;
      link.click();
      toast({ message: "CSV exportado com sucesso!", intent: "success" });
    } catch (err) {
      toast({ message: "Erro ao exportar CSV", intent: "error" });
    }
  };

  const handleFilterChange = (key: string, value: any) => {
    setFilters((prev) => ({
      ...prev,
      [key]: value || undefined,
      offset: 0,
    }));
  };

  return (
    <div className="space-y-6 pb-8">
      <PageHeader title="Relatório de Alvarás" description="KPIs e análise de alvarás regulados" icon={BarChart3} />

      {/* KPIs */}
      {kpisLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-lg bg-gray-200" />
          ))}
        </div>
      ) : kpis ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <KPICard
            label="Total de Alvarás"
            value={kpis.total_alvaras}
            icon={() => <div className="h-8 w-8 rounded-full bg-blue-100" />}
            color="text-blue-600"
          />
          <KPICard
            label="Ativos"
            value={kpis.ativos}
            icon={TrendingUp}
            color="text-green-600"
          />
          <KPICard
            label="Vencidos"
            value={kpis.vencidos}
            icon={TrendingDown}
            color="text-red-600"
          />
          <KPICard
            label="A Renovar (30d)"
            value={kpis.a_renovar_30d}
            icon={() => <div className="h-8 w-8 rounded-full bg-yellow-100" />}
            color="text-yellow-600"
          />
        </div>
      ) : null}

      {/* Filtros */}
      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <h3 className="mb-4 text-lg font-semibold">Filtros</h3>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <div>
            <Label>Tipo de Serviço</Label>
            <Select
              value={filters.tipo_servico || ""}
              onChange={(e) =>
                handleFilterChange("tipo_servico", e.target.value || undefined)
              }
            >
              <option value="">Todos</option>
              {TIPOS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </div>

          <div>
            <Label>Status</Label>
            <Select
              value={filters.status || ""}
              onChange={(e) =>
                handleFilterChange(
                  "status",
                  (e.target.value || undefined) as Filters["status"],
                )
              }
            >
              <option value="">Todos</option>
              <option value="ativo">Ativo</option>
              <option value="vencido">Vencido</option>
              <option value="a_renovar_30d">A Renovar (30d)</option>
              <option value="indefinido">Indefinido</option>
            </Select>
          </div>

          <div className="flex items-end">
            <Button
              variant="secondary"
              onClick={() =>
                setFilters({
                  tipo_servico: undefined,
                  id_permissionario: undefined,
                  status: undefined,
                  limit: 50,
                  offset: 0,
                })
              }
              className="w-full"
            >
              Limpar Filtros
            </Button>
          </div>

          <div className="flex items-end">
            <Button
              onClick={handleExportCsv}
              variant="secondary"
              className="w-full"
              disabled={!relatorio || relatorio.alvaras.length === 0}
            >
              <Download className="mr-2 h-4 w-4" />
              Exportar CSV
            </Button>
          </div>
        </div>
      </div>

      {/* Tabela de Alvarás */}
      <div className="rounded-lg border bg-white shadow-sm">
        {relatarioLoading ? (
          <div className="p-6 text-center">Carregando relatório...</div>
        ) : !relatorio || relatorio.alvaras.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="Nenhum alvará encontrado"
            description="Ajuste seus filtros para ver alvarás"
          />
        ) : (
          <>
            <Table>
              <THead>
                <TR>
                  <TH>Número</TH>
                  <TH>Tipo</TH>
                  <TH>Status</TH>
                  <TH>Validade</TH>
                  <TH>Dias para Vencer</TH>
                </TR>
              </THead>
              <TBody>
                {relatorio.alvaras.map((alvara) => (
                  <TR key={alvara.id}>
                    <TD className="font-medium">{alvara.numero_alvara}</TD>
                    <TD>{alvara.tipo_servico}</TD>
                    <TD>
                      <Badge className={STATUS_COLORS[alvara.status]}>
                        {STATUS_LABELS[alvara.status]}
                      </Badge>
                    </TD>
                    <TD>
                      {alvara.data_validade
                        ? new Date(alvara.data_validade).toLocaleDateString(
                            "pt-BR",
                          )
                        : "—"}
                    </TD>
                    <TD>
                      {alvara.dias_para_vencimento !== null
                        ? `${alvara.dias_para_vencimento}d`
                        : "—"}
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>

            {/* Paginação */}
            <div className="border-t px-6 py-4 flex items-center justify-between">
              <div className="text-sm text-gray-600">
                Total: {relatorio.total} alvarás
              </div>
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
                  disabled={
                    (filters.offset + filters.limit) >= relatorio.total
                  }
                  onClick={() =>
                    setFilters((prev) => ({
                      ...prev,
                      offset: prev.offset + prev.limit,
                    }))
                  }
                >
                  Próximo
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
