"use client";

import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { useMemo } from "react";

import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { api } from "@/lib/api";

function fmtMoeda(v: number): string {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function Stat({
  label,
  value,
  intent,
}: {
  label: string;
  value: string | number;
  intent?: "danger" | "warning" | "success";
}) {
  const cls =
    intent === "danger"
      ? "text-danger-soft-foreground"
      : intent === "warning"
        ? "text-warning-soft-foreground"
        : intent === "success"
          ? "text-success-soft-foreground"
          : "text-foreground";
  return (
    <div className="rounded-lg border border-border bg-surface-1 p-4">
      <p className="text-sm text-foreground-muted">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${cls}`}>{value}</p>
    </div>
  );
}

export default function RelatoriosFrotaPage() {
  // Visão gerencial: agrega dados das APIs já existentes (sem backend novo).
  const veiculosQ = useQuery({ queryKey: ["frota-veiculos"], queryFn: () => api.frota.listAll() });
  const solicitacoesQ = useQuery({ queryKey: ["frota-solicitacoes"], queryFn: () => api.solicitacoes.listAll() });
  const alertasQ = useQuery({ queryKey: ["frota-documentos-alertas"], queryFn: () => api.documentosVeiculo.alertas(30) });
  const manutQ = useQuery({ queryKey: ["frota-manutencoes-all"], queryFn: () => api.manutencoes.list() });
  const ocorrenciasQ = useQuery({ queryKey: ["frota-ocorrencias-all"], queryFn: () => api.ocorrencias.list() });
  const abastResumoQ = useQuery({ queryKey: ["frota-abast-resumo"], queryFn: () => api.abastecimentos.resumo() });

  const veiculos = useMemo(() => {
    const all = veiculosQ.data ?? [];
    const porSituacao = (s: string) => all.filter((v) => v.situacao === s).length;
    return {
      total: all.length,
      disponiveis: porSituacao("disponivel"),
      em_uso: porSituacao("em_uso"),
      manutencao: porSituacao("manutencao"),
    };
  }, [veiculosQ.data]);

  const solicitacoes = useMemo(() => {
    const all = solicitacoesQ.data ?? [];
    const por = (s: string) => all.filter((x) => x.status === s).length;
    return {
      solicitada: por("solicitada"),
      aprovada: por("aprovada"),
      em_uso: por("em_uso"),
      concluida: por("concluida"),
    };
  }, [solicitacoesQ.data]);

  const manutencoesAbertas = useMemo(
    () => (manutQ.data ?? []).filter((m) => m.status === "aberta" || m.status === "em_andamento").length,
    [manutQ.data],
  );
  const ocorrenciasAbertas = useMemo(
    () => (ocorrenciasQ.data ?? []).filter((o) => o.status === "aberta" || o.status === "em_tratamento").length,
    [ocorrenciasQ.data],
  );

  const vencidos = alertasQ.data?.vencidos.length ?? 0;
  const aVencer = alertasQ.data?.a_vencer.length ?? 0;
  const abast = abastResumoQ.data;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={BarChart3}
        title="Visão gerencial"
        description="Indicadores operacionais consolidados da frota."
        breadcrumbs={[{ label: "Frota Pública", href: "/frotas" }, { label: "Visão gerencial" }]}
      />

      <SectionCard icon={BarChart3} title="Veículos" description="Situação atual da frota.">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Total de veículos" value={veiculos.total} />
          <Stat label="Disponíveis" value={veiculos.disponiveis} intent="success" />
          <Stat label="Em uso" value={veiculos.em_uso} />
          <Stat label="Em manutenção" value={veiculos.manutencao} intent="warning" />
        </div>
      </SectionCard>

      <SectionCard icon={BarChart3} title="Solicitações" description="Pedidos de uso por status.">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Solicitadas" value={solicitacoes.solicitada} />
          <Stat label="Aprovadas" value={solicitacoes.aprovada} />
          <Stat label="Em uso" value={solicitacoes.em_uso} />
          <Stat label="Concluídas" value={solicitacoes.concluida} intent="success" />
        </div>
      </SectionCard>

      <SectionCard
        icon={BarChart3}
        title="Pendências operacionais"
        description="Itens que exigem atenção."
      >
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Documentos vencidos" value={vencidos} intent={vencidos > 0 ? "danger" : undefined} />
          <Stat label="Documentos a vencer (30d)" value={aVencer} intent={aVencer > 0 ? "warning" : undefined} />
          <Stat label="Manutenções abertas" value={manutencoesAbertas} intent={manutencoesAbertas > 0 ? "warning" : undefined} />
          <Stat label="Ocorrências abertas" value={ocorrenciasAbertas} intent={ocorrenciasAbertas > 0 ? "warning" : undefined} />
        </div>
      </SectionCard>

      <SectionCard
        icon={BarChart3}
        title="Abastecimentos"
        description="Consolidado de abastecimentos registrados."
      >
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Abastecimentos" value={abast?.total_abastecimentos ?? 0} />
          <Stat label="Litros (total)" value={(abast?.total_litros ?? 0).toLocaleString("pt-BR")} />
          <Stat label="Custo total" value={fmtMoeda(abast?.total_valor ?? 0)} />
          <Stat
            label="Média R$/litro"
            value={abast?.media_valor_litro != null ? fmtMoeda(abast.media_valor_litro) : "—"}
          />
        </div>
        <p className="mt-3 text-xs text-foreground-muted">
          Quilometragem rodada por período depende do histórico de odômetro e será detalhada em uma
          evolução futura desta visão.
        </p>
      </SectionCard>
    </div>
  );
}
