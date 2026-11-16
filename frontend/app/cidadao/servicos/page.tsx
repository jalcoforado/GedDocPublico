"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, Clock, ListChecks, Search, Star, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ListaDocumentos } from "@/components/cidadao/ListaDocumentos";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton, SkeletonLine } from "@/components/ui/skeleton";
import { portalApi, type ServicoPublico } from "@/lib/api";

function fmtPrazo(dias: number): string {
  return dias === 1 ? "até 1 dia" : `até ${dias} dias`;
}

/** Minúsculas e sem acento: "iluminacao" acha "Iluminação". */
function normalizar(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

// Abaixo disso a lista cabe na tela e a busca só ocupa espaço.
const MIN_PARA_BUSCA = 7;

export default function ServicosPublicosPage() {
  const servicosQ = useQuery({
    queryKey: ["portal-servicos"],
    queryFn: () => portalApi.servicos(),
  });
  const [busca, setBusca] = useState("");

  const todos = servicosQ.data ?? [];
  const visiveis = useMemo(() => {
    const q = normalizar(busca.trim());
    if (!q) return todos;
    return todos.filter((s) =>
      normalizar([s.nome, s.categoria, s.descricao_curta].filter(Boolean).join(" ")).includes(q),
    );
  }, [todos, busca]);

  return (
    <div className="space-y-5">
      <PageHeader
        icon={ListChecks}
        title="Carta de Serviços"
        description="O que a prefeitura oferece, o que você precisa levar e quanto tempo costuma levar. Escolha um serviço para pedir."
      />

      {todos.length >= MIN_PARA_BUSCA && (
        <div role="search" className="relative max-w-md">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
            aria-hidden="true"
          />
          <Input
            type="search"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            aria-label="Procurar serviço"
            placeholder="Procure: certidão, alvará, iluminação…"
            className="pl-9 pr-11"
          />
          {busca && (
            <button
              type="button"
              onClick={() => setBusca("")}
              aria-label="Limpar busca"
              className="absolute right-1 top-1/2 inline-flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-md text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      )}

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

      {todos.length > 0 && visiveis.length === 0 && (
        <EmptyState
          icon={Search}
          title={`Nenhum serviço com “${busca.trim()}”`}
          description="Tente outra palavra, ou abra um processo contando o que você precisa."
          action={
            <Button variant="secondary" onClick={() => setBusca("")}>
              Limpar a busca
            </Button>
          }
        />
      )}

      {visiveis.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {visiveis.map((s) => (
            <ServicoCard key={s.slug} servico={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function ServicoCardSkeleton() {
  return (
    <div className="rounded-card border border-border bg-card p-4 shadow-xs">
      <SkeletonLine width="60%" className="h-5" />
      <SkeletonLine width="35%" className="mt-2 h-3" />
      <SkeletonLine width="80%" className="mt-3 h-3" />
      <SkeletonLine width="50%" className="mt-1.5 h-3" />
      <Skeleton className="mt-4 h-11 w-full sm:w-36" />
    </div>
  );
}

function ServicoCard({ servico: s }: { servico: ServicoPublico }) {
  return (
    <article
      className="
        flex flex-col rounded-card border border-border bg-card p-4 shadow-xs
        transition-[border-color,box-shadow] duration-fast
        hover:border-border-strong hover:shadow-md
      "
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          {s.categoria && (
            <p className="text-xs font-medium uppercase tracking-wide text-foreground-subtle">
              {s.categoria}
            </p>
          )}
          <h2 className="text-base font-semibold text-foreground">{s.nome}</h2>
        </div>
        {s.destaque && (
          <Badge intent="brand" icon={Star}>
            Destaque
          </Badge>
        )}
      </div>

      {s.descricao_curta && (
        <p className="mt-2 text-sm text-foreground-muted">{s.descricao_curta}</p>
      )}

      {(s.prazo_estimado_dias != null || s.unidade_responsavel) && (
        <dl className="mt-3 space-y-1.5 text-sm">
          {s.prazo_estimado_dias != null && (
            <div className="flex items-center gap-2 text-foreground-muted">
              <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
              <dt className="sr-only">Prazo</dt>
              <dd>Prazo estimado: {fmtPrazo(s.prazo_estimado_dias)}</dd>
            </div>
          )}
          {s.unidade_responsavel && (
            <div className="flex items-center gap-2 text-foreground-muted">
              <Building2 className="h-4 w-4 shrink-0" aria-hidden="true" />
              <dt className="sr-only">Quem atende</dt>
              <dd>{s.unidade_responsavel}</dd>
            </div>
          )}
        </dl>
      )}

      <ListaDocumentos documentos={s.documentos_exigidos ?? []} compacta className="mt-3" />

      {/* Botão no pé do cartão, largura toda no celular (alvo de toque). */}
      <div className="mt-auto pt-4">
        {s.solicitar_habilitado ? (
          <Button asChild className="w-full sm:w-auto">
            <Link href={`/cidadao/servicos/${s.slug}`}>Solicitar serviço</Link>
          </Button>
        ) : (
          <Button
            variant="secondary"
            disabled
            className="w-full sm:w-auto"
            title="O atendimento online deste serviço está pausado pela prefeitura."
          >
            Solicitação indisponível
          </Button>
        )}
      </div>
    </article>
  );
}
