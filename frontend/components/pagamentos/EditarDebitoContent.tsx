"use client";

import { useQuery } from "@tanstack/react-query";
import { FileEdit } from "lucide-react";
import Link from "next/link";

import { FormularioDebito } from "@/components/pagamentos/FormularioDebito";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type SituacaoTramitacao } from "@/lib/api";

/** Etapas em que o backend aceita edição — espelha `atualizar_debito`. */
export const TRAMITACOES_EDITAVEIS: SituacaoTramitacao[] = [
  "RASCUNHO", "AJUSTE_GESTOR", "AJUSTE_VALIDACAO", "AJUSTE_AUTORIDADE",
];

/**
 * Edição da solicitação de pagamento. Extraído da rota pelo mesmo motivo do
 * `DetalheDebitoContent`: o `use(params)` não se resolve de forma confiável em
 * teste isolado.
 */
export function EditarDebitoContent({ id }: { id: number }) {
  // Chave própria, e não a do detalhe: o formulário é semeado uma vez com o
  // que vier daqui, e não pode ser alimentado por um dado em cache já velho.
  const q = useQuery({
    queryKey: ["pag-debito-edicao", id],
    queryFn: () => api.pagamentos.debitos.get(id),
    gcTime: 0,
  });
  const detalhe = `/m/pagamentos/solicitacoes/${id}`;
  const breadcrumbs = [
    { label: "Pagamentos", href: "/m/pagamentos" },
    { label: "Solicitações", href: "/m/pagamentos/solicitacoes" },
    { label: `Solicitação #${id}`, href: detalhe },
  ];
  const debito = q.data;

  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={breadcrumbs}
        title={`Editar solicitação #${id}`}
        description={debito?.nome_fornecedor}
        icon={FileEdit}
      />
      {q.isLoading ? (
        <Skeleton className="h-96 w-full max-w-2xl" />
      ) : !debito ? (
        <EmptyState
          icon={FileEdit}
          title="Solicitação não encontrada"
          description="Ela pode ter sido removida, ou o número informado está incorreto."
        />
      ) : !TRAMITACOES_EDITAVEIS.includes(debito.situacao_tramitacao) ? (
        <EmptyState
          icon={FileEdit}
          title="Esta solicitação não pode mais ser editada"
          description="Só é possível editar enquanto ela está em rascunho ou devolvida para ajuste."
          action={
            <Button asChild variant="secondary">
              <Link href={detalhe}>Voltar para a solicitação</Link>
            </Button>
          }
        />
      ) : (
        <FormularioDebito debito={debito} />
      )}
    </div>
  );
}
