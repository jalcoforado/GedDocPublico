/**
 * As filas por etapa pedem ao servidor uma página por situação e contam pelo
 * total real. Antes baixavam a fila inteira e repartiam no navegador.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Pedido = { situacao_tramitacao?: string[]; page?: number; page_size?: number };

let contagem: Record<string, number> = {};

const debito = (id: number, situacao: string) => ({
  id, nome_fornecedor: `Fornecedor ${id}`, descricao: `Débito ${id}`, valor_total: "100.00",
  situacao_tramitacao: situacao,
});

const paginaMock = vi.fn((p?: Pedido) => {
  const situacao = p?.situacao_tramitacao?.[0] ?? "";
  const total = contagem[situacao] ?? 0;
  const page = p?.page ?? 1;
  const tamanho = p?.page_size ?? 10;
  const inicio = (page - 1) * tamanho;
  const qtd = Math.max(0, Math.min(tamanho, total - inicio));
  // ids distintos por situação e por página, para o teste distinguir as linhas
  const base = situacao === "AJUSTE_GESTOR" ? 500 : 100;
  return Promise.resolve({
    items: Array.from({ length: qtd }, (_, i) => debito(base + inicio + i + 1, situacao)),
    total, page, page_size: tamanho,
  });
});
const contagemMock = vi.fn(() => Promise.resolve(contagem));
const listMock = vi.fn(() => Promise.resolve([]));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      pagamentos: {
        ...actual.api.pagamentos,
        debitos: {
          ...actual.api.pagamentos.debitos,
          pagina: paginaMock, contagemPorSituacao: contagemMock, list: listMock,
        },
      },
    },
  };
});

async function abrir(pasta: "gestor" | "concluidas") {
  const { default: Pagina } = await import(`@/app/(app)/m/pagamentos/solicitacoes/${pasta}/page`);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Pagina />
    </QueryClientProvider>,
  );
  await waitFor(() => expect(contagemMock).toHaveBeenCalled());
}

/** Valor do cartão de contagem com aquele rótulo (o título da lista pode repeti-lo). */
const kpi = (rotulo: string) =>
  screen
    .getAllByTestId("kpi-valor")
    .find((v) => within(v.parentElement as HTMLElement).queryByText(rotulo))?.textContent;

afterEach(cleanup);

beforeEach(() => {
  contagem = {};
  paginaMock.mockClear();
  contagemMock.mockClear();
  listMock.mockClear();
});

// O primeiro teste paga a importação a frio da página; em máquina lenta isso
// passa dos 5 s padrão e o estouro deixa a tela montada para o teste seguinte.
vi.setConfig({ testTimeout: 20_000 });

describe("fila por etapa de pagamentos", () => {
  it("conta pelo total do servidor e baixa só uma página de cada situação", async () => {
    contagem = { AGUARDANDO_GESTOR: 23, AJUSTE_GESTOR: 2, AUTORIZADA: 400 };
    await abrir("gestor");

    await waitFor(() => expect(screen.getAllByRole("link", { name: "Analisar" })).toHaveLength(10));

    // 23 na fila, 10 na tela: o cartão mostra a fila, não o que foi baixado.
    expect(kpi("Aguardando decisão")).toBe("23");
    expect(kpi("Aguardando ajustes")).toBe("2");
    expect(screen.getAllByRole("link", { name: "Ver" })).toHaveLength(2);

    // Nunca a listagem inteira, e nunca situação de outra etapa.
    expect(listMock).not.toHaveBeenCalled();
    const pedidos = paginaMock.mock.calls.map((c) => c[0] as Pedido);
    expect(pedidos.map((p) => p.situacao_tramitacao?.[0]).sort()).toEqual(
      ["AGUARDANDO_GESTOR", "AJUSTE_GESTOR"]);
    expect(pedidos.every((p) => p.page === 1 && p.page_size === 10)).toBe(true);
  });

  it("cada seção pagina sozinha, e só mostra controles quando há mais de uma página", async () => {
    contagem = { AGUARDANDO_GESTOR: 23, AJUSTE_GESTOR: 2 };
    await abrir("gestor");
    await waitFor(() => expect(screen.getAllByRole("link", { name: "Analisar" })).toHaveLength(10));

    // Só a seção com 23 itens tem controles; a de 2 não.
    const nav = screen.getByRole("navigation", { name: "Páginas de Aguardando sua decisão" });
    expect(screen.queryByRole("navigation", { name: "Páginas de Aguardando ajustes da unidade" }))
      .toBeNull();
    expect(within(nav).getByText("Página 1 de 3")).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: "Página anterior" })).toBeDisabled();

    paginaMock.mockClear();
    fireEvent.click(within(nav).getByRole("button", { name: "Próxima página" }));
    await screen.findByText("Página 2 de 3");
    await screen.findByText("#111");

    // Só a seção clicada voltou ao servidor.
    expect(paginaMock.mock.calls.map((c) => c[0])).toEqual([
      { situacao_tramitacao: ["AGUARDANDO_GESTOR"], page: 2, page_size: 10 },
    ]);

    fireEvent.click(within(nav).getByRole("button", { name: "Próxima página" }));
    await screen.findByText("Página 3 de 3");
    await waitFor(() => expect(screen.getAllByRole("link", { name: "Analisar" })).toHaveLength(3));
    expect(within(nav).getByRole("button", { name: "Próxima página" })).toBeDisabled();
  });

  it("fila vazia mostra o aviso e não pede página nenhuma", async () => {
    contagem = { AUTORIZADA: 7 };
    await abrir("gestor");
    await screen.findByText("Nenhuma solicitação aguardando sua ação");
    expect(paginaMock).not.toHaveBeenCalled();
  });

  it("concluídas: quatro situações, cada uma com o seu total", async () => {
    contagem = { AUTORIZADA: 12, REJEITADA_GESTOR: 1, CANCELADA: 3, AGUARDANDO_GESTOR: 50 };
    await abrir("concluidas");
    await waitFor(() => expect(screen.getAllByRole("link", { name: "Ver" })).toHaveLength(14));

    expect(kpi("Autorizadas")).toBe("12");
    expect(kpi("Rejeitadas")).toBe("1");
    expect(kpi("Indeferidas")).toBe("0");
    expect(kpi("Canceladas")).toBe("3");
    // Indeferidas está vazia: não vai ao servidor.
    expect(paginaMock.mock.calls.map((c) => (c[0] as Pedido).situacao_tramitacao?.[0]).sort())
      .toEqual(["AUTORIZADA", "CANCELADA", "REJEITADA_GESTOR"]);
  });
});
