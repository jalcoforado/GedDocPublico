/**
 * "Onde o processo para?" conta quem está na unidade AGORA. O `por_unidade`
 * do backend só soma estadas encerradas, e a unidade que segurava um
 * processo havia 30 dias aparecia com 0 min.
 */
import { describe, expect, it } from "vitest";

import type { TramitacaoEtapa, TramitacaoProcesso } from "@/lib/api";
import { tempoPorUnidade } from "@/lib/tempo-por-unidade";

function etapa(p: Partial<TramitacaoEtapa>): TramitacaoEtapa {
  return {
    id_unidade: 1,
    unidade: "Protocolo",
    chegou_em: "2026-11-01T08:00:00",
    saiu_em: null,
    minutos_no_local: null,
    prazo_estipulado: null,
    atrasou: false,
    ...p,
  };
}

function processo(p: Partial<TramitacaoProcesso>): TramitacaoProcesso {
  return {
    id: 1,
    numero_processo: "P1",
    data_hora_abertura: "2026-11-01T08:00:00",
    ativo: true,
    manifestante: null,
    assunto: null,
    qtd_encaminhamentos: 0,
    qtd_unidades_visitadas: 1,
    minutos_total: 0,
    minutos_em_andamento: 0,
    teve_atraso: false,
    qtd_atrasos: 0,
    local_atual: null,
    etapas: [],
    ...p,
  };
}

describe("tempoPorUnidade", () => {
  it("a estada em curso entra com o tempo em andamento do processo", () => {
    const r = tempoPorUnidade([
      processo({
        minutos_em_andamento: 43200, // 30 dias parado na Saúde
        etapas: [
          etapa({ id_unidade: 1, unidade: "Protocolo", saiu_em: "2026-11-01T09:00:00", minutos_no_local: 60 }),
          etapa({ id_unidade: 2, unidade: "Saúde" }),
        ],
      }),
    ]);
    expect(r.map((u) => u.unidade)).toEqual(["Saúde", "Protocolo"]);
    expect(r[0]).toMatchObject({ minutos: 43200, paradosAgora: 1, passagens: 1 });
    expect(r[1]).toMatchObject({ minutos: 60, paradosAgora: 0 });
  });

  it("processo arquivado não acumula tempo na última unidade", () => {
    const r = tempoPorUnidade([
      processo({ ativo: false, minutos_em_andamento: 99999, etapas: [etapa({})] }),
    ]);
    expect(r).toEqual([]);
  });

  it("etapa em trânsito (sem chegada) fica de fora; atrasos são contados", () => {
    const r = tempoPorUnidade([
      processo({
        minutos_em_andamento: 10,
        etapas: [
          etapa({ saiu_em: "2026-11-02T08:00:00", minutos_no_local: 120, atrasou: true }),
          etapa({ id_unidade: 3, unidade: "Obras", chegou_em: null }),
        ],
      }),
    ]);
    expect(r).toHaveLength(1);
    expect(r[0]).toMatchObject({ unidade: "Protocolo", atrasos: 1, medio: 120 });
  });
});
