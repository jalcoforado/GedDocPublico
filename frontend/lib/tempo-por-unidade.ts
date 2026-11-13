import type { TramitacaoProcesso } from "@/lib/api";

export interface TempoNaUnidade {
  chave: string;
  unidade: string;
  /** Estadas contadas: as encerradas mais as que estão em curso agora. */
  passagens: number;
  minutos: number;
  medio: number;
  /** Processos ativos parados nesta unidade neste momento. */
  paradosAgora: number;
  atrasos: number;
}

/**
 * Tempo de cada unidade contando também QUEM ESTÁ LÁ AGORA.
 *
 * O `por_unidade` do backend soma só estadas encerradas (`minutos_no_local`,
 * que é nulo enquanto o processo não sai). Para "onde o processo para?" isso
 * inverte a resposta: a unidade que segura um processo há 30 dias aparecia
 * com 0 min, justamente por ainda não ter soltado. Aqui a estada em curso de
 * processo ativo entra com o tempo que o backend já calcula para ela
 * (`minutos_em_andamento`) — sem conta de relógio no navegador.
 *
 * Etapa em trânsito (encaminhada, ainda não recebida) não tem unidade de
 * chegada nem tempo e fica de fora.
 */
export function tempoPorUnidade(processos: TramitacaoProcesso[]): TempoNaUnidade[] {
  const porChave = new Map<string, TempoNaUnidade>();
  for (const p of processos) {
    for (const e of p.etapas) {
      let minutos = e.minutos_no_local;
      let agora = false;
      if (minutos === null && e.saiu_em === null && e.chegou_em !== null && p.ativo) {
        minutos = p.minutos_em_andamento;
        agora = true;
      }
      if (minutos === null) continue;
      const chave = String(e.id_unidade ?? e.unidade ?? "—");
      const u = porChave.get(chave) ?? {
        chave,
        unidade: e.unidade ?? "—",
        passagens: 0,
        minutos: 0,
        medio: 0,
        paradosAgora: 0,
        atrasos: 0,
      };
      u.passagens += 1;
      u.minutos += minutos;
      if (agora) u.paradosAgora += 1;
      if (e.atrasou) u.atrasos += 1;
      porChave.set(chave, u);
    }
  }
  return [...porChave.values()]
    .map((u) => ({ ...u, medio: u.passagens ? u.minutos / u.passagens : 0 }))
    .sort((a, b) => b.medio - a.medio);
}
