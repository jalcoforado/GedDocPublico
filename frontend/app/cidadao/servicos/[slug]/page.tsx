"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2, Clock, FileText, Loader2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { portalApi } from "@/lib/api";

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
        className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
      >
        <ArrowLeft className="h-4 w-4" />
        Voltar à Carta de Serviços
      </Link>

      {servicoQ.isLoading && (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
          Carregando…
        </p>
      )}

      {servicoQ.isError && (
        <p className="rounded-lg border border-border bg-card px-4 py-6 text-center text-sm text-muted-foreground">
          Serviço não encontrado.
        </p>
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
                    Público-alvo
                  </dt>
                  <dd>{servicoQ.data.publico_alvo}</dd>
                </div>
              )}
              {servicoQ.data.prazo_estimado_dias != null && (
                <div className="flex items-center gap-2 text-foreground-muted">
                  <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>Prazo estimado: {servicoQ.data.prazo_estimado_dias} dia(s)</span>
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
                <h3 className="text-sm font-semibold text-foreground">Instruções</h3>
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
                    Documentos exigidos
                  </h3>
                  <ul className="mt-1 list-inside list-disc text-sm text-foreground-muted">
                    {servicoQ.data.documentos_exigidos.map((d, i) => (
                      <li key={i}>
                        {d.nome}
                        {d.obrigatorio && <span className="text-danger"> *</span>}
                        {d.descricao && (
                          <span className="text-foreground-subtle"> — {d.descricao}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

            <div className="pt-2">
              {servicoQ.data.solicitar_habilitado ? (
                <Button onClick={() => router.push(`/cidadao/servicos/${slug}/solicitar`)}>
                  Solicitar serviço
                </Button>
              ) : (
                <Button disabled title="Solicitação indisponível">
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
