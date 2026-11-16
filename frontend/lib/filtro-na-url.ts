"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

type Valor = string | number | boolean | undefined;

/**
 * Filtro aplicado de um relatório, guardado na URL.
 *
 * O relatório gerado tem endereço: recarregar a página, voltar do processo
 * aberto a partir da lista ou mandar o link a um colega reabre o MESMO
 * recorte. Antes o filtro vivia só em estado do React e se perdia em
 * qualquer uma dessas três situações.
 *
 * Tipos pelo nome da chave, sem esquema por relatório: `id_*` é número,
 * `apenas_*` é booleano, o resto é texto (datas ISO incluídas). Valor vazio,
 * `false` e `undefined` saem da URL.
 */
export function lerFiltro<T extends object>(sp: URLSearchParams): T {
  const out: Record<string, Valor> = {};
  sp.forEach((v, k) => {
    if (v === "") return;
    if (k.startsWith("id_")) {
      const n = Number(v);
      if (Number.isFinite(n)) out[k] = n;
    } else if (k.startsWith("apenas_")) {
      if (v === "1" || v === "true") out[k] = true;
    } else {
      out[k] = v;
    }
  });
  return out as T;
}

export function filtroParaQuery(f: object): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(f) as [string, Valor][]) {
    if (v === undefined || v === null || v === "" || v === false) continue;
    sp.set(k, v === true ? "1" : String(v));
  }
  return sp.toString();
}

export function useFiltroNaUrl<T extends object>(): [T, (f: T) => void] {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const chave = sp.toString();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- `chave` é o conteúdo de `sp`
  const aplicado = useMemo(() => lerFiltro<T>(new URLSearchParams(chave)), [chave]);
  const aplicar = useCallback(
    (f: T) => {
      const q = filtroParaQuery(f);
      router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
    },
    [router, pathname],
  );
  return [aplicado, aplicar];
}
