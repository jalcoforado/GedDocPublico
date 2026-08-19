import { useQuery } from "@tanstack/react-query";

import { api, type Assunto } from "./api";

/**
 * Fonte única do catálogo de assuntos no cache do React Query.
 *
 * A chave `["assuntos-all"]` era usada por cinco telas com `queryFn`
 * divergentes: quatro guardavam o objeto `Paginated` e uma guardava
 * `.items`. Como o cache é indexado pela chave e não por quem escreveu,
 * quem chegasse depois lia o formato do outro — e a tela de Serviços
 * quebrava com `data.map is not a function` ao ser aberta depois de
 * Processos, Relatórios, Balcão ou Novo processo.
 *
 * Regra: nenhuma tela monta essa query à mão. `__tests__/assuntos-cache.test.ts`
 * reprova quem voltar a escrever a chave fora daqui.
 *
 * `page_size` fica em 200 porque é o teto do backend
 * (`routers/assuntos.py`, `Query(20, ge=1, le=200)`): pedir 500 devolvia 422
 * e deixava o combo vazio no Balcão e no Novo processo.
 */
export const ASSUNTOS_ALL_KEY = ["assuntos-all"] as const;
export const ASSUNTOS_PAGE_SIZE = 200;

export function useAssuntosAll() {
  return useQuery<Assunto[]>({
    queryKey: ASSUNTOS_ALL_KEY,
    queryFn: () =>
      api.assuntos.list({ page_size: ASSUNTOS_PAGE_SIZE }).then((r) => r.items),
  });
}
