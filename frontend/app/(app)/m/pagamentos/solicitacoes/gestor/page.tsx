"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle, Reply, Users } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type DebitoOut } from "@/lib/api";
import { FilaSecao } from "@/components/pagamentos/FilaSecao";

export default function GestorPage() {
  // Listar débitos aguardando gestor
  const listQ = useQuery({
    queryKey: ["pag-solicitacoes-gestor"],
    queryFn: async () => {
      const debitos = await api.pagamentos.debitos.list();
      return (debitos as DebitoOut[]).filter((d) =>
        ["AGUARDANDO_GESTOR", "AJUSTE_GESTOR"].includes(d.situacao_tramitacao)
      );
    },
  });

  const debitos = (listQ.data ?? []) as DebitoOut[];
  const aguardandoGestor = debitos.filter((d) => d.situacao_tramitacao === "AGUARDANDO_GESTOR");
  const ajusteGestor = debitos.filter((d) => d.situacao_tramitacao === "AJUSTE_GESTOR");

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[
          { label: "Pagamentos", href: "/m/pagamentos" },
          { label: "Solicitações", href: "/m/pagamentos/solicitacoes" },
        ]}
        title="Fila do Gestor"
        description="Solicitações aguardando sua decisão"
        icon={Users}
      />

      <div className="grid grid-cols-2 gap-3">
        <KpiCard label="Aguardando decisão" value={aguardandoGestor.length} icon={Users} />
        <KpiCard label="Aguardando ajustes" value={ajusteGestor.length} icon={Reply} intent="warning" />
      </div>

      {listQ.isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {!listQ.isLoading && debitos.length === 0 && (
        <EmptyState
          icon={CheckCircle}
          title="Nenhuma solicitação aguardando sua ação"
          description="A fila do gestor está em dia."
        />
      )}

      <FilaSecao
        titulo="Aguardando sua decisão"
        icon={Users}
        itens={aguardandoGestor}
        acaoLabel="Analisar"
      />
      <FilaSecao
        titulo="Aguardando ajustes da unidade"
        icon={Reply}
        itens={ajusteGestor}
        acaoLabel="Ver"
      />
    </div>
  );
}
