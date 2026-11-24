import { ChevronRight, Home } from "lucide-react";
import Link from "next/link";

import type { ModuloAtual } from "@/lib/modulo-atual";

/**
 * Trilha do topo das telas de módulo — "Início › Módulo". Era "Menu
 * principal › Meus módulos › Módulo" (protótipo Figma) até o launcher sair.
 *
 * Mora no SHELL (`app/(app)/layout.tsx`), não no `PageHeader`: a primeira
 * versão ficava no cabeçalho de página, e uma em cada três telas de módulo
 * (Usuários, Grupos, Relatórios, Caixa…) desenha o próprio `<h1>` sem ele —
 * nessas a trilha simplesmente não aparecia.
 */
export function TrilhaDoModulo({ modulo }: { modulo: ModuloAtual }) {
  const link =
    "rounded underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
  const seta = <ChevronRight className="h-3.5 w-3.5 shrink-0 opacity-60" aria-hidden="true" />;
  return (
    <nav
      aria-label="Trilha"
      className="mb-3 flex flex-wrap items-center gap-x-1.5 gap-y-1 font-display text-sm text-titulo-destaque"
    >
      <Home className="mr-1 h-4 w-4 shrink-0 text-foreground-subtle" aria-hidden="true" />
      {/* "Menu principal › Meus módulos" saiu com o launcher (menu único,
          2026-11-05): o ponto de partida é o Início. */}
      <Link href="/home" className={link}>
        Início
      </Link>
      {seta}
      <Link href={modulo.raiz} className={`${link} font-bold`}>
        {modulo.nome}
      </Link>
    </nav>
  );
}
