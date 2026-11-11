/**
 * Página gerencial de relatórios (SI-34). Uma tela, filtro no topo, cinco
 * seções; cada número leva à lista que o produziu, com o MESMO recorte. O
 * backend garante que o número da seção é o total dessa lista
 * (`tests/test_relatorios_protocolo_medidas.py`); aqui se garante que o link
 * da seção carrega o recorte certo — sem isso a lista abriria com outro
 * filtro e o número não bateria, com os dois lados "certos".
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { GerencialResposta } from "@/lib/api";
import {
  filtroDaUrl,
  filtroParaUrl,
  fmtDataHora,
  fmtDias,
} from "@/lib/relatorios";

const nav = { busca: "", replace: vi.fn() };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace, push: vi.fn(), back: vi.fn() }),
  usePathname: () => "/m/protocolo/relatorios",
  useSearchParams: () => new URLSearchParams(nav.busca),
}));

const gerencialMock = vi.fn((_f: unknown) => Promise.resolve(resposta()));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      relatorios: { ...actual.api.relatorios, gerencial: (f: unknown) => gerencialMock(f) },
      tiposProcesso: { ...actual.api.tiposProcesso, list: () => Promise.resolve([]) },
      assuntos: { ...actual.api.assuntos, list: () => Promise.resolve({ items: [], total: 0 }) },
    },
    organogramaApi: { tree: () => Promise.resolve([]) },
  };
});

function resposta(): GerencialResposta {
  return {
    descricao_filtros: ["Período: 01/10/2026 a 31/10/2026 — cada seção diz por qual data conta"],
    entrada: {
      abertos: 142,
      por_canal: [
        { canal: "balcao", rotulo: "Balcão", count: 100 },
        { canal: null, rotulo: "Não informado", count: 42 },
      ],
      top_assuntos: [
        { id_assunto: 9, assunto: "Iluminação pública", count: 40 },
        { id_assunto: 4, assunto: "Poda de árvore", count: 20 },
      ],
    },
    andamento: { em_andamento: 88, em_transito: 9, parados: 12, dias_parado: 15 },
    saida: { arquivados: 41, dias_medio_ate_arquivar: 18.25 },
    prazos: {
      concluidos_no_prazo: 32, concluidos_atrasados: 9, concluidos_sem_prazo: 0,
      dentro_do_prazo: 51, vencendo: 8, atrasados: 6, em_aberto_sem_prazo: 23,
    },
    tendencia: {
      granularidade: "semana", desde: "2026-10-01", ate: "2026-10-31",
      pontos: [
        { inicio: "2026-09-28", abertos: 30, arquivados: 10 },
        { inicio: "2026-10-05", abertos: 40, arquivados: 12 },
      ],
    },
    comparacao: { desde: "2026-08-31", ate: "2026-09-30", abertos: 125, arquivados: 50 },
    gargalos: {
      unidades: [
        { id_unidade: 3, unidade: "Secretaria de Obras", chegadas: 20, com_prazo: 10, atrasos: 7, dias_medio: 4.5 },
      ],
      cortado: false,
    },
    assinaturas: { total: 30, pendentes: 6, concluidas: 22, canceladas: 2, minutos_medio_conclusao: 2880 },
  };
}

async function abrir(busca = "") {
  nav.busca = busca;
  const { default: Pagina } = await import("@/app/(app)/m/protocolo/relatorios/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Pagina />
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { name: "Entrada" });
}

/** Os parâmetros do link "Ver lista" dentro da seção. */
function linkDaSecao(secao: string, indice = 0): { rota: string; params: URLSearchParams } {
  const regiao = screen.getByRole("region", { name: secao });
  const href = within(regiao).getAllByRole("link", { name: /Ver lista/ })[indice].getAttribute("href")!;
  const [rota, qs = ""] = href.split("?");
  return { rota, params: new URLSearchParams(qs) };
}

// A página traz a biblioteca de gráficos: o primeiro import é lento (7s numa
// máquina ocupada) e estourava o limite de 5s do primeiro teste. Carrega uma
// vez aqui, com folga, e os testes medem a página, não o import.
beforeAll(async () => {
  await import("@/app/(app)/m/protocolo/relatorios/page");
}, 60_000);

beforeEach(() => {
  gerencialMock.mockClear();
  nav.replace.mockClear();
});
afterEach(() => cleanup());

const RECORTE = "desde=2026-10-01&ate=2026-10-31&id_unidade=3&modo_unidade=passou&id_assunto=9";

describe("página gerencial — o recorte vai da URL para a consulta e para os links", () => {
  it("consulta com o recorte da URL e mostra os números de cada seção", async () => {
    await abrir(RECORTE);
    expect(gerencialMock).toHaveBeenCalledWith({
      id_unidade: 3, modo_unidade: "passou", id_assunto: 9, id_tipo_processo: undefined,
      desde: "2026-10-01", ate: "2026-10-31", dias_parado: 15,
    });
    expect(within(screen.getByRole("region", { name: "Entrada" })).getByText("142")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Saída" })).getByText("18,3 dias")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Gargalos" })).getByText("Secretaria de Obras")).toBeTruthy();
    expect(screen.getByText(/cada seção diz por qual data conta/)).toBeTruthy();
  });

  it("Entrada e Saída abrem a lista do mesmo período, cada uma pela sua data", async () => {
    await abrir(RECORTE);
    const entrada = linkDaSecao("Entrada");
    expect(entrada.rota).toBe("/m/protocolo/relatorios/processos");
    expect(Object.fromEntries(entrada.params)).toEqual({
      desde: "2026-10-01", ate: "2026-10-31", id_unidade: "3", modo_unidade: "passou",
      id_assunto: "9", data_base: "abertura",
    });
    expect(linkDaSecao("Saída").params.get("data_base")).toBe("arquivamento");
  });

  it("Andamento é foto de hoje: o link tira o período e leva a situação", async () => {
    await abrir(RECORTE);
    const emTransito = linkDaSecao("Andamento", 1);
    expect(emTransito.params.get("situacao")).toBe("em_transito");
    expect(emTransito.params.has("desde")).toBe(false);
    expect(emTransito.params.has("ate")).toBe(false);
    // unidade e assunto continuam valendo
    expect(emTransito.params.get("id_unidade")).toBe("3");
    const parados = linkDaSecao("Andamento", 2);
    expect(parados.params.get("parado_ha_dias")).toBe("15");
  });

  it("Gargalos e Assinaturas abrem as suas listas pela data de entrada e de pedido", async () => {
    await abrir(RECORTE);
    const garg = linkDaSecao("Gargalos");
    expect(garg.rota).toBe("/m/protocolo/relatorios/tramitacao");
    expect(garg.params.get("data_base")).toBe("chegada");
    const ass = linkDaSecao("Assinaturas");
    expect(ass.rota).toBe("/m/protocolo/relatorios/assinaturas");
    expect(ass.params.get("data_base")).toBe("pedido");
    expect(ass.params.get("id_unidade")).toBe("3");
  });
});

describe("página gerencial — prazos, tendência e comparação", () => {
  it("Prazos: arquivados pelo período de arquivamento; em aberto sem período", async () => {
    await abrir(RECORTE);
    const vencidos = linkDaSecao("Prazos", 4);
    expect(vencidos.params.get("prazo")).toBe("atrasado");
    expect(vencidos.params.has("desde")).toBe(false);
    const comAtraso = linkDaSecao("Prazos", 1);
    expect(comAtraso.params.get("prazo")).toBe("concluido_atrasado");
    expect(comAtraso.params.get("data_base")).toBe("arquivamento");
    expect(comAtraso.params.get("desde")).toBe("2026-10-01");
    const regiao = screen.getByRole("region", { name: "Prazos" });
    // 32 de 41 com prazo; os sem prazo são ditos, não escondidos
    expect(within(regiao).getByText("78% dos arquivados com prazo")).toBeTruthy();
    expect(within(regiao).getByText(/23 em aberto sem prazo de serviço/)).toBeTruthy();
  });

  it("comparação em números, não em %", async () => {
    await abrir(RECORTE);
    const entrada = screen.getByRole("region", { name: "Entrada" });
    expect(within(entrada).getByText("+17 vs. 31/08–30/09/2026 (125)")).toBeTruthy();
    const saida = screen.getByRole("region", { name: "Saída" });
    expect(within(saida).getByText("-9 vs. 31/08–30/09/2026 (50)")).toBeTruthy();
  });

  it("assunto leva à lista dele; gráfico tem a tabela para leitor de tela", async () => {
    await abrir(RECORTE);
    const link = screen.getByRole("link", { name: /Iluminação pública/ });
    const params = new URLSearchParams(link.getAttribute("href")!.split("?")[1]);
    expect(params.get("id_assunto")).toBe("9");
    expect(params.get("data_base")).toBe("abertura");
    const tabela = within(screen.getByRole("region", { name: "Entrada e saída no tempo" })).getByRole("table");
    expect(within(tabela).getAllByRole("row")).toHaveLength(3);
  });
});

describe("apoio dos relatórios", () => {
  it("lê da URL só o que é válido — link editado à mão não vira erro do servidor", () => {
    const f = filtroDaUrl(
      new URLSearchParams("id_unidade=abc&desde=10/10/2026&ate=2026-10-31&modo_unidade=xpto&situacao=em_transito&data_base=pedido"),
    );
    expect(f).toMatchObject({ id_unidade: undefined, desde: undefined, ate: "2026-10-31",
      modo_unidade: undefined, situacao: "em_transito", data_base: "pedido" });
  });

  it("modo da unidade só vai para a URL quando há unidade", () => {
    expect(filtroParaUrl({ modo_unidade: "dona", desde: "2026-10-01" })).toBe("?desde=2026-10-01");
    expect(filtroParaUrl({ id_unidade: 3, modo_unidade: "dona" })).toBe("?id_unidade=3&modo_unidade=dona");
    expect(filtroParaUrl({})).toBe("");
  });

  it("data sem fuso é formatada, não convertida", () => {
    // 23:30 de Brasília tem de sair 23:30, em qualquer fuso do navegador
    expect(fmtDataHora("2026-10-10T23:30:00")).toBe("10/10/2026 23:30");
    expect(fmtDias(18.25)).toBe("18,3 dias");
    expect(fmtDias(null)).toBe("—");
  });
});
