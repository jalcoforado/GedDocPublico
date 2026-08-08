"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle, Gavel, Reply } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type DebitoOut } from "@/lib/api";
import { FilaSecao } from "@/components/pagamentos/FilaSecao";

export default function AutoridadePage() {
  // Listar débitos aguardando autoridade
  const listQ = useQuery({
    queryKey: ["pag-solicitacoes-autoridade"],
    queryFn: async () => {
      const debitos = await api.pagamentos.debitos.list();
      return (debitos as DebitoOut[]).filter((d) =>
        ["AGUARDANDO_AUTORIDADE", "AJUSTE_AUTORIDADE"].includes(d.situacao_tramitacao)
      );
    },
  });

  const debitos = (listQ.data ?? []) as DebitoOut[];
  const aguardandoAutoridade = debitos.filter(
    (d) => d.situacao_tramitacao === "AGUARDANDO_AUTORIDADE"
  );
  const ajusteAutoridade = debitos.filter(
    (d) => d.situacao_tramitacao === "AJUSTE_AUTORIDADE"
  );

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[
          { label: "Pagamentos", href: "/m/pagamentos" },
          { label: "Solicitações", href: "/m/pagamentos/solicitacoes" },
        ]}
        title="Fila da Autoridade"
        description="Solicitações aguardando aprovação final"
        icon={Gavel}
      />

      <div className="grid grid-cols-2 gap-3">
        <KpiCard label="Aguardando aprovação" value={aguardandoAutoridade.length} icon={Gavel} />
        <KpiCard label="Aguardando ajustes" value={ajusteAutoridade.length} icon={Reply} intent="warning" />
      </div>

      {listQ.isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {!listQ.isLoading && debitos.length === 0 && (
        <EmptyState
          icon={CheckCircle}
          title="Nenhuma solicitação aguardando sua aprovação"
          description="A fila da autoridade está em dia."
        />
      )}

      <FilaSecao
        titulo="Aguardando sua aprovação"
        icon={Gavel}
        itens={aguardandoAutoridade}
        acaoLabel="Aprovar"
      />
      <FilaSecao
        titulo="Aguardando ajustes da unidade"
        icon={Reply}
        itens={ajusteAutoridade}
        acaoLabel="Ver"
      />
    </div>
  );
}
