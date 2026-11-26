/**
 * Filtro dos relatórios na URL: o recorte gerado tem endereço (recarregar,
 * voltar e mandar o link reabrem o mesmo relatório).
 */
import { describe, expect, it } from "vitest";

import { filtroParaQuery, lerFiltro } from "@/lib/filtro-na-url";

describe("filtro na URL", () => {
  it("ida e volta preserva tipos: id_* número, apenas_* booleano, resto texto", () => {
    const f = {
      id_unidade: 12,
      id_tipo_processo: 3,
      desde: "2026-11-01T00:00:00",
      apenas_ativos: true,
      status: "pendente",
    };
    expect(lerFiltro(new URLSearchParams(filtroParaQuery(f)))).toEqual(f);
  });

  it("vazio, false e undefined não vão para a URL", () => {
    expect(
      filtroParaQuery({ id_unidade: undefined, desde: "", apenas_ativos: false }),
    ).toBe("");
  });

  it("id que não é número é ignorado em vez de virar NaN no filtro", () => {
    expect(lerFiltro(new URLSearchParams("id_unidade=abc&id_assunto=7"))).toEqual({
      id_assunto: 7,
    });
  });
});
