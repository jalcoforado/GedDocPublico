"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, Search, SlashIcon } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import type { IndicadorCatalogo } from "@/lib/api";
import { api } from "@/lib/api";

/**
 * Catálogo de indicadores — a tela que encerra a discussão sobre o que cada
 * número quer dizer.
 *
 * As definições vêm do backend (`services/pagamentos_catalogo.py`), que é a
 * fonte única. Esta tela não guarda texto de definição nenhum: se guardasse,
 * em poucas semanas haveria duas verdades e o painel afirmaria uma coisa
 * enquanto o catálogo afirmaria outra.
 */
export default function CatalogoPage() {
  const [busca, setBusca] = useState("");
  const q = useQuery({
    queryKey: ["pag-catalogo"],
    // As definições não mudam por tenant nem por minuto.
    staleTime: 60 * 60 * 1000,
    queryFn: () => api.pagamentos.catalogoIndicadores(),
  });

  const itens = useMemo(() => {
    const todos = q.data ?? [];
    const termo = busca.trim().toLowerCase();
    if (!termo) return todos;
    return todos.filter((i) =>
      [i.nome, i.definicao, i.formula, i.nao_confundir, i.grupo]
        .join(" ")
        .toLowerCase()
        .includes(termo),
    );
  }, [q.data, busca]);

  const grupos = useMemo(() => {
    const mapa = new Map<string, IndicadorCatalogo[]>();
    for (const i of itens) {
      const atual = mapa.get(i.grupo) ?? [];
      atual.push(i);
      mapa.set(i.grupo, atual);
    }
    return [...mapa.entries()];
  }, [itens]);

  const indisponiveis = (q.data ?? []).filter((i) => !i.disponivel).length;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={BookOpen}
        title="Catálogo de indicadores"
        description="O que cada número do módulo significa, como é calculado e de onde vem."
      />

      <p className="max-w-3xl text-sm leading-relaxed text-foreground-muted">
        Este catálogo serve para duas coisas. A primeira é acabar com a conversa sobre o que um
        número quer dizer — “comprometido” tem uma definição só, escrita aqui. A segunda é
        declarar o que o sistema <strong className="font-semibold text-foreground">não tem</strong>:{" "}
        {indisponiveis} conceitos que a gestão pública usa aparecem com a ficha explicando por que
        não existem aqui. Procurar e não achar faz pensar que esqueceram; achar a ficha mostra o
        que falta para o indicador existir.
      </p>

      <div className="relative max-w-md">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-subtle"
          aria-hidden="true"
        />
        <Input
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          placeholder="Buscar indicador, fórmula ou conceito…"
          aria-label="Buscar no catálogo"
          className="pl-9"
        />
      </div>

      {q.isLoading && <div className="h-64 animate-pulse rounded-card bg-surface-2/40" />}

      {q.data && itens.length === 0 && (
        <EmptyState
          icon={Search}
          title="Nenhum indicador encontrado"
          description="Tente outro termo — por exemplo “saldo”, “empenho” ou “vinculado”."
        />
      )}

      {grupos.map(([grupo, lista]) => (
        <section key={grupo} className="space-y-3">
          <h2 className="font-display text-base font-semibold text-foreground">{grupo}</h2>
          <div className="grid gap-3 lg:grid-cols-2">
            {lista.map((i) => (
              <Ficha key={i.codigo} i={i} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function Ficha({ i }: { i: IndicadorCatalogo }) {
  return (
    <article
      className={
        i.disponivel
          ? "rounded-card border border-border bg-surface-1 p-4 shadow-card"
          : "rounded-card border border-dashed border-border-strong bg-surface-2/40 p-4"
      }
    >
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="font-display text-sm font-semibold text-foreground">{i.nome}</h3>
        {!i.disponivel && (
          <span className="inline-flex items-center gap-1 rounded-badge bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-foreground-muted">
            <SlashIcon className="h-3 w-3" aria-hidden="true" />
            Não existe no sistema
          </span>
        )}
      </header>

      <p className="mt-2 text-sm leading-relaxed text-foreground-muted">{i.definicao}</p>

      <dl className="mt-3 space-y-1.5 text-xs">
        {i.formula !== "—" && (
          <Campo rotulo="Fórmula">
            <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-foreground">
              {i.formula}
            </code>
          </Campo>
        )}
        <Campo rotulo="Fonte">{i.fonte}</Campo>
        {i.granularidade !== "—" && <Campo rotulo="Granularidade">{i.granularidade}</Campo>}
        {i.periodicidade !== "—" && <Campo rotulo="Atualização">{i.periodicidade}</Campo>}
      </dl>

      <p className="mt-3 border-t border-border pt-2 text-xs leading-relaxed text-foreground-muted">
        <span className="font-medium text-foreground">Restrições:</span> {i.restricoes}
      </p>
      <p className="mt-1.5 text-xs leading-relaxed text-foreground-muted">
        <span className="font-medium text-foreground">Não confundir com:</span> {i.nao_confundir}
      </p>
    </article>
  );
}

function Campo({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap gap-x-2">
      <dt className="shrink-0 font-medium text-foreground-subtle">{rotulo}:</dt>
      <dd className="min-w-0 text-foreground-muted">{children}</dd>
    </div>
  );
}
