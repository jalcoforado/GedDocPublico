import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import type { ComboboxOption } from "@/components/ui/combobox";

/**
 * Combobox alimentado por busca no servidor, para listas que crescem sem
 * limite (manifestante, processo).
 *
 * O padrão anterior carregava a lista inteira de uma vez
 * (`list({ page_size: 500 })`) e filtrava no navegador. Isso esbarra no teto
 * de `page_size` do backend (`le=200`/`le=100`): o pedido volta 422 e o combo
 * fica vazio — foi o erro visto em 2026-09-28 na busca de manifestante. E
 * mesmo dentro do teto, a partir do item N+1 os novos somem da busca sem erro
 * nenhum.
 *
 * - `buscar(q)` é chamado com o texto digitado, com debounce; `q` vazio traz
 *   a primeira página, para o combo não abrir em branco.
 * - O selecionado continua resolvível mesmo quando sai do resultado da busca:
 *   os itens vistos ficam guardados e, se o valor veio de fora (rascunho
 *   restaurado), `porId` busca o item.
 */
export interface OpcoesBuscaNoServidor<T extends { id: number }> {
  chave: string;
  buscar: (q: string) => Promise<T[]>;
  porId?: (id: number) => Promise<T>;
  valor: number | null;
  paraOpcao: (item: T) => ComboboxOption;
  atrasoMs?: number;
}

export function useBuscaNoServidor<T extends { id: number }>({
  chave,
  buscar,
  porId,
  valor,
  paraOpcao,
  atrasoMs = 250,
}: OpcoesBuscaNoServidor<T>) {
  const [digitado, setDigitado] = useState("");
  const [termo, setTermo] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setTermo(digitado.trim()), atrasoMs);
    return () => clearTimeout(t);
  }, [digitado, atrasoMs]);

  const resultadoQ = useQuery({
    queryKey: [chave, "busca", termo],
    queryFn: () => buscar(termo),
    placeholderData: keepPreviousData,
  });

  const vistos = useRef(new Map<number, T>());
  for (const item of resultadoQ.data ?? []) vistos.current.set(item.id, item);

  const faltaSelecionado = valor != null && !vistos.current.has(valor);
  const selecionadoQ = useQuery({
    queryKey: [chave, "id", valor],
    queryFn: () => porId!(valor as number),
    enabled: porId !== undefined && faltaSelecionado,
  });
  if (selecionadoQ.data) vistos.current.set(selecionadoQ.data.id, selecionadoQ.data);

  const selecionado = valor != null ? vistos.current.get(valor) ?? null : null;
  const options = useMemo(
    () => (resultadoQ.data ?? []).map(paraOpcao),
    // `paraOpcao` costuma ser função inline: depender dela refaria a lista a
    // cada render sem ganho.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [resultadoQ.data],
  );

  return {
    options,
    selectedOption: selecionado ? paraOpcao(selecionado) : null,
    selecionado,
    onQueryChange: setDigitado,
    loading: resultadoQ.isFetching,
  };
}
