"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

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
 * Seção "Módulos" no rodapé da Sidebar: um link por módulo disponível, para
 * que trocar de módulo (e o menu lateral inteiro junto — design F2) nunca
 * pareça "os menus sumiram". O módulo ativo fica destacado como "você está
 * aqui"; os demais são o caminho de um clique para o resto do sistema.
 *
 * Consome a MESMA queryKey `modulos-me` do ModuloSwitcher/launcher/cabeçalho.
 * Estados: carregando/erro não mostram nada — o SidebarModuloHeader (mesma
 * query, mesmo cache) já é quem expõe o erro de forma recuperável; repetir a
 * mensagem aqui seria ruído. Com um módulo só a seção some: não há para onde
 * trocar.
 */
export function SidebarModulos({ modulo, collapsed }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["modulos-me"],
    queryFn: api.modulos,
  });

  if (isLoading || isError) return null;

  const itens = data?.itens ?? [];
  if (itens.length < 2) return null;

  const ordenados = [...itens].sort((a, b) => a.ordem - b.ordem);

  return (
    <div
      data-testid="sidebar-modulos"
      className={cn(
        "border-t border-sidebar-border px-2 py-2",
        collapsed && "lg:hidden",
      )}
    >
      <div className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-sidebar-muted">
        Módulos
      </div>
      <div className="flex flex-col gap-0.5">
        {ordenados.map((m) => {
          const Icone = iconeDoModulo(m.icone);
          // Mesmo fail-open do launcher: slug fora de MENUS cai em /home.
          const raiz = MENUS[m.slug]?.raiz ?? "/home";
          const ativo = m.slug === modulo;
          return (
            <Link
              key={m.slug}
              href={raiz}
              aria-current={ativo ? "true" : undefined}
              className={cn(
                "group flex items-center gap-3 rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-fast",
                ativo
                  ? "bg-sidebar-active text-sidebar-foreground"
                  : "text-sidebar-foreground/90 hover:bg-sidebar-accent hover:text-sidebar-foreground",
              )}
            >
              <Icone
                className={cn("h-4 w-4 shrink-0", ativo && "text-accent")}
                aria-hidden="true"
              />
              <span className="flex-1 truncate">{m.nome}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
