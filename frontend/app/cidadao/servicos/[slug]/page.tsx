"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2, Clock, ListChecks, Search, Users } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { ListaDocumentos } from "@/components/cidadao/ListaDocumentos";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton, SkeletonLine } from "@/components/ui/skeleton";
import { portalApi } from "@/lib/api";

function fmtPrazo(dias: number): string {
  return dias === 1 ? "até 1 dia" : `até ${dias} dias`;
}

function Info({
  icon: Icon,
  rotulo,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  rotulo: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3">
      <span
        aria-hidden="true"
        className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-foreground-muted"
      >
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <dt className="text-xs font-medium text-foreground-muted">{rotulo}</dt>
        <dd className="text-sm text-foreground">{children}</dd>
      </div>
    </div>
  );
}

export default function ServicoDetalhePage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const servicoQ = useQuery({
    queryKey: ["portal-servico", slug],
    queryFn: () => portalApi.servico(slug),
  });
  const s = servicoQ.data;
  // A descrição curta vai no cabeçalho; a detalhada, no corpo — sem repetir.
  const corpo = s?.descricao_detalhada && s.descricao_detalhada !== s.descricao_curta ? s.descricao_detalhada : null;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href="/cidadao/servicos"
        className="inline-flex min-h-9 items-center gap-1 rounded text-sm text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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

      {s && (
        <>
          <PageHeader
            icon={ListChecks}
            title={s.nome}
            description={s.descricao_curta ?? undefined}
            actions={s.categoria ? <Badge intent="neutral">{s.categoria}</Badge> : undefined}
          />

          <Card>
            <CardContent className="space-y-5 pt-4 sm:pt-[var(--density-space)]">
              {corpo && <p className="whitespace-pre-wrap text-sm text-foreground">{corpo}</p>}

              {(s.publico_alvo || s.prazo_estimado_dias != null || s.unidade_responsavel) && (
                <dl className="grid gap-4 sm:grid-cols-2">
                  {s.publico_alvo && (
                    <Info icon={Users} rotulo="Para quem é este serviço">
                      {s.publico_alvo}
                    </Info>
                  )}
                  {s.prazo_estimado_dias != null && (
                    <Info icon={Clock} rotulo="Quanto tempo costuma levar">
                      Prazo estimado: {fmtPrazo(s.prazo_estimado_dias)}
                    </Info>
                  )}
                  {s.unidade_responsavel && (
                    <Info icon={Building2} rotulo="Quem atende">
                      {s.unidade_responsavel}
                    </Info>
                  )}
                </dl>
              )}

              {s.instrucoes_cidadao && (
                <div>
                  <h3 className="text-sm font-semibold text-foreground">Como solicitar</h3>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-foreground-muted">
                    {s.instrucoes_cidadao}
                  </p>
                </div>
              )}

              <ListaDocumentos documentos={s.documentos_exigidos ?? []} />
              {(s.documentos_exigidos?.length ?? 0) > 0 && s.solicitar_habilitado && (
                <p className="-mt-3 text-xs text-foreground-muted">
                  Você anexa os documentos depois de fazer o pedido — pode ser foto tirada pelo celular.
                </p>
              )}

              {!s.solicitar_habilitado && (
                <Alert intent="warning">
                  O atendimento online deste serviço está pausado pela prefeitura no momento. Acompanhe
                  ou abra uma nova solicitação em outro momento.
                </Alert>
              )}
            </CardContent>
          </Card>

          {/* Botão fixo no celular: o cidadão sempre vê o "Solicitar" mesmo
              rolando textos longos; sobe pela barra de baixo do portal
              (`--barra-inferior`). Em ≥sm volta a ser um botão no fluxo. */}
          <div
            className="
              sticky bottom-[var(--barra-inferior,0px)] z-10 -mx-4 border-t border-border bg-card/95
              px-4 py-3 backdrop-blur
              sm:static sm:mx-0 sm:border-0 sm:bg-transparent sm:p-0
              sm:backdrop-blur-none
            "
          >
            {s.solicitar_habilitado ? (
              <Button
                onClick={() => router.push(`/cidadao/servicos/${slug}/solicitar`)}
                size="lg"
                className="w-full sm:w-auto"
              >
                Solicitar serviço
              </Button>
            ) : (
              <Button
                disabled
                size="lg"
                className="w-full sm:w-auto"
                title="O atendimento online deste serviço está pausado pela prefeitura."
              >
                Solicitação indisponível
              </Button>
            )}
          </div>
        </>
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
        <Skeleton className="h-11 w-40" />
      </CardContent>
    </Card>
  );
}
