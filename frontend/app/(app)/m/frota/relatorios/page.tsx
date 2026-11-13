"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  AlertTriangle,
  BarChart3,
  Calculator,
  Car,
  CheckCircle2,
  ClipboardList,
  Droplets,
  FileClock,
  FileX,
  Fuel,
  KeyRound,
  Send,
  ThumbsUp,
  Wallet,
  Wrench,
} from "lucide-react";
import { useMemo } from "react";

import { fmtLitros } from "@/components/frota/rotulos";
import { fmtMoeda } from "@/components/pagamentos/format";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { api } from "@/lib/api";

const GRADE = "grid grid-cols-2 gap-3 lg:grid-cols-4";

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
        breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Visão gerencial" }]}
      />

      <SectionCard icon={Car} title="Veículos" description="Situação atual da frota.">
        <div className={GRADE}>
          <KpiCard label="Total de veículos" value={veiculos.total} icon={Car} />
          <KpiCard label="Disponíveis" value={veiculos.disponiveis} icon={CheckCircle2} intent="success" />
          <KpiCard label="Em uso" value={veiculos.em_uso} icon={KeyRound} intent="info" />
          <KpiCard
            label="Em manutenção"
            value={veiculos.manutencao}
            icon={Wrench}
            intent={veiculos.manutencao > 0 ? "warning" : "default"}
          />
        </div>
      </SectionCard>

      <SectionCard icon={ClipboardList} title="Solicitações" description="Pedidos de uso por status.">
        <div className={GRADE}>
          <KpiCard
            label="Aguardando aprovação"
            value={solicitacoes.solicitada}
            icon={Send}
            intent={solicitacoes.solicitada > 0 ? "warning" : "default"}
          />
          <KpiCard label="Aprovadas" value={solicitacoes.aprovada} icon={ThumbsUp} intent="info" />
          <KpiCard label="Em uso" value={solicitacoes.em_uso} icon={KeyRound} intent="info" />
          <KpiCard label="Concluídas" value={solicitacoes.concluida} icon={CheckCircle2} intent="success" />
        </div>
      </SectionCard>

      <SectionCard
        icon={AlertTriangle}
        title="Pendências operacionais"
        description="Itens que exigem atenção."
      >
        <div className={GRADE}>
          <KpiCard
            label="Documentos vencidos"
            value={vencidos}
            icon={FileX}
            intent={vencidos > 0 ? "danger" : "default"}
          />
          <KpiCard
            label="Documentos a vencer"
            value={aVencer}
            hint="nos próximos 30 dias"
            icon={FileClock}
            intent={aVencer > 0 ? "warning" : "default"}
          />
          <KpiCard
            label="Manutenções abertas"
            value={manutencoesAbertas}
            icon={Wrench}
            intent={manutencoesAbertas > 0 ? "warning" : "default"}
          />
          <KpiCard
            label="Ocorrências abertas"
            value={ocorrenciasAbertas}
            icon={AlertOctagon}
            intent={ocorrenciasAbertas > 0 ? "warning" : "default"}
          />
        </div>
      </SectionCard>

      <SectionCard
        icon={Fuel}
        title="Abastecimentos"
        description="Consolidado de abastecimentos registrados."
      >
        <div className={GRADE}>
          <KpiCard label="Abastecimentos" value={abast?.total_abastecimentos ?? 0} icon={Fuel} />
          <KpiCard label="Litros (total)" value={fmtLitros(abast?.total_litros ?? 0)} icon={Droplets} />
          <KpiCard label="Custo total" value={fmtMoeda(abast?.total_valor ?? 0)} icon={Wallet} />
          <KpiCard
            label="Média por litro"
            value={abast?.media_valor_litro != null ? fmtMoeda(abast.media_valor_litro) : "—"}
            icon={Calculator}
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
