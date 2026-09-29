import { api, type Manifestante } from "./api";
import { useBuscaNoServidor } from "./busca-no-servidor";

/**
 * Combo de manifestante com busca no servidor (nome ou CPF/CNPJ, com ou sem
 * máscara — o backend normaliza). Usado por Novo processo e Balcão.
 *
 * Nenhuma tela carrega "todos os manifestantes": a lista cresce um por
 * cidadão atendido e o backend corta em `page_size ≤ 200`
 * (`routers/manifestantes.py`). `__tests__/page-size-teto.test.ts` reprova
 * quem pedir acima do teto.
 */
export const MANIFESTANTES_BUSCA_KEY = "manifestantes-busca";
const POR_BUSCA = 20;

export function useManifestantesBusca(valor: number | null) {
  return useBuscaNoServidor<Manifestante>({
    chave: MANIFESTANTES_BUSCA_KEY,
    buscar: (q) =>
      api.manifestantes
        .list({ q: q || undefined, page_size: POR_BUSCA })
        .then((r) => r.items),
    porId: (id) => api.manifestantes.get(id),
    valor,
    paraOpcao: (m) => ({
      value: m.id,
      label: m.nome ?? "(sem nome)",
      hint: m.cpf_cnpj ?? undefined,
    }),
  });
}
