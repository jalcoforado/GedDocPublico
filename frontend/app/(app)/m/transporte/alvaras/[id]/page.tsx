"use client";

import { Carregando } from "@/components/ui/carregando";

import { useQuery } from "@tanstack/react-query";
import { History, Inbox, Link2, ScrollText, SearchX, Truck } from "lucide-react";
import { use, useState } from "react";

import { fmtData } from "@/components/pagamentos/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { AlvaraVeiculosModal } from "@/components/transporte-regulado/alvara-veiculos-modal";
import { rotuloTipoServico } from "@/components/transporte/rotulos";
import { WorkflowTimeline } from "@/components/transporte/WorkflowTimeline";
import {
  api,
  type Alvara,
  type AlvaraAuditoriaListResponse,
} from "@/lib/api";

interface PageParams {
  params: Promise<{ id: string }>;
}

const ACTION_LABELS: Record<string, string> = {
  "alvara.criada": "Alvará criado",
  "alvara.editada": "Alvará editado",
  "alvara.renovada": "Alvará renovado",
  "alvara.finalizada": "Alvará finalizado",
  "alvara.excluida": "Alvará excluído",
  "alvara.responsavel_adicionado": "Responsável adicionado",
  "alvara.responsavel_removido": "Responsável removido",
  "alvara.documento_adicionado": "Documento adicionado",
  "alvara.documento_removido": "Documento removido",
  "alvara.veiculo_vinculado": "Veículo vinculado",
  "alvara.veiculo_desvinculado": "Veículo desvinculado",
};

const ACTION_INTENTS: Record<
  string,
  "neutral" | "success" | "danger" | "warning" | "info" | "brand"
> = {
  "alvara.criada": "info",
  "alvara.editada": "warning",
  "alvara.renovada": "success",
  "alvara.finalizada": "brand",
  "alvara.excluida": "danger",
  "alvara.responsavel_adicionado": "info",
  "alvara.responsavel_removido": "warning",
  "alvara.documento_adicionado": "brand",
  "alvara.documento_removido": "danger",
  "alvara.veiculo_vinculado": "success",
  "alvara.veiculo_desvinculado": "warning",
};

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function JsonDiff({ antes, depois }: any) {
  return (
    <div className="space-y-2 text-xs">
      {antes && (
        <div className="rounded bg-danger-soft p-2">
          <p className="font-semibold text-danger-soft-foreground">Antes:</p>
          <pre className="whitespace-pre-wrap break-words text-danger-soft-foreground">
            {JSON.stringify(antes, null, 2)}
          </pre>
        </div>
      )}
      {depois && (
        <div className="rounded bg-success-soft p-2">
          <p className="font-semibold text-success-soft-foreground">Depois:</p>
          <pre className="whitespace-pre-wrap break-words text-success-soft-foreground">
            {JSON.stringify(depois, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function AlvaraDetailPage({ params }: PageParams) {
  // `use(params)` e não `params.then(setState)` + retorno antecipado: com o
  // retorno antes dos `useQuery`, o segundo render tinha mais hooks que o
  // primeiro — o React acusa isso como erro.
  const { id } = use(params);
  const alvaraId = parseInt(id, 10);
  const [page, setPage] = useState(0);
  const [showVeiculosModal, setShowVeiculosModal] = useState(false);
  const LIMIT = 20;

  // Alvará
  const { data: alvara, isLoading: alvaraLoading } = useQuery<Alvara>({
    queryKey: [`/transporte-regulado/alvaras/${alvaraId}`],
    queryFn: () => api.alvaras.get(alvaraId),
  });

  // Auditoria
  const { data: auditoria, isLoading: auditoriaLoading } =
    useQuery<AlvaraAuditoriaListResponse>({
      queryKey: [
        `/transporte-regulado/alvaras/${alvaraId}/auditoria`,
        page,
      ],
      queryFn: () =>
        api.alvaras.auditoria.list(alvaraId, {
          limit: LIMIT,
          offset: page * LIMIT,
        }),
    });

  if (alvaraLoading) {
    return <Carregando className="py-8 text-center text-foreground-muted" />;
  }

  if (!alvara) {
    return (
      <EmptyState
        icon={SearchX}
        title="Alvará não encontrado"
        description="Ele pode ter sido excluído. Volte para a lista de alvarás."
      />
    );
  }

  return (
    <div className="space-y-6 pb-8">
      {/* A seta de voltar vem da trilha (Alvarás); o botão "Voltar" solto
          com router.back() saiu. */}
      <PageHeader
        icon={ScrollText}
        title={`Alvará ${alvara.numero_alvara}`}
        description={`${rotuloTipoServico(alvara.tipo_servico)} · cadastrado em ${fmtData(alvara.criado_em)}`}
        breadcrumbs={[
          { label: "Transporte Regulado", href: "/m/transporte" },
          { label: "Alvarás", href: "/m/transporte/alvaras" },
          { label: alvara.numero_alvara },
        ]}
      />

      {/* Informações do Alvará */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <SectionCard title="Dados do alvará" icon={ScrollText}>
          <dl className="space-y-3">
            <div>
              <dt className="text-sm font-medium text-muted-foreground">Número</dt>
              <dd className="font-mono text-base text-foreground">{alvara.numero_alvara}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">Tipo de serviço</dt>
              <dd className="text-base text-foreground">
                {rotuloTipoServico(alvara.tipo_servico)}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">Início</dt>
              <dd className="text-base tabular-nums text-foreground">
                {fmtData(alvara.data_inicio)}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">Validade</dt>
              <dd className="text-base tabular-nums text-foreground">
                {alvara.data_validade ? fmtData(alvara.data_validade) : "Sem validade"}
              </dd>
            </div>
          </dl>
        </SectionCard>

        <SectionCard title="Vínculos" icon={Link2}>
          <dl className="space-y-3">
            <div>
              <dt className="text-sm font-medium text-muted-foreground">Permissionário</dt>
              <dd className="text-base text-foreground">
                {alvara.id_permissionario ? `Nº ${alvara.id_permissionario}` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">Empresa</dt>
              <dd className="text-base text-foreground">
                {alvara.id_empresa ? `Nº ${alvara.id_empresa}` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-muted-foreground">Renovado de</dt>
              <dd className="text-base text-foreground">
                {alvara.renovado_de ? `Alvará ${alvara.renovado_de}` : "Original"}
              </dd>
            </div>
          </dl>
        </SectionCard>
      </div>

      <SectionCard
        title="Veículos vinculados"
        description="Veículos que operam sob este alvará."
        icon={Truck}
      >
        <Button variant="secondary" size="sm" onClick={() => setShowVeiculosModal(true)}>
          <Truck className="mr-1 h-4 w-4" aria-hidden="true" />
          Gerenciar veículos
        </Button>
      </SectionCard>

      {/* Fluxo de trabalho */}
      <WorkflowTimeline entidadeTipo="alvara" entidadeId={alvara.id} />

      {/* Histórico de Auditoria */}
      <section className="rounded-card border border-border bg-card shadow-card">
        <div className="border-b border-border px-6 py-4">
          <div className="flex items-center gap-2">
            <History className="h-5 w-5 text-brand" aria-hidden="true" />
            <h2 className="text-md font-semibold text-foreground">Histórico de auditoria</h2>
          </div>
        </div>

        {auditoriaLoading ? (
          <Carregando className="p-6 text-center text-muted-foreground" />
        ) : !auditoria || auditoria.eventos.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={Inbox}
              title="Nenhum evento de auditoria"
              description="As alterações deste alvará aparecem aqui."
            />
          </div>
        ) : (
          <>
            <div className="divide-y divide-border">
              {auditoria.eventos.map((evento) => (
                <div key={evento.id} className="px-6 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="mb-2 flex items-center gap-2">
                        <Badge intent={ACTION_INTENTS[evento.acao] || "neutral"}>
                          {ACTION_LABELS[evento.acao] || evento.acao}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(evento.criado_em)}
                        </span>
                      </div>

                      {(evento.dados_antigos || evento.dados_novos) && (
                        <JsonDiff
                          antes={evento.dados_antigos}
                          depois={evento.dados_novos}
                        />
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Paginação */}
            {auditoria.total && auditoria.total > LIMIT && (
              <div className="border-t border-border px-6 py-4 flex items-center justify-between">
                <div className="text-sm text-muted-foreground">
                  {auditoria.total} eventos
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={page === 0}
                    onClick={() => setPage(Math.max(0, page - 1))}
                  >
                    Anterior
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={(page + 1) * LIMIT >= (auditoria.total || 0)}
                    onClick={() => setPage(page + 1)}
                  >
                    Próxima
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </section>

      {/* Modal de Veículos */}
      <AlvaraVeiculosModal
        alvaraId={alvaraId}
        open={showVeiculosModal}
        onOpenChange={setShowVeiculosModal}
      />
    </div>
  );
}
