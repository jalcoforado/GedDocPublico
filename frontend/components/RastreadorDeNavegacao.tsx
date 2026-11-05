"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { registrarVisita } from "@/lib/trilha-navegacao";

/**
 * Anota cada página visitada na trilha da aba (`lib/trilha-navegacao.ts`),
 * inclusive troca de filtro, que só muda a query. Mora no shell autenticado;
 * não desenha nada. O shell o embrulha em `<Suspense>`: `useSearchParams`
 * fora de um exige isso no build do Next.
 */
export function RastreadorDeNavegacao() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const query = searchParams.toString();
  useEffect(() => {
    registrarVisita(query ? `${pathname}?${query}` : pathname);
  }, [pathname, query]);
  return null;
}
