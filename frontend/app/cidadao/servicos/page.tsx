"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, Clock, FileText, Search, Star } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton, SkeletonLine } from "@/components/ui/skeleton";
import { portalApi, type ServicoPublico } from "@/lib/api";

function fmtPrazo(dias: number): string {
  return dias === 1 ? "até 1 dia" : `até ${dias} dias`;
}

function temAlgumObrigatorio(s: ServicoPublico): boolean {
  return (s.documentos_exigidos ?? []).some((d) => d.obrigatorio);
}

export default function ServicosPublicosPage() {
  const servicosQ = useQuery({
    queryKey: ["portal-servicos"],
    queryFn: () => portalApi.servicos(),
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-primary">Carta de Serviços</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Conheça os serviços públicos disponíveis e solicite o que precisar.
        </p>
      </div>

      {servicosQ.isLoading && (
        <div
          className="grid grid-cols-1 gap-4 sm:grid-cols-2"
          data-testid="servicos-loading"
        >
          {Array.from({ length: 4 }).map((_, i) => (
            <ServicoCardSkeleton key={i} />
          ))}
        </div>
      )}

      {servicosQ.data?.length === 0 && (
        <EmptyState
          icon={Search}
          title="Nenhum serviço disponível no momento"
          description="A prefeitura ainda não publicou serviços para solicitação online. Tente novamente em breve."
        />
      )}

      {servicosQ.data && servicosQ.data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {servicosQ.data.map((s) => (
            <ServicoCard key={s.slug} servico={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function ServicoCardSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-xs">
      <SkeletonLine width="60%" className="h-5" />
      <SkeletonLine width="35%" className="mt-2 h-3" />
      <SkeletonLine width="80%" className="mt-3 h-3" />
      <SkeletonLine width="50%" className="mt-1.5 h-3" />
      <Skeleton className="mt-4 h-9 w-32" />
    </div>
  );
}

function ServicoCard({ servico: s }: { servico: ServicoPublico }) {
  const algumObrigatorio = temAlgumObrigatorio(s);
  return (
    <article
      className="
        flex flex-col rounded-xl border border-border bg-card p-4 shadow-xs
        transition-all duration-fast
        hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md
      "
    >
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-base font-semibold text-foreground">{s.nome}</h2>
        {s.destaque && (
          <Badge intent="brand" icon={Star}>
            Destaque
          </Badge>
        )}
      </div>

      {s.categoria && (
        <span className="mt-1 text-xs font-medium uppercase tracking-wide text-foreground-subtle">
          {s.categoria}
        </span>
      )}

      {s.descricao_curta && (
        <p className="mt-2 text-sm text-foreground-muted">{s.descricao_curta}</p>
      )}

      <dl className="mt-3 space-y-1.5 text-sm">
        {s.prazo_estimado_dias != null && (
          <div className="flex items-center gap-2 text-foreground-muted">
            <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>Prazo estimado: {fmtPrazo(s.prazo_estimado_dias)}</span>
          </div>
        )}
        {s.unidade_responsavel && (
          <div className="flex items-center gap-2 text-foreground-muted">
            <Building2 className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{s.unidade_responsavel}</span>
          </div>
        )}
      </dl>

      {s.documentos_exigidos && s.documentos_exigidos.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
            <FileText className="h-3.5 w-3.5" aria-hidden="true" />
            Documentos necessários
          </div>
          <ul className="mt-1 list-inside list-disc text-sm text-foreground-muted">
            {s.documentos_exigidos.map((d, i) => (
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
          {algumObrigatorio && (
            <p className="mt-1 text-[10px] text-foreground-subtle">
              <span className="text-danger">*</span> obrigatório
            </p>
          )}
        </div>
      )}

      <div className="mt-4 pt-1">
        {s.solicitar_habilitado ? (
          <Button asChild size="sm" className="w-full sm:w-auto">
            <Link href={`/cidadao/servicos/${s.slug}`}>Solicitar serviço</Link>
          </Button>
        ) : (
          <Button
            variant="secondary"
            size="sm"
            disabled
            title="O atendimento online deste serviço está pausado pela prefeitura."
          >
            Solicitação indisponível
          </Button>
        )}
      </div>
    </article>
  );
}
