/**
 * Montar relatório (SI-35). O que se trava aqui é a costura da tela:
 *
 * - "Gerar relatório" aplica a definição NA URL (`?d=`), e é essa definição
 *   que vai ao backend e aos links de CSV e PDF — o que se exporta é o que
 *   está na tela, não o rascunho do formulário;
 * - abrir um salvo (`?salvo=`) aplica a definição que veio do servidor;
 * - salvar manda nome e definição e passa a URL para o salvo;
 * - sem coluna não se gera nem se salva.
 *
 * Quem vê o quê é do backend (`backend/tests/test_relatorio_montado.py`):
 * nenhum teste daqui afirma proteger dado.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "@/components/ui/confirm";
import { ToastProvider } from "@/components/ui/toast";
import type { CatalogoMontado, DefinicaoMontado, ResultadoMontado } from "@/lib/api";

const nav = { busca: "", replace: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace, push: nav.push, back: vi.fn() }),
  usePathname: () => "/m/protocolo/relatorios/montar",
  useSearchParams: () => new URLSearchParams(nav.busca),
}));

const CATALOGO: CatalogoMontado = {
  colunas: [
    { chave: "aberto_em", rotulo: "Aberto em", grupo: "Processo", tipo: "data_hora" },
    { chave: "situacao", rotulo: "Situação", grupo: "Processo", tipo: "texto" },
    { chave: "assunto", rotulo: "Assunto", grupo: "Processo", tipo: "texto" },
    { chave: "unidade_dona", rotulo: "Unidade dona", grupo: "Processo", tipo: "texto" },
    { chave: "local_atual", rotulo: "Onde está", grupo: "Processo", tipo: "texto" },
    { chave: "tram_atrasos", rotulo: "Etapas atrasadas", grupo: "Tramitação", tipo: "numero" },
  ],
  colunas_padrao: ["aberto_em", "situacao", "assunto", "unidade_dona", "local_atual"],
  ordens: { numero: "Número", aberto_em: "Aberto em" } as CatalogoMontado["ordens"],
  agrupamentos: { assunto: "Assunto" } as CatalogoMontado["agrupamentos"],
  max_colunas: 30,
};

function resultado(d: DefinicaoMontado): ResultadoMontado {
  return {
    definicao: d,
    colunas: d.colunas.map((c) => CATALOGO.colunas.find((x) => x.chave === c)!),
    descricao_filtros: ["Período: 14/10/2026 a 12/11/2026, pela data de abertura"],
    desde: "2026-10-14",
    ate: "2026-11-12",
    totais: { total: 1, em_andamento: 1, em_transito: 0, arquivados: 0 },
    rotulo_agrupamento: null,
    agrupamento: null,
    linhas: [
      {
        id: 42,
        numero_processo: "00042/2026",
        nivel_sigilo: "reservado",
        valores: { aberto_em: "2026-11-01T09:15:00", situacao: "Em andamento", tram_atrasos: 2 },
      },
    ],
    cortado: false,
    avisos: [],
  };
}

const montadoMock = vi.fn((d: DefinicaoMontado) => Promise.resolve(resultado(d)));
const createMock = vi.fn((body: { nome: string; definicao: DefinicaoMontado }) =>
  Promise.resolve({ id: 9, nome: body.nome, criado_em: "", atualizado_em: "", definicao: body.definicao, avisos: [] }),
);
const SALVO: DefinicaoMontado = { colunas: ["assunto", "tram_atrasos"], filtros: { com_atraso: true }, periodo: { tipo: "mes_atual" } };
const getMock = vi.fn((id: number) =>
  Promise.resolve({ id, nome: "Atrasados do mês", criado_em: "", atualizado_em: "", definicao: SALVO, avisos: [] }),
);

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      relatorios: {
        ...actual.api.relatorios,
        montadoCatalogo: () => Promise.resolve(CATALOGO),
        montado: (d: DefinicaoMontado) => montadoMock(d),
        servicos: () => Promise.resolve([]),
        salvos: {
          list: () => Promise.resolve([]),
          get: (id: number) => getMock(id),
          create: (b: { nome: string; definicao: DefinicaoMontado }) => createMock(b),
          update: vi.fn(),
          remove: vi.fn(),
        },
      },
      tiposProcesso: { ...actual.api.tiposProcesso, list: () => Promise.resolve([]) },
      assuntos: { ...actual.api.assuntos, list: () => Promise.resolve({ items: [], total: 0 }) },
    },
    organogramaApi: { tree: () => Promise.resolve([]) },
  };
});

async function abrir(busca = "") {
  nav.busca = busca;
  const { default: Pagina } = await import("@/app/(app)/m/protocolo/relatorios/montar/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const r = render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ConfirmProvider>
          <Pagina />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  await screen.findByRole("group", { name: "Processo" });
  return r;
}

function definicaoDe(url: string): DefinicaoMontado {
  return JSON.parse(new URL(url, "http://x").searchParams.get("d") ?? "null");
}

beforeEach(() => {
  nav.replace.mockReset();
  nav.push.mockReset();
  montadoMock.mockClear();
  createMock.mockClear();
  getMock.mockClear();
});
afterEach(cleanup);

describe("montar relatório", () => {
  it("Gerar relatório aplica a definição na URL, com as colunas escolhidas", async () => {
    await abrir();
    expect(montadoMock).not.toHaveBeenCalled(); // nada aplicado ainda
    fireEvent.click(screen.getByLabelText("Etapas atrasadas"));
    fireEvent.click(screen.getByRole("button", { name: "Gerar relatório" }));
    const url = nav.replace.mock.calls.at(-1)![0] as string;
    expect(url.startsWith("/m/protocolo/relatorios/montar?d=")).toBe(true);
    const d = definicaoDe(url);
    expect(d.colunas).toEqual(["aberto_em", "situacao", "assunto", "unidade_dona", "local_atual", "tram_atrasos"]);
    expect(d.periodo).toEqual({ tipo: "ultimos_dias", dias: 30 });
  });

  it("mostra o resultado da definição aplicada, e o CSV/PDF levam a mesma", async () => {
    const d: DefinicaoMontado = { colunas: ["aberto_em", "tram_atrasos"], filtros: {}, periodo: { tipo: "sem" }, agrupar_por: null, ordem: null, ordem_desc: true };
    await abrir(`d=${encodeURIComponent(JSON.stringify(d))}`);
    const tabela = await screen.findByRole("table");
    expect(montadoMock).toHaveBeenCalledWith(d);
    expect(within(tabela).getByRole("columnheader", { name: "Etapas atrasadas" })).toBeInTheDocument();
    expect(within(tabela).getByText("01/11/2026 09:15")).toBeInTheDocument();
    expect(within(tabela).getByRole("link", { name: "00042/2026" })).toHaveAttribute("href", "/m/protocolo/processos/42");
    const csv = screen.getByRole("link", { name: /CSV/ }).getAttribute("href")!;
    expect(definicaoDe(csv)).toEqual(d);
  });

  it("com mudança ainda não aplicada, não oferece exportar o que não está na tela", async () => {
    const d: DefinicaoMontado = { colunas: ["aberto_em"], filtros: {}, periodo: { tipo: "sem" }, agrupar_por: null, ordem: null, ordem_desc: true };
    await abrir(`d=${encodeURIComponent(JSON.stringify(d))}`);
    await screen.findByRole("table");
    fireEvent.click(within(screen.getByRole("group", { name: "Processo" })).getByLabelText("Assunto"));
    expect(screen.queryByRole("link", { name: /CSV/ })).toBeNull();
    expect(screen.getByText("Há mudanças ainda não aplicadas ao resultado.")).toBeInTheDocument();
  });

  it("abrir um salvo aplica a definição que veio do servidor", async () => {
    await abrir("salvo=7");
    await waitFor(() => expect(nav.replace).toHaveBeenCalled());
    expect(getMock).toHaveBeenCalledWith(7);
    const url = nav.replace.mock.calls.at(-1)![0] as string;
    expect(new URL(url, "http://x").searchParams.get("salvo")).toBe("7");
    expect(definicaoDe(url).colunas).toEqual(["assunto", "tram_atrasos"]);
    expect(definicaoDe(url).filtros).toEqual({ com_atraso: true });
  });

  it("salvar pede o nome, manda nome e definição e passa a URL para o salvo", async () => {
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: /Salvar relatório/ }));
    const dialogo = await screen.findByRole("dialog");
    fireEvent.change(within(dialogo).getByLabelText(/Nome do relatório/), { target: { value: "Meus abertos" } });
    fireEvent.click(within(dialogo).getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(createMock).toHaveBeenCalled());
    expect(createMock.mock.calls[0][0].nome).toBe("Meus abertos");
    expect(createMock.mock.calls[0][0].definicao.colunas).toHaveLength(5);
    await waitFor(() => expect(nav.replace).toHaveBeenCalled());
    expect(new URL(nav.replace.mock.calls.at(-1)![0] as string, "http://x").searchParams.get("salvo")).toBe("9");
  });

  it("sem nenhuma coluna não gera nem salva", async () => {
    await abrir();
    for (const rotulo of ["Aberto em", "Situação", "Assunto", "Unidade dona", "Onde está"]) {
      fireEvent.click(within(screen.getByRole("group", { name: "Processo" })).getByLabelText(rotulo));
    }
    expect(screen.getByRole("alert")).toHaveTextContent("Escolha pelo menos uma coluna.");
    expect(screen.getByRole("button", { name: "Gerar relatório" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Salvar relatório/ })).toBeDisabled();
  });

  it("arrastar e soltar muda a ordem das colunas", async () => {
    await abrir();
    const lista = screen.getByRole("list", { name: "Colunas escolhidas" });
    const itens = () => within(lista).getAllByRole("listitem");
    const dt = { effectAllowed: "", dropEffect: "", setData: vi.fn(), getData: vi.fn() };
    // "Onde está" (último) solto sobre "Situação" (segundo): vai para antes dele
    fireEvent.dragStart(itens()[4], { dataTransfer: dt });
    fireEvent.dragOver(itens()[1], { dataTransfer: dt });
    fireEvent.drop(itens()[1], { dataTransfer: dt });
    expect(itens().map((li) => li.textContent)).toEqual(["Aberto em", "Onde está", "Situação", "Assunto", "Unidade dona"]);
    // "Aberto em" (primeiro) solto sobre "Assunto": arrastando para baixo, cai depois dele
    fireEvent.dragStart(itens()[0], { dataTransfer: dt });
    fireEvent.dragOver(itens()[3], { dataTransfer: dt });
    fireEvent.drop(itens()[3], { dataTransfer: dt });
    expect(itens().map((li) => li.textContent)).toEqual(["Onde está", "Situação", "Assunto", "Aberto em", "Unidade dona"]);
    // e é essa ordem que vai para o relatório
    fireEvent.click(screen.getByRole("button", { name: "Gerar relatório" }));
    expect(definicaoDe(nav.replace.mock.calls.at(-1)![0] as string).colunas).toEqual([
      "local_atual", "situacao", "assunto", "aberto_em", "unidade_dona",
    ]);
  });

  it("pelo teclado, a alça move com as setas e anuncia a posição", async () => {
    await abrir();
    const lista = screen.getByRole("list", { name: "Colunas escolhidas" });
    fireEvent.keyDown(within(lista).getByRole("button", { name: /Mover Assunto/ }), { key: "ArrowUp" });
    expect(within(lista).getAllByRole("listitem").map((li) => li.textContent)).toEqual(
      ["Aberto em", "Assunto", "Situação", "Unidade dona", "Onde está"],
    );
    expect(screen.getByText("Assunto: posição 2 de 5")).toBeInTheDocument();
    // no topo, seta para cima não faz nada
    fireEvent.keyDown(within(lista).getByRole("button", { name: /Mover Aberto em/ }), { key: "ArrowUp" });
    expect(within(lista).getAllByRole("listitem")[0]).toHaveTextContent("Aberto em");
  });
});
