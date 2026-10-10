import { ChevronRight, Home } from "lucide-react";
import Link from "next/link";

import type { ModuloAtual } from "@/lib/modulo-atual";

/**
 * Trilha do topo das telas de módulo — "Menu principal › Meus módulos ›
 * Módulo", do layout de referência (protótipo Figma "Sistema - Aprimora").
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
      <Link href="/home" className={link}>
        Menu principal
      </Link>
      {seta}
      <Link href="/modulos" className={link}>
        Meus módulos
      </Link>
      {seta}
      <Link href={modulo.raiz} className={`${link} font-bold`}>
        {modulo.nome}
      </Link>
    </nav>
  );
}
