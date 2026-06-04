"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2, Clock, FileText, Search } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton, SkeletonLine } from "@/components/ui/skeleton";
import { portalApi } from "@/lib/api";

function fmtPrazo(dias: number): string {
  return dias === 1 ? "até 1 dia" : `até ${dias} dias`;
}

export default function ServicoDetalhePage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const servicoQ = useQuery({
    queryKey: ["portal-servico", slug],
    queryFn: () => portalApi.servico(slug),
  });

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href="/cidadao/servicos"
        className="
          inline-flex items-center gap-1 rounded text-sm text-primary
          hover:underline focus-visible:outline-none focus-visible:ring-2
          focus-visible:ring-ring
        "
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Voltar à Carta de Serviços
      </Link>

      {servicoQ.isLoading && <DetalheSkeleton />}

      {servicoQ.isError && (
        <EmptyState
          icon={Search}
          title="Serviço não encontrado"
          description="Verifique o link ou volte à Carta de Serviços para procurar pelo nome."
          action={
            <Button asChild size="sm">
              <Link href="/cidadao/servicos">Voltar à Carta de Serviços</Link>
            </Button>
          }
        />
      )}

      {servicoQ.data && (
        <Card>
          <CardHeader>
            <div className="flex items-start justify-between gap-2">
              <CardTitle>{servicoQ.data.nome}</CardTitle>
              {servicoQ.data.categoria && (
                <Badge intent="neutral">{servicoQ.data.categoria}</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {servicoQ.data.descricao_detalhada || servicoQ.data.descricao_curta ? (
              <p className="whitespace-pre-wrap text-sm text-foreground">
                {servicoQ.data.descricao_detalhada ?? servicoQ.data.descricao_curta}
              </p>
            ) : null}

            <dl className="space-y-2 text-sm">
              {servicoQ.data.publico_alvo && (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Para quem é este serviço
                  </dt>
                  <dd>{servicoQ.data.publico_alvo}</dd>
                </div>
              )}
              {servicoQ.data.prazo_estimado_dias != null && (
                <div className="flex items-center gap-2 text-foreground-muted">
                  <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>
                    Prazo estimado: {fmtPrazo(servicoQ.data.prazo_estimado_dias)}
                  </span>
                </div>
              )}
              {servicoQ.data.unidade_responsavel && (
                <div className="flex items-center gap-2 text-foreground-muted">
                  <Building2 className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>{servicoQ.data.unidade_responsavel}</span>
                </div>
              )}
            </dl>

            {servicoQ.data.instrucoes_cidadao && (
              <div>
                <h3 className="text-sm font-semibold text-foreground">
                  Como solicitar
                </h3>
                <p className="mt-1 whitespace-pre-wrap text-sm text-foreground-muted">
                  {servicoQ.data.instrucoes_cidadao}
                </p>
              </div>
            )}

            {servicoQ.data.documentos_exigidos &&
              servicoQ.data.documentos_exigidos.length > 0 && (
                <div>
                  <h3 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                    <FileText className="h-4 w-4" aria-hidden="true" />
                    Documentos necessários
                  </h3>
                  <ul className="mt-1 list-inside list-disc text-sm text-foreground-muted">
                    {servicoQ.data.documentos_exigidos.map((d, i) => (
                      <li key={i}>
                        {d.nome}
                        {d.obrigatorio && (
                          <abbr
                            title="Documento obrigatório"
                            className="ml-0.5 text-danger no-underline"
                          >
                            *
                          </abbr>
                        )}
                        {d.descricao && (
                          <span className="text-foreground-subtle"> — {d.descricao}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                  {servicoQ.data.documentos_exigidos.some((d) => d.obrigatorio) && (
                    <p className="mt-1 text-[10px] text-foreground-subtle">
                      <span className="text-danger">*</span> obrigatório
                    </p>
                  )}
                </div>
              )}

            {!servicoQ.data.solicitar_habilitado && (
              <div
                role="status"
                className="rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground"
              >
                O atendimento online deste serviço está pausado pela prefeitura no
                momento. Acompanhe ou abra uma nova solicitação em outro momento.
              </div>
            )}

            {/* Botão sticky-on-mobile: o cidadão sempre vê o CTA mesmo
                rolando textos longos. Em ≥sm volta a ser um botão normal
                no fluxo. */}
            <div
              className="
                sticky bottom-4 z-10 -mx-4 mt-4 border-t border-border bg-card/95
                px-4 py-3 backdrop-blur
                sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:p-0
                sm:backdrop-blur-none
              "
            >
              {servicoQ.data.solicitar_habilitado ? (
                <Button
                  onClick={() => router.push(`/cidadao/servicos/${slug}/solicitar`)}
                  className="w-full sm:w-auto"
                >
                  Solicitar serviço
                </Button>
              ) : (
                <Button
                  disabled
                  className="w-full sm:w-auto"
                  title="O atendimento online deste serviço está pausado pela prefeitura."
                >
                  Solicitação indisponível
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function DetalheSkeleton() {
  return (
    <Card>
      <CardHeader>
        <SkeletonLine width="65%" className="h-6" />
      </CardHeader>
      <CardContent className="space-y-4">
        <SkeletonLine width="100%" className="h-3" />
        <SkeletonLine width="90%" className="h-3" />
        <SkeletonLine width="80%" className="h-3" />
        <div className="space-y-2">
          <SkeletonLine width="40%" className="h-3" />
          <SkeletonLine width="50%" className="h-3" />
          <SkeletonLine width="45%" className="h-3" />
        </div>
        <Skeleton className="h-9 w-40" />
      </CardContent>
    </Card>
  );
}
