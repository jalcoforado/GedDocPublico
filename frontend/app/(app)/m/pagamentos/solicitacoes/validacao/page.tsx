"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle, Reply, ShieldCheck } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type DebitoOut } from "@/lib/api";
import { FilaSecao } from "@/components/pagamentos/FilaSecao";

export default function ValidacaoPage() {
  // Listar débitos aguardando validação
  const listQ = useQuery({
    queryKey: ["pag-solicitacoes-validacao"],
    queryFn: async () => {
      const debitos = await api.pagamentos.debitos.list();
      return (debitos as DebitoOut[]).filter((d) =>
        ["AGUARDANDO_VALIDACAO", "AJUSTE_VALIDACAO"].includes(d.situacao_tramitacao)
      );
    },
  });

  const debitos = (listQ.data ?? []) as DebitoOut[];
  const aguardandoValidacao = debitos.filter((d) => d.situacao_tramitacao === "AGUARDANDO_VALIDACAO");
  const ajusteValidacao = debitos.filter((d) => d.situacao_tramitacao === "AJUSTE_VALIDACAO");

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[
          { label: "Pagamentos", href: "/m/pagamentos" },
          { label: "Solicitações", href: "/m/pagamentos/solicitacoes" },
        ]}
        title="Fila de Validação"
        description="Solicitações aguardando validação financeira"
        icon={ShieldCheck}
      />

      <div className="grid grid-cols-2 gap-3">
        <KpiCard label="Aguardando validação" value={aguardandoValidacao.length} icon={ShieldCheck} />
        <KpiCard label="Aguardando ajustes" value={ajusteValidacao.length} icon={Reply} intent="warning" />
      </div>

      {listQ.isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {!listQ.isLoading && debitos.length === 0 && (
        <EmptyState
          icon={CheckCircle}
          title="Nenhuma solicitação aguardando validação"
          description="A fila de validação está em dia."
        />
      )}

      <FilaSecao
        titulo="Aguardando validação"
        icon={ShieldCheck}
        itens={aguardandoValidacao}
        acaoLabel="Validar"
      />
      <FilaSecao
        titulo="Aguardando ajustes da unidade"
        icon={Reply}
        itens={ajusteValidacao}
        acaoLabel="Ver"
      />
    </div>
  );
}
