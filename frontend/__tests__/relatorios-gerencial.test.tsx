/**
 * Página gerencial de relatórios (SI-34). Uma tela, filtro no topo, quatro
 * grupos; cada número leva à lista que o produziu, com o MESMO recorte. O
 * backend garante que o número da seção é o total dessa lista
 * (`tests/test_relatorios_protocolo_medidas.py`); aqui se garante que o link
 * da seção carrega o recorte certo — sem isso a lista abriria com outro
 * filtro e o número não bateria, com os dois lados "certos".
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import type { GerencialResposta, RelatorioFiltroInput } from "@/lib/api";
import {
  VISOES_DOCUMENTACAO,
  VISOES_PROCESSOS,
  comVisao,
  consultaDaDocumentacao,
  consultaDaLista,
  filtroDaUrl,
  filtroParaUrl,
  fmtDataHora,
  fmtDias,
  visaoDe,
  visaoDocDe,
  type VisaoProcessos,
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
      relatorios: {
        ...actual.api.relatorios,
        gerencial: (f: unknown) => gerencialMock(f),
        servicos: () => Promise.resolve([{ id: 5, nome: "Alvará", ativo: true }]),
      },
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
    gargalos: {
      unidades: [
        { id_unidade: 3, unidade: "Secretaria de Obras", chegadas: 20, com_prazo: 10, atrasos: 7, dias_medio: 4.5 },
      ],
      cortado: false,
    },
    assinaturas: { total: 30, pendentes: 6, concluidas: 22, canceladas: 2, minutos_medio_conclusao: 2880 },
    documentacao: {
      pendentes: 5, parciais: 3, completos: 12, sem_documentos_exigidos: 122,
      complementacao_pedida: 7, aguardando_cidadao: 4, complementacao_respondida: 2, dias_medio_resposta: 3.5,
    },
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

/** Os links da página (todos os "Ver …"), por grupo. */
function linksDoGrupo(grupo: string): { rota: string; params: URLSearchParams }[] {
  const regiao = screen.getByRole("region", { name: grupo });
  return within(regiao)
    .queryAllByRole("link")
    .map((a) => {
      const [rota, qs = ""] = a.getAttribute("href")!.split("?");
      return { rota, params: new URLSearchParams(qs) };
    });
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
const RECORTE_PARAMS = {
  desde: "2026-10-01", ate: "2026-10-31", id_unidade: "3", modo_unidade: "passou", id_assunto: "9",
};

describe("página gerencial — grupos por tela de destino, um botão por grupo", () => {
  it("consulta com o recorte da URL e mostra os números", async () => {
    await abrir(RECORTE);
    expect(gerencialMock).toHaveBeenCalledWith({
      id_unidade: 3, modo_unidade: "passou", id_assunto: 9, id_tipo_processo: undefined,
      desde: "2026-10-01", ate: "2026-10-31", dias_parado: 15,
    });
    expect(within(screen.getByRole("region", { name: "Entrada" })).getByText("142")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Saída" })).getByText("18,3 dias")).toBeTruthy();
    expect(
      within(screen.getByRole("region", { name: "Gargalos por unidade" })).getByText("Secretaria de Obras"),
    ).toBeTruthy();
  });

  it("quatro grupos, um link cada, cada um para uma tela diferente", async () => {
    await abrir(RECORTE);
    const grupos = ["Processos", "Tramitação", "Documentação", "Assinaturas"];
    expect(grupos.map((g) => linksDoGrupo(g).length)).toEqual([1, 1, 1, 1]);
    // nenhum outro link na área dos números (o PDF da página fica no cabeçalho)
    const main = document.body;
    const todos = within(main).getAllByRole("link").map((a) => a.getAttribute("href") ?? "");
    const telas = todos.filter((h) => h.startsWith("/m/protocolo/relatorios/")).map((h) => h.split("?")[0]);
    expect(new Set(telas).size).toBe(4);
    expect(telas).toHaveLength(4);
    // e nenhum CSV solto na página: exportar é na lista
    expect(screen.queryByRole("link", { name: /CSV/ })).toBeNull();
  });

  it("cada botão leva o recorte do filtro à sua tela", async () => {
    await abrir(RECORTE);
    const [processos] = linksDoGrupo("Processos");
    expect(processos.rota).toBe("/m/protocolo/relatorios/processos");
    // só o recorte: a lista abre em "abertos no período" e o Mostrar troca
    expect(Object.fromEntries(processos.params)).toEqual(RECORTE_PARAMS);
    const [tramitacao] = linksDoGrupo("Tramitação");
    expect(tramitacao.rota).toBe("/m/protocolo/relatorios/tramitacao");
    expect(Object.fromEntries(tramitacao.params)).toEqual({ ...RECORTE_PARAMS, data_base: "chegada" });
    const [assinaturas] = linksDoGrupo("Assinaturas");
    expect(assinaturas.rota).toBe("/m/protocolo/relatorios/assinaturas");
    expect(Object.fromEntries(assinaturas.params)).toEqual({ ...RECORTE_PARAMS, data_base: "pedido" });
    const [documentacao] = linksDoGrupo("Documentação");
    expect(documentacao.rota).toBe("/m/protocolo/relatorios/documentacao");
    expect(Object.fromEntries(documentacao.params)).toEqual(RECORTE_PARAMS);
  });

  it("o serviço é filtro do recorte comum e vai para todas as telas", async () => {
    await abrir(`${RECORTE}&id_servico=5`);
    expect(gerencialMock).toHaveBeenCalledWith(expect.objectContaining({ id_servico: 5 }));
    for (const g of ["Processos", "Tramitação", "Documentação", "Assinaturas"]) {
      expect(linksDoGrupo(g)[0].params.get("id_servico")).toBe("5");
    }
  });

  it("Documentação: documentos exigidos e complementação, cada número dizendo sua data", async () => {
    await abrir(RECORTE);
    const docs = screen.getByRole("region", { name: "Documentos exigidos" });
    for (const [rotulo, n] of [["Pendentes", "5"], ["Parciais", "3"], ["Completos", "12"]]) {
      const card = within(docs).getByText(rotulo).closest(".rounded-card");
      expect(card?.querySelector("[data-testid=kpi-valor]")?.textContent).toBe(n);
    }
    expect(within(docs).getByText(/122 aberto\(s\) no período/)).toBeTruthy();
    const compl = screen.getByRole("region", { name: "Complementação" });
    expect(within(compl).getByText("pela data do pedido")).toBeTruthy();
    expect(within(compl).getByText("situação de hoje")).toBeTruthy();
    expect(within(compl).getByText("3,5 dias")).toBeTruthy();
  });

  it("Prazos: cinco cartões numa grade só; os sem prazo são ditos", async () => {
    await abrir(RECORTE);
    const regiao = screen.getByRole("region", { name: "Prazos" });
    for (const rotulo of ["No prazo", "Com atraso", "Dentro do prazo", "Vencendo", "Vencidos"]) {
      expect(within(regiao).getByText(rotulo)).toBeTruthy();
    }
    // 32 de 41 com prazo
    expect(within(regiao).getByText("78% dos arquivados com prazo")).toBeTruthy();
    expect(within(regiao).getByText(/0 arquivado\(s\) no período e 23 em aberto/)).toBeTruthy();
    // todos os cartões na MESMA grade — é o que iguala a altura
    const grades = new Set(
      ["No prazo", "Vencidos"].map((r) => within(regiao).getByText(r).closest(".grid")),
    );
    expect(grades.size).toBe(1);
  });

  it("sem comparação com o período anterior nem principais assuntos (decisão de 2026-11-11)", async () => {
    await abrir(RECORTE);
    expect(screen.queryByText(/ vs\. /)).toBeNull();
    // os assuntos viraram o "Agrupar por" da lista de processos
    expect(screen.queryByText("Principais assuntos")).toBeNull();
  });

  it("gráfico com tabela para leitor de tela", async () => {
    await abrir(RECORTE);
    const tabela = within(screen.getByRole("region", { name: "Entrada e saída no tempo" })).getByRole("table");
    expect(within(tabela).getAllByRole("row")).toHaveLength(3);
  });
});

describe("filtros próprios das listas, na URL", () => {
  it("serviço, sigilo, origem e atraso vão e voltam pela URL; valor estranho é ignorado", () => {
    const f = filtroDaUrl(
      new URLSearchParams("id_servico=5&sigilo=sigiloso&origem=externa&com_atraso=true&visao=doc_parcial"),
    );
    expect(f).toMatchObject({
      id_servico: 5, sigilo: "sigiloso", origem: "externa", com_atraso: true, visao: "doc_parcial",
    });
    expect(filtroDaUrl(new URLSearchParams(filtroParaUrl(f).slice(1)))).toEqual(f);
    const estranho = filtroDaUrl(new URLSearchParams("sigilo=secreto&origem=x&com_atraso=1&visao=tudo"));
    expect([estranho.sigilo, estranho.origem, estranho.com_atraso, estranho.visao]).toEqual([
      undefined, undefined, undefined, undefined,
    ]);
  });

  it("trocar o Mostrar mantém sigilo e origem; a consulta os leva", () => {
    const f = filtroDaUrl(new URLSearchParams(`${RECORTE}&sigilo=sigiloso&origem=interna`));
    const vencidos = comVisao(f, "vencidos");
    expect([vencidos.sigilo, vencidos.origem]).toEqual(["sigiloso", "interna"]);
    expect(consultaDaLista(vencidos)).toMatchObject({ sigilo: "sigiloso", origem: "interna", prazo: "atrasado" });
  });
});

describe("lista de documentação — o Mostrar é a consulta de cada número do grupo", () => {
  it.each(VISOES_DOCUMENTACAO.map((v) => [v.id, v.hoje] as const))("%s (hoje=%s)", (id, hoje) => {
    const f = { ...filtroDaUrl(new URLSearchParams(RECORTE)), visao: id };
    expect(visaoDocDe(f).id).toBe(id);
    const c = consultaDaDocumentacao(f);
    expect(c.visao).toBe(id);
    expect(c.desde).toBe(hoje ? undefined : "2026-10-01");
    expect(c.id_unidade).toBe(3);
    expect(c.data_base).toBeUndefined();
  });

  it("só \"aguardando o cidadão\" é situação de hoje", () => {
    expect(VISOES_DOCUMENTACAO.filter((v) => v.hoje).map((v) => v.id)).toEqual(["compl_aberta"]);
  });

  it("sem visão na URL, abre em todos os que exigem documentos", () => {
    expect(visaoDocDe(filtroDaUrl(new URLSearchParams(RECORTE))).id).toBe("documentos");
  });
});

describe("lista de processos — o Mostrar é a consulta de cada número da página", () => {
  // Os parâmetros que o backend usa para provar "número da página = total da
  // lista" (`test_relatorios_protocolo_medidas.py`). Cada visão tem de pedir
  // exatamente isto; mudar um lado sem o outro quebra a conferência.
  const ESPERADO: Record<VisaoProcessos, Partial<RelatorioFiltroInput>> = {
    abertos: { data_base: "abertura" },
    arquivados: { data_base: "arquivamento" },
    em_andamento: { data_base: "abertura", situacao: "em_andamento" },
    em_transito: { data_base: "abertura", situacao: "em_transito" },
    parados: { data_base: "abertura", parado_ha_dias: 15 },
    no_prazo: { data_base: "arquivamento", prazo: "concluido_no_prazo" },
    com_atraso: { data_base: "arquivamento", prazo: "concluido_atrasado" },
    dentro_do_prazo: { data_base: "abertura", prazo: "dentro_do_prazo" },
    vencendo: { data_base: "abertura", prazo: "vencendo" },
    vencidos: { data_base: "abertura", prazo: "atrasado" },
  };

  it.each(VISOES_PROCESSOS.map((v) => [v.id, v.hoje] as const))(
    "%s pede a consulta certa (hoje=%s)",
    (id, hoje) => {
      const url = comVisao(filtroDaUrl(new URLSearchParams(RECORTE)), id);
      expect(visaoDe(url).id).toBe(id);
      const c = consultaDaLista(url);
      const { situacao, parado_ha_dias, prazo, data_base } = c;
      expect(
        Object.fromEntries(
          Object.entries({ situacao, parado_ha_dias, prazo, data_base }).filter(([, v]) => v !== undefined),
        ),
      ).toEqual(ESPERADO[id]);
      // "de hoje" ignora o período na consulta, mas a URL o guarda
      expect(c.desde).toBe(hoje ? undefined : "2026-10-01");
      expect(url.desde).toBe("2026-10-01");
      expect(c.id_unidade).toBe(3);
    },
  );

  it("sem nada na URL, a lista abre em abertos no período", () => {
    expect(visaoDe(filtroDaUrl(new URLSearchParams(RECORTE))).id).toBe("abertos");
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
