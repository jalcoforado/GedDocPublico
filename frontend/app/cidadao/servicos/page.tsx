"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, Clock, FileText, Loader2, Star } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { portalApi, type ServicoPublico } from "@/lib/api";

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
          Serviços públicos oferecidos pela prefeitura.
        </p>
      </div>

      {servicosQ.isLoading && (
        <p className="text-sm text-muted-foreground">
          <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
          Carregando serviços…
        </p>
      )}

      {servicosQ.data?.length === 0 && (
        <p className="rounded-lg border border-border bg-card px-4 py-6 text-center text-sm text-muted-foreground">
          Nenhum serviço disponível no momento.
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {servicosQ.data?.map((s) => (
          <ServicoCard key={s.slug} servico={s} />
        ))}
      </div>
    </div>
  );
}

function ServicoCard({ servico: s }: { servico: ServicoPublico }) {
  return (
    <article className="flex flex-col rounded-xl border border-border bg-card p-4 shadow-xs">
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
            <span>Prazo estimado: {s.prazo_estimado_dias} dia(s)</span>
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
            Documentos exigidos
          </div>
          <ul className="mt-1 list-inside list-disc text-sm text-foreground-muted">
            {s.documentos_exigidos.map((d, i) => (
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

      <div className="mt-4 pt-1">
        {/* PR 4a: abertura por serviço é o PR 4b — botão desabilitado. */}
        <Button variant="secondary" size="sm" disabled title="Disponível em breve">
          Solicitação disponível em breve
        </Button>
      </div>
    </article>
  );
}
