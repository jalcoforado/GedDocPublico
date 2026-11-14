/**
 * Relatórios do protocolo: o Panorama do Painel de controle e o índice de
 * relatórios (decisão de 2026-11-14), mais o apoio das listas (SI-34/35).
 *
 * O Panorama é a antiga página gerencial no visual do Início: cada bloco
 * leva à lista que produziu o número, com o MESMO recorte. O backend garante
 * que o número é o total dessa lista (`tests/test_relatorios_protocolo_medidas.py`);
 * aqui se garante que o link carrega o recorte certo — sem isso a lista
 * abriria com outro filtro e o número não bateria, com os dois lados "certos".
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { DIAS_PARADO_PANORAMA, PanoramaDoProtocolo, periodoDosUltimos } from "@/components/protocolo/PanoramaDoProtocolo";
import type { RelatorioFiltroInput } from "@/lib/api";
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

import { respostaGerencial } from "./apoio/respostaGerencial";

const nav = { busca: "", replace: vi.fn() };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace, push: vi.fn(), back: vi.fn() }),
  usePathname: () => "/m/protocolo/relatorios",
  useSearchParams: () => new URLSearchParams(nav.busca),
}));

const gerencialMock = vi.fn((_f: unknown) => Promise.resolve(respostaGerencial()));
const salvosMock = vi.fn(() =>
  Promise.resolve([{ id: 7, nome: "Alvarás parados", criado_em: "2026-11-12T10:00:00", atualizado_em: "2026-11-12T10:30:00" }]),
);

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
        salvos: { ...actual.api.relatorios.salvos, list: () => salvosMock() },
      },
      tiposProcesso: { ...actual.api.tiposProcesso, list: () => Promise.resolve([]) },
      assuntos: { ...actual.api.assuntos, list: () => Promise.resolve({ items: [], total: 0 }) },
    },
    organogramaApi: { tree: () => Promise.resolve([]) },
  };
});

function cliente() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

async function abrirPanorama(idUnidade: number | null = 3) {
  render(
    <QueryClientProvider client={cliente()}>
      <PanoramaDoProtocolo idUnidade={idUnidade} nomeUnidade={idUnidade ? "Secretaria de Obras" : null} />
    </QueryClientProvider>,
  );
  await screen.findByRole("region", { name: "Quantos processos entram e quantos saem?" });
  await within(cartao("Abertos")).findByText("142");
}

async function abrirIndice() {
  const { default: Pagina } = await import("@/app/(app)/m/protocolo/relatorios/page");
  render(
    <QueryClientProvider client={cliente()}>
      <Pagina />
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { name: "Relatórios padrão" });
}

/** O cartão de tendência (é um link) com aquele rótulo. */
const cartao = (rotulo: string) =>
  within(screen.getByLabelText("Números do período")).getByText(rotulo, { exact: true }).closest("a") as HTMLAnchorElement;
const destino = (a: Element | null) => {
  const [rota, qs = ""] = (a?.getAttribute("href") ?? "").split("?");
  return { rota, params: Object.fromEntries(new URLSearchParams(qs)) };
};
const quadro = (pergunta: string) => screen.getByRole("region", { name: pergunta });

// Os gráficos são pesados no primeiro import; carrega uma vez, com folga.
beforeAll(async () => {
  await import("@/components/protocolo/PanoramaDoProtocolo");
}, 60_000);

beforeEach(() => {
  gerencialMock.mockClear();
  salvosMock.mockClear();
  nav.replace.mockClear();
});
afterEach(() => cleanup());

// Recorte usado pelos testes de apoio das listas, mais abaixo.
const RECORTE = "desde=2026-10-01&ate=2026-10-31&id_unidade=3&modo_unidade=dona&id_assunto=9";
const ULTIMOS_30 = periodoDosUltimos(30);
const RECORTE_MINHA = { ...ULTIMOS_30, id_unidade: "3", modo_unidade: "envolvida" };

describe("Panorama do protocolo — o segundo andar do Painel de controle", () => {
  it("abre nos últimos 30 dias da unidade ativa (regra de hoje) e mostra os números do gerencial", async () => {
    await abrirPanorama();
    expect(gerencialMock).toHaveBeenCalledWith({
      ...ULTIMOS_30, id_unidade: 3, modo_unidade: "envolvida", dias_parado: DIAS_PARADO_PANORAMA,
    });
    expect(within(cartao("Arquivados")).getByText("41")).toBeInTheDocument();
    expect(within(cartao("Arquivados")).getByText(/18,3 dias/)).toBeInTheDocument();
    expect(within(cartao("Em andamento")).getByText("88")).toBeInTheDocument();
    expect(within(cartao(`Parados há ${DIAS_PARADO_PANORAMA}+ dias`)).getByText("12")).toBeInTheDocument();
    expect(within(cartao("Prazo vencido")).getByText("6")).toBeInTheDocument();
    expect(within(cartao("Assinaturas pendentes")).getByText("16")).toBeInTheDocument();
    expect(screen.getByText(/na unidade Secretaria de Obras/)).toBeInTheDocument();
  });

  it("“Todas” tira a unidade da consulta; o período muda com os botões", async () => {
    await abrirPanorama();
    fireEvent.click(screen.getByRole("radio", { name: "Todas" }));
    await screen.findByText(/em todas as unidades/);
    expect(gerencialMock).toHaveBeenLastCalledWith({ ...ULTIMOS_30, dias_parado: DIAS_PARADO_PANORAMA });
    fireEvent.click(screen.getByRole("radio", { name: "7 dias" }));
    await screen.findByText(/últimos 7 dias/);
    expect(gerencialMock).toHaveBeenLastCalledWith({ ...periodoDosUltimos(7), dias_parado: DIAS_PARADO_PANORAMA });
  });

  it("sem unidade ativa, abre em todas e “Minha unidade” fica desabilitado", async () => {
    await abrirPanorama(null);
    expect(screen.getByRole("radio", { name: "Minha unidade" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Todas" })).toHaveAttribute("aria-checked", "true");
    expect(gerencialMock).toHaveBeenCalledWith({ ...ULTIMOS_30, dias_parado: DIAS_PARADO_PANORAMA });
  });

  it("cada cartão leva à lista de processos na visão que produziu o número, com o recorte", async () => {
    await abrirPanorama();
    const abertos = destino(cartao("Abertos"));
    expect(abertos.rota).toBe("/m/protocolo/relatorios/processos");
    expect(abertos.params).toEqual(expect.objectContaining(RECORTE_MINHA));
    expect(visaoDe(filtroDaUrl(new URLSearchParams(cartao("Abertos").getAttribute("href")!.split("?")[1]))).id).toBe("abertos");
    const porCartao: [string, VisaoProcessos][] = [
      ["Arquivados", "arquivados"],
      ["Em andamento", "em_andamento"],
      [`Parados há ${DIAS_PARADO_PANORAMA}+ dias`, "parados"],
      ["Prazo vencido", "vencidos"],
    ];
    for (const [rotulo, visao] of porCartao) {
      const qs = cartao(rotulo).getAttribute("href")!.split("?")[1];
      expect(visaoDe(filtroDaUrl(new URLSearchParams(qs))).id, rotulo).toBe(visao);
      expect(destino(cartao(rotulo)).params).toEqual(expect.objectContaining(RECORTE_MINHA));
    }
    const assinaturas = destino(cartao("Assinaturas pendentes"));
    expect(assinaturas.rota).toBe("/m/protocolo/relatorios/assinaturas");
    expect(assinaturas.params).toEqual({ ...RECORTE_MINHA, data_base: "pedido" });
  });

  it("cada quadro leva à sua tela com o recorte; as fatias levam ao seu “Mostrar”", async () => {
    await abrirPanorama();
    const ver = (pergunta: string, nome: RegExp) => destino(within(quadro(pergunta)).getByRole("link", { name: nome }));

    const tram = ver("Onde os processos demoram?", /Ver tramitação/);
    expect(tram.rota).toBe("/m/protocolo/relatorios/tramitacao");
    expect(tram.params).toEqual({ ...RECORTE_MINHA, data_base: "chegada" });
    // só quem atrasou entra no ranking
    expect(within(quadro("Onde os processos demoram?")).getByText("Secretaria de Obras")).toBeInTheDocument();
    expect(within(quadro("Onde os processos demoram?")).queryByText("Protocolo Geral")).toBeNull();

    const doc = ver("Os documentos estão em dia?", /Ver documentação/);
    expect(doc.rota).toBe("/m/protocolo/relatorios/documentacao");
    expect(doc.params).toEqual(RECORTE_MINHA);
    const pendentes = destino(within(quadro("Os documentos estão em dia?")).getByRole("link", { name: /Pendentes/ }));
    expect(pendentes.params).toEqual({ ...RECORTE_MINHA, visao: "doc_pendente" });
    const aguardando = destino(within(quadro("Os documentos estão em dia?")).getByRole("link", { name: /4 aguardando/ }));
    expect(aguardando.params.visao).toBe("compl_aberta");

    const ass = ver("Como andam as assinaturas?", /Ver assinaturas/);
    expect(ass.params).toEqual({ ...RECORTE_MINHA, data_base: "pedido" });
    expect(within(quadro("Como andam as assinaturas?")).getByText(/Tempo médio até concluir/)).toBeInTheDocument();

    const vencidos = destino(within(quadro("Os prazos estão sendo cumpridos?")).getByRole("link", { name: /Vencidos/ }));
    expect(visaoDe(filtroDaUrl(new URLSearchParams(vencidos.params))).id).toBe("vencidos");
    expect(within(quadro("Os prazos estão sendo cumpridos?")).getByText(/23 em aberto sem prazo/)).toBeInTheDocument();

    const processos = ver("Quantos processos entram e quantos saem?", /Ver lista de processos/);
    expect(processos.rota).toBe("/m/protocolo/relatorios/processos");
    expect(processos.params).toEqual(RECORTE_MINHA);
  });

  it("sem comparação com o período anterior (decisão de 2026-11-14) e com tabela do gráfico para leitor de tela", async () => {
    await abrirPanorama();
    expect(screen.queryByText(/período anterior/)).toBeNull();
    expect(screen.queryByText(/ vs\. /)).toBeNull();
    const tabela = within(quadro("Quantos processos entram e quantos saem?")).getByRole("table");
    expect(within(tabela).getAllByRole("row")).toHaveLength(3);
    // o PDF é do recorte que está na tela
    const pdf = screen.getByRole("link", { name: /PDF do panorama/ }).getAttribute("href")!;
    expect(pdf).toContain("/relatorios/gerencial.pdf?");
    expect(pdf).toContain("id_unidade=3");
  });
});

describe("Relatórios — o índice", () => {
  it("lista os relatórios padrão com pergunta e quem usa, cada um abrindo a sua lista; sem números", async () => {
    await abrirIndice();
    expect(gerencialMock).not.toHaveBeenCalled();
    const abrir = (titulo: string) => destino(screen.getByRole("link", { name: `Abrir relatório ${titulo}` }));
    expect(abrir("Processos")).toEqual({ rota: "/m/protocolo/relatorios/processos", params: {} });
    expect(abrir("Tramitação")).toEqual({ rota: "/m/protocolo/relatorios/tramitacao", params: { data_base: "chegada" } });
    expect(abrir("Documentação")).toEqual({ rota: "/m/protocolo/relatorios/documentacao", params: {} });
    expect(abrir("Assinaturas")).toEqual({ rota: "/m/protocolo/relatorios/assinaturas", params: { data_base: "pedido" } });
    expect(screen.getAllByText(/Quem usa:/)).toHaveLength(4);
    expect(screen.getByRole("link", { name: /Painel de controle/ })).toHaveAttribute("href", "/m/protocolo/painel");
    expect(screen.queryByRole("link", { name: /CSV/ })).toBeNull();
  });

  it("Meus relatórios lista os salvos da pessoa e leva ao montador", async () => {
    await abrirIndice();
    const grupo = screen.getByRole("region", { name: "Meus relatórios" });
    expect(within(grupo).getByRole("link", { name: /Montar relatório/ })).toHaveAttribute(
      "href",
      "/m/protocolo/relatorios/montar",
    );
    const salvo = await within(grupo).findByRole("link", { name: /Alvarás parados/ });
    // abre pelo id: a definição vem do servidor, que só devolve o que é da pessoa
    expect(salvo).toHaveAttribute("href", "/m/protocolo/relatorios/montar?salvo=7");
    expect(salvo).toHaveTextContent("alterado em 12/11/2026 10:30");
  });
});

describe("filtros próprios das listas, na URL", () => {
  it("link antigo com o sentido “por onde passou” cai no padrão, sem erro do servidor", () => {
    expect(filtroDaUrl(new URLSearchParams("id_unidade=3&modo_unidade=passou")).modo_unidade).toBeUndefined();
  });

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
