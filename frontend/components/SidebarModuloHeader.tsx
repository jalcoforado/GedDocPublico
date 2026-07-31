"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  /** Slug do módulo ativo (`moduloDoPathname`), ou `null` em rota transversal. */
  modulo: string | null;
  collapsed: boolean;
}

/**
 * Cabeçalho no topo da Sidebar: mostra em que módulo o usuário está e serve
 * de caminho de volta a `/modulos`. Antes desta peça o único caminho de
 * volta ao launcher vivia dentro do dropdown do `ModuloSwitcher`, no Header.
 *
 * Consome a MESMA queryKey `modulos-me` que `ModuloSwitcher` e o launcher
 * usam (não cria chave nova nem `QueryClient` próprio — já foi bug nesta
 * fatia). Como o componente vive dentro da mesma árvore de `Providers`, o
 * cache costuma já estar quente quando a Sidebar monta.
 *
 * Três casos (o terceiro é o que mais erra, ver spec da fatia):
 *
 * 1. Dentro de um módulo, com mais de um módulo disponível: seta + nome do
 *    módulo atual, clicável, leva a `/modulos`.
 * 2. Rota transversal (`modulo` nulo): rótulo neutro ("Módulos"), clicável —
 *    não pode sugerir que o usuário está num módulo em que não está.
 * 3. Usuário com UM módulo só: o launcher faz auto-redirect quando há
 *    exatamente um módulo (`app/(launcher)/modulos/page.tsx`, não mexido
 *    aqui) — um link para `/modulos` bateria e voltaria na hora, um laço da
 *    perspectiva do usuário. Mostra só o nome do módulo, sem seta, sem ação:
 *    informa o contexto, não promete uma navegação que não entrega.
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
          collapsed && "lg:hidden",
        )}
      >
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{isRefetching ? "Tentando novamente…" : "Módulos indisponíveis"}</span>
      </button>
    );
  }

  const itens = data?.itens ?? [];
  // 0 módulos: nada para mostrar nem para onde voltar — mesma decisão do
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
          collapsed && "lg:hidden",
        )}
      >
        <span className="truncate">{ordenados[0].nome}</span>
      </div>
    );
  }

  // Casos 1 e 2 — mais de um módulo disponível: sempre clicável.
  const atual = ordenados.find((m) => m.slug === modulo) ?? null;
  const rotulo = atual?.nome ?? "Módulos";
  const rotuloAcessivel = atual
    ? `Módulo atual: ${atual.nome}. Voltar para a lista de módulos.`
    : "Voltar para a lista de módulos.";

  return (
    <Link
      href="/modulos"
      data-testid="sidebar-modulo-header"
      aria-label={rotuloAcessivel}
      title={rotuloAcessivel}
      className={cn(
        "flex items-center gap-2 border-b border-sidebar-border px-3 py-3 text-sm font-medium text-sidebar-foreground/90",
        "transition-colors duration-fast hover:bg-sidebar-accent hover:text-sidebar-foreground",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        collapsed && "lg:hidden",
      )}
    >
      <ArrowLeft className="h-4 w-4 shrink-0 text-sidebar-muted" aria-hidden="true" />
      <span className="truncate">{rotulo}</span>
    </Link>
  );
}
