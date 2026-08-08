"use client";

import { useQuery } from "@tanstack/react-query";
import { Ban, CheckCircle2, History, ThumbsDown, X } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type DebitoOut } from "@/lib/api";
import { FilaSecao } from "@/components/pagamentos/FilaSecao";

export default function ConcluidasPage() {
  // Listar débitos concluídos
  const listQ = useQuery({
    queryKey: ["pag-solicitacoes-concluidas"],
    queryFn: async () => {
      const debitos = await api.pagamentos.debitos.list();
      return (debitos as DebitoOut[]).filter((d) =>
        ["AUTORIZADA", "REJEITADA_GESTOR", "INDEFERIDA_AUTORIDADE", "CANCELADA"].includes(
          d.situacao_tramitacao
        )
      );
    },
  });

  const debitos = (listQ.data ?? []) as DebitoOut[];
  const autorizadas = debitos.filter((d) => d.situacao_tramitacao === "AUTORIZADA");
  const rejeitadas = debitos.filter((d) => d.situacao_tramitacao === "REJEITADA_GESTOR");
  const indeferidas = debitos.filter(
    (d) => d.situacao_tramitacao === "INDEFERIDA_AUTORIDADE"
  );
  const canceladas = debitos.filter((d) => d.situacao_tramitacao === "CANCELADA");

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[
          { label: "Pagamentos", href: "/m/pagamentos" },
          { label: "Solicitações", href: "/m/pagamentos/solicitacoes" },
        ]}
        title="Solicitações Concluídas"
        description="Histórico de solicitações já finalizadas"
        icon={History}
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiCard label="Autorizadas" value={autorizadas.length} icon={CheckCircle2} intent="success" />
        <KpiCard label="Rejeitadas" value={rejeitadas.length} icon={X} intent="danger" />
        <KpiCard label="Indeferidas" value={indeferidas.length} icon={ThumbsDown} intent="danger" />
        <KpiCard label="Canceladas" value={canceladas.length} icon={Ban} />
      </div>

      {listQ.isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {!listQ.isLoading && debitos.length === 0 && (
        <EmptyState
          icon={History}
          title="Nenhuma solicitação concluída"
          description="Solicitações autorizadas, rejeitadas, indeferidas ou canceladas aparecem aqui."
        />
      )}

      <FilaSecao titulo="Autorizadas" icon={CheckCircle2} itens={autorizadas} acaoLabel="Ver" />
      <FilaSecao titulo="Rejeitadas" icon={X} itens={rejeitadas} acaoLabel="Ver" />
      <FilaSecao titulo="Indeferidas" icon={ThumbsDown} itens={indeferidas} acaoLabel="Ver" />
      <FilaSecao titulo="Canceladas" icon={Ban} itens={canceladas} acaoLabel="Ver" />
    </div>
  );
}
