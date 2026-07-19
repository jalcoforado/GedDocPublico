"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, History } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
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

const ACTION_COLORS: Record<string, string> = {
  "alvara.criada": "bg-blue-100 text-blue-800",
  "alvara.editada": "bg-yellow-100 text-yellow-800",
  "alvara.renovada": "bg-green-100 text-green-800",
  "alvara.finalizada": "bg-purple-100 text-purple-800",
  "alvara.excluida": "bg-red-100 text-red-800",
  "alvara.responsavel_adicionado": "bg-cyan-100 text-cyan-800",
  "alvara.responsavel_removido": "bg-orange-100 text-orange-800",
  "alvara.documento_adicionado": "bg-indigo-100 text-indigo-800",
  "alvara.documento_removido": "bg-pink-100 text-pink-800",
  "alvara.veiculo_vinculado": "bg-teal-100 text-teal-800",
  "alvara.veiculo_desvinculado": "bg-amber-100 text-amber-800",
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
        <div className="rounded bg-red-50 p-2">
          <p className="font-semibold text-red-800">Antes:</p>
          <pre className="whitespace-pre-wrap break-words text-red-700">
            {JSON.stringify(antes, null, 2)}
          </pre>
        </div>
      )}
      {depois && (
        <div className="rounded bg-green-50 p-2">
          <p className="font-semibold text-green-800">Depois:</p>
          <pre className="whitespace-pre-wrap break-words text-green-700">
            {JSON.stringify(depois, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default function AlvaraDetailPage({ params }: PageParams) {
  const router = useRouter();
  const [resolvedParams, setResolvedParams] = useState<{ id: string } | null>(
    null,
  );
  const [page, setPage] = useState(0);
  const LIMIT = 20;

  // Resolve params
  if (!resolvedParams) {
    params.then((p) => setResolvedParams(p));
    return <div>Carregando...</div>;
  }

  const alvaraId = parseInt(resolvedParams.id, 10);

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
    return <div className="p-6 text-center">Carregando alvará...</div>;
  }

  if (!alvara) {
    return (
      <div className="p-6 text-center text-red-600">
        Alvará não encontrado
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.back()}
          className="gap-2"
        >
          <ChevronLeft className="h-4 w-4" />
          Voltar
        </Button>
      </div>

      <PageHeader
        title={`Alvará ${alvara.numero_alvara}`}
        description={`ID: ${alvara.id} • Criado em ${formatDate(alvara.criado_em)}`}
      />

      {/* Informações do Alvará */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h3 className="mb-4 text-lg font-semibold">Informações Básicas</h3>
          <dl className="space-y-3">
            <div>
              <dt className="text-sm font-medium text-gray-600">Número</dt>
              <dd className="text-base text-gray-900">{alvara.numero_alvara}</dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-600">
                Tipo de Serviço
              </dt>
              <dd className="text-base text-gray-900">
                {alvara.tipo_servico}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-600">Data Início</dt>
              <dd className="text-base text-gray-900">
                {alvara.data_inicio
                  ? new Date(alvara.data_inicio).toLocaleDateString("pt-BR")
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-600">Validade</dt>
              <dd className="text-base text-gray-900">
                {alvara.data_validade
                  ? new Date(alvara.data_validade).toLocaleDateString("pt-BR")
                  : "Indefinido"}
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <h3 className="mb-4 text-lg font-semibold">Relacionamentos</h3>
          <dl className="space-y-3">
            <div>
              <dt className="text-sm font-medium text-gray-600">
                Permissionário
              </dt>
              <dd className="text-base text-gray-900">
                {alvara.id_permissionario ? `ID: ${alvara.id_permissionario}` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-600">Empresa</dt>
              <dd className="text-base text-gray-900">
                {alvara.id_empresa ? `ID: ${alvara.id_empresa}` : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-sm font-medium text-gray-600">
                Renovado De
              </dt>
              <dd className="text-base text-gray-900">
                {alvara.renovado_de ? `Alvará ${alvara.renovado_de}` : "Original"}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Histórico de Auditoria */}
      <div className="rounded-lg border bg-white shadow-sm">
        <div className="border-b px-6 py-4">
          <div className="flex items-center gap-2">
            <History className="h-5 w-5" />
            <h3 className="text-lg font-semibold">Histórico de Auditoria</h3>
          </div>
        </div>

        {auditoriaLoading ? (
          <div className="p-6 text-center text-gray-600">
            Carregando histórico...
          </div>
        ) : !auditoria || auditoria.eventos.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon="inbox"
              title="Nenhum evento de auditoria"
              description="Nenhuma alteração registrada ainda"
            />
          </div>
        ) : (
          <>
            <div className="divide-y">
              {auditoria.eventos.map((evento) => (
                <div key={evento.id} className="px-6 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="mb-2 flex items-center gap-2">
                        <Badge
                          className={
                            ACTION_COLORS[evento.acao] ||
                            "bg-gray-100 text-gray-800"
                          }
                        >
                          {ACTION_LABELS[evento.acao] || evento.acao}
                        </Badge>
                        <span className="text-xs text-gray-600">
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
              <div className="border-t px-6 py-4 flex items-center justify-between">
                <div className="text-sm text-gray-600">
                  Total: {auditoria.total} eventos
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 0}
                    onClick={() => setPage(Math.max(0, page - 1))}
                  >
                    Anterior
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={(page + 1) * LIMIT >= (auditoria.total || 0)}
                    onClick={() => setPage(page + 1)}
                  >
                    Próximo
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
