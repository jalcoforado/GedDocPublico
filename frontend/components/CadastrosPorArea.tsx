"use client";

import { useQuery } from "@tanstack/react-query";
import { FolderTree, Lock } from "lucide-react";

import { CartoesDoHub, gruposDoHub } from "@/components/HubDoModulo";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { MENUS } from "@/lib/menus";
import { AREAS, modulosDasAreas } from "@/lib/menus/areas";
import { nomeDoModulo } from "@/lib/modulos";

/**
 * `/cadastros` — cadastros, fluxos e configuração de TODOS os módulos, numa
 * tela só, por área (menu por área, 2026-11-14). Antes cada módulo tinha o
 * seu "Cadastros e configuração" / "Cadastros e controle" na barra.
 *
 * Gerada do menu, como o `HubDoModulo`: as telas `lugar: "hub"` de cada
 * módulo contratado, podadas pela mesma `canSeeItem`. Módulo que nenhuma área
 * cita (um módulo novo) entra no fim, com o próprio nome.
 */
export function CadastrosPorArea() {
  const { can } = useAuth();
  const modulosQ = useQuery({ queryKey: ["modulos-me"], queryFn: api.modulos, staleTime: 5 * 60_000 });
  // Sem a lista de contratados (erro), mostra todos — o que cada pessoa vê
  // continua decidido pela permissão de cada tela.
  const contratados = new Set(
    modulosQ.isError ? Object.keys(MENUS) : (modulosQ.data?.itens ?? []).map((m) => m.slug),
  );

  const blocos: { titulo: string; modulos: { slug: string; grupos: ReturnType<typeof gruposDoHub> }[] }[] = [];
  for (const area of AREAS) {
    const slugs = Array.from(
      new Set(area.itens.flatMap((r) => ("subgrupo" in r ? r.itens : [r]).map((x) => x.modulo))),
    );
    const modulos = slugs
      .filter((s) => contratados.has(s))
      .map((slug) => ({ slug, grupos: gruposDoHub(slug, can) }))
      .filter((m) => m.grupos.length > 0);
    if (modulos.length > 0) blocos.push({ titulo: area.titulo, modulos });
  }
  const citados = modulosDasAreas();
  for (const slug of Object.keys(MENUS)) {
    if (slug === "comum" || citados.has(slug) || !contratados.has(slug)) continue;
    const grupos = gruposDoHub(slug, can);
    if (grupos.length > 0) blocos.push({ titulo: nomeDoModulo(slug), modulos: [{ slug, grupos }] });
  }

  return (
    <div className="space-y-10">
      <PageHeader
        icon={FolderTree}
        title="Cadastros e configuração"
        description="Cadastros, fluxos e configuração de todos os módulos, organizados por área."
      />
      {modulosQ.isLoading ? null : blocos.length === 0 ? (
        <EmptyState
          icon={Lock}
          title="Nenhuma destas telas está liberada para o seu perfil"
          description="Quem concede o acesso é o administrador do órgão, em Administração › Grupos & Permissões."
        />
      ) : (
        blocos.map((b) => (
          <section key={b.titulo} aria-labelledby={`area-${b.titulo}`} className="space-y-6">
            <h2 id={`area-${b.titulo}`} className="font-display text-lg font-semibold text-titulo">
              {b.titulo}
            </h2>
            {b.modulos.map((m) => (
              <div key={m.slug} className="space-y-6">
                {b.modulos.length > 1 &&
                  // O grupo do módulo já tem o nome dele ("Frota") — não repete.
                  !m.grupos.some((g) => g.titulo === nomeDoModulo(m.slug)) && (
                  <h3 className="text-sm font-semibold text-foreground">{nomeDoModulo(m.slug)}</h3>
                )}
                {m.grupos.map((g) => (
                  <CartoesDoHub key={g.titulo} titulo={g.titulo} itens={g.itens} />
                ))}
              </div>
            ))}
          </section>
        ))
      )}
    </div>
  );
}
