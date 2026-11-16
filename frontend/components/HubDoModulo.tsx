"use client";

import { ArrowRight, Lock, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/lib/auth";
import { MENUS, canSeeItem, type NavItem } from "@/lib/menus";

/** Grupos de telas "hub" de um módulo que a pessoa pode ver (vazios fora). */
export function gruposDoHub(
  slug: string,
  can: (perm: string) => boolean,
): { titulo: string; itens: NavItem[] }[] {
  return (MENUS[slug]?.grupos ?? [])
    .map((g) => ({ titulo: g.title, itens: g.items.filter((i) => i.lugar === "hub" && canSeeItem(i, can)) }))
    .filter((g) => g.itens.length > 0);
}

/** Cartões de um grupo do hub — o mesmo desenho no índice do módulo e no `/cadastros`. */
export function CartoesDoHub({ titulo, itens }: { titulo: string; itens: NavItem[] }) {
  return (
    <section aria-label={titulo} className="space-y-4">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-foreground-subtle">{titulo}</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {itens.map((i) => {
          const Icone = i.icon;
          return (
            <Link
              key={i.href}
              href={i.href}
              className="group flex items-center gap-3 rounded-card border border-border bg-surface-1 px-5 py-4 shadow-xs transition-[border-color,box-shadow,transform] duration-base ease-out-expo hover:-translate-y-0.5 hover:border-brand/40 hover:shadow-md motion-reduce:hover:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-brand transition-colors duration-fast group-hover:bg-brand group-hover:text-primary-foreground">
                <Icone className="h-4 w-4" aria-hidden="true" />
              </span>
              <span className="min-w-0 flex-1 text-sm font-medium text-foreground">{i.label}</span>
              <ArrowRight
                className="h-4 w-4 shrink-0 text-foreground-subtle transition-transform duration-fast group-hover:translate-x-0.5 group-hover:text-brand motion-reduce:group-hover:translate-x-0"
                aria-hidden="true"
              />
            </Link>
          );
        })}
      </div>
    </section>
  );
}

/**
 * Tela-índice de um módulo: as telas que existem mas não são de trabalho do
 * dia (cadastros, configuração, referência) e por isso saíram do menu lateral
 * no menu único de 2026-11-05.
 *
 * É GERADA do menu, e não uma lista à parte: aparecem os itens com
 * `lugar: "hub"` do módulo, nos grupos em que estão declarados e podados pela
 * mesma `canSeeItem` da barra e do Ctrl+K. Uma lista escrita à mão aqui
 * divergiria do menu na primeira tela nova — e a tela nova ficaria órfã.
 *
 * Desde o menu por área (2026-11-14) a barra leva a `/cadastros`, que junta
 * os índices de todos os módulos; este continua valendo por URL e Ctrl+K.
 */
export function HubDoModulo({
  slug,
  titulo,
  descricao,
  icone,
}: {
  slug: string;
  titulo: string;
  descricao: string;
  icone: LucideIcon;
}) {
  const { can } = useAuth();
  const grupos = gruposDoHub(slug, can);

  return (
    <div className="space-y-8">
      <PageHeader icon={icone} title={titulo} description={descricao} />
      {grupos.length === 0 ? (
        <EmptyState
          icon={Lock}
          title="Nenhuma destas telas está liberada para o seu perfil"
          description="Quem concede o acesso é o administrador do órgão, em Administração › Grupos & Permissões."
        />
      ) : (
        grupos.map((g) => <CartoesDoHub key={g.titulo} titulo={g.titulo} itens={g.itens} />)
      )}
    </div>
  );
}
