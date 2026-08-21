"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronsUpDown, LayoutGrid } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api";
import { MENUS } from "@/lib/menus";
import { iconeDoModulo } from "@/lib/modulos";
import { cn } from "@/lib/utils";

interface Props {
  /** Slug do módulo ativo (`moduloDoPathname`), ou `null` em rota transversal. */
  modulo: string | null;
  collapsed: boolean;
}

/**
 * Seletor de módulo no topo da Sidebar: mostra onde o usuário está e, ao
 * clicar, abre ali mesmo a lista dos OUTROS módulos + o link para `/modulos`.
 * Fechado não ocupa nada além de uma linha — a versão anterior (lista
 * permanente no rodapé) duplicava o nome do módulo ativo três vezes na mesma
 * coluna e foi rejeitada em revisão visual (2026-08-20).
 *
 * Consome a MESMA queryKey `modulos-me` que `ModuloSwitcher` e o launcher
 * usam (não cria chave nova nem `QueryClient` próprio — já foi bug nesta
 * fatia). Como o componente vive dentro da mesma árvore de `Providers`, o
 * cache costuma já estar quente quando a Sidebar monta.
 *
 * Três casos (o terceiro é o que mais erra, ver spec da fatia):
 *
 * 1. Mais de um módulo disponível: botão com o nome do módulo atual (ou
 *    "Módulos" em rota transversal — não pode sugerir que o usuário está num
 *    módulo em que não está) que expande/recolhe a lista.
 * 2. Rota transversal: idem, rótulo neutro; a lista traz todos os módulos.
 * 3. Usuário com UM módulo só: o launcher faz auto-redirect quando há
 *    exatamente um módulo (`app/(launcher)/modulos/page.tsx`) — oferecer
 *    troca seria um laço da perspectiva do usuário. Mostra só o nome do
 *    módulo, sem ação: informa o contexto, não promete uma navegação que não
 *    entrega.
 *
 * Estados de carregamento/erro espelham o `ModuloSwitcher`: carregando não
 * mostra nada (transitório e curto, mesmo cache); erro fica À MOSTRA e
 * recuperável — não pode sumir de um jeito que o usuário confunda "falhou"
 * com "você só tem um módulo".
 */
export function SidebarModuloHeader({ modulo, collapsed }: Props) {
  const { data, isLoading, isError, refetch, isRefetching } = useQuery({
    queryKey: ["modulos-me"],
    queryFn: api.modulos,
  });
  const [aberto, setAberto] = useState(false);

  if (isLoading) return null;

  if (isError) {
    return (
      <button
        type="button"
        data-testid="sidebar-modulo-header"
        onClick={() => refetch()}
        disabled={isRefetching}
        aria-label="Não foi possível carregar os módulos. Tentar novamente."
        title="Não foi possível carregar os módulos. Tentar novamente."
        className={cn(
          "flex w-full items-center gap-2 border-b border-sidebar-border px-3 py-3 text-left text-sm font-medium text-danger",
          "transition-colors duration-fast hover:bg-danger-soft disabled:opacity-60",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          collapsed && "md:hidden",
        )}
      >
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{isRefetching ? "Tentando novamente…" : "Módulos indisponíveis"}</span>
      </button>
    );
  }

  const itens = data?.itens ?? [];
  // 0 módulos: nada para mostrar nem para onde trocar — mesma decisão do
  // ModuloSwitcher (some em vez de apontar para um launcher vazio).
  if (itens.length === 0) return null;

  const ordenados = [...itens].sort((a, b) => a.ordem - b.ordem);

  // Caso 3 — módulo único: contexto sem ação.
  if (ordenados.length === 1) {
    return (
      <div
        data-testid="sidebar-modulo-header"
        className={cn(
          "flex items-center gap-2 border-b border-sidebar-border px-3 py-3 text-sm font-medium text-sidebar-foreground/90",
          collapsed && "md:hidden",
        )}
      >
        <span className="truncate">{ordenados[0].nome}</span>
      </div>
    );
  }

  const atual = ordenados.find((m) => m.slug === modulo) ?? null;
  const rotulo = atual?.nome ?? "Módulos";
  // O módulo ativo é o rótulo do botão — listá-lo de novo seria a duplicação
  // que motivou esta versão.
  const outros = ordenados.filter((m) => m.slug !== modulo);

  return (
    <div className={cn("border-b border-sidebar-border", collapsed && "md:hidden")}>
      <button
        type="button"
        data-testid="sidebar-modulo-header"
        onClick={() => setAberto((v) => !v)}
        aria-expanded={aberto}
        aria-controls="sidebar-modulo-lista"
        aria-label={atual ? `Módulo atual: ${atual.nome}. Trocar de módulo.` : "Trocar de módulo."}
        title="Trocar de módulo"
        className={cn(
          "flex w-full items-center gap-2 px-3 py-3 text-left text-sm font-medium text-sidebar-foreground/90",
          "transition-colors duration-fast hover:bg-sidebar-accent hover:text-sidebar-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <span className="flex-1 truncate">{rotulo}</span>
        <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-sidebar-muted" aria-hidden="true" />
      </button>
      {aberto && (
        <div
          id="sidebar-modulo-lista"
          data-testid="sidebar-modulo-lista"
          className="flex flex-col gap-0.5 px-2 pb-2"
        >
          {outros.map((m) => {
            const Icone = iconeDoModulo(m.icone);
            // Mesmo fail-open do launcher: slug fora de MENUS cai em /home.
            const raiz = MENUS[m.slug]?.raiz ?? "/home";
            return (
              <Link
                key={m.slug}
                href={raiz}
                onClick={() => setAberto(false)}
                className="flex items-center gap-3 rounded-md px-3 py-1.5 text-sm font-medium text-sidebar-foreground/90 transition-colors duration-fast hover:bg-sidebar-accent hover:text-sidebar-foreground"
              >
                <Icone className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="flex-1 truncate">{m.nome}</span>
              </Link>
            );
          })}
          <Link
            href="/modulos"
            onClick={() => setAberto(false)}
            className="mt-0.5 flex items-center gap-3 rounded-md border-t border-sidebar-border px-3 pb-1.5 pt-2 text-sm font-medium text-sidebar-muted transition-colors duration-fast hover:bg-sidebar-accent hover:text-sidebar-foreground"
          >
            <LayoutGrid className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="flex-1">Todos os módulos</span>
          </Link>
        </div>
      )}
    </div>
  );
}
