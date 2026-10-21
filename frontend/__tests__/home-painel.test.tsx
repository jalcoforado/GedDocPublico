/**
 * Tela inicial como "Painel de controle" (pedido da reunião de 2026-10-20,
 * referência: Painel de Controle do SEI). Cada quadro mostra o número da
 * unidade e leva à lista que o conta.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { PainelUnidade } from "@/lib/api";

const estado: { perms: string[] } = { perms: [] };

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Maria Souza", id_unidade_trabalho: 3 },
    perms: { is_super_usuario: false },
    loading: false,
    can: (codigo: string) => estado.perms.includes(codigo),
  }),
}));

let painel: PainelUnidade;
const painelMock = vi.fn(() => Promise.resolve(painel));
const notifMock = vi.fn(() => Promise.resolve({ items: [], nao_lidas: 4 }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    // Preguiçosos: o `vi.mock` sobe para antes das declarações acima.
    api: { ...actual.api, processos: { ...actual.api.processos, painel: () => painelMock() } },
    notificacoesApi: { ...actual.notificacoesApi, listarMinhas: () => notifMock() },
  };
});

function painelBase(): PainelUnidade {
  return {
    caixas: {
      entrada: 3, saida: 2, analise: 12, externos: 1, aguardando_assinatura: 5,
      enviado_para_assinatura: 1, arquivados: 40, recusados: 2,
    },
    atribuidos_a_mim: 4,
    sem_responsavel: 6,
    prazos: { vencidos: 2, vencendo: 3, no_prazo: 5, sem_prazo: 2 },
    aguardando_retorno: { total: 2, atrasados: 1 },
  };
}

async function abrir() {
  const { default: Pagina } = await import("@/app/(app)/home/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Pagina />
    </QueryClientProvider>,
  );
}

/** O link do quadro que tem aquele rótulo. */
const quadro = (rotulo: string) => screen.getByText(rotulo).closest("a") as HTMLAnchorElement;
const valorDo = (rotulo: string) =>
  within(quadro(rotulo)).getByTestId("kpi-valor").textContent;

vi.setConfig({ testTimeout: 20_000 });

beforeEach(() => {
  estado.perms = ["processo"];
  painel = painelBase();
  painelMock.mockClear();
  notifMock.mockClear();
});
afterEach(cleanup);

describe("painel de controle", () => {
  it("cada quadro mostra o número da unidade e leva à lista que o conta", async () => {
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));

    expect(valorDo("A receber")).toBe("3");
    expect(valorDo("Enviados")).toBe("2");
    expect(valorDo("Recusados")).toBe("2");
    expect(valorDo("Atribuídos a mim")).toBe("4");
    expect(valorDo("Sem responsável")).toBe("6");
    expect(valorDo("Para assinar")).toBe("5");
    await waitFor(() => expect(valorDo("Notificações")).toBe("4"));

    expect(quadro("A receber")).toHaveAttribute(
      "href", "/m/protocolo/processos?caixa=entrada&ativos=0");
    expect(quadro("Recusados")).toHaveAttribute(
      "href", "/m/protocolo/processos?caixa=recusados&ativos=0");
    expect(quadro("Atribuídos a mim")).toHaveAttribute(
      "href", "/m/protocolo/processos?caixa=analise&escopo=meus&ativos=0");
    expect(quadro("Para assinar")).toHaveAttribute("href", "/para-assinar");
  });

  it("recusados ficam em destaque quando há algum, e quietos quando não há", async () => {
    await abrir();
    await waitFor(() => expect(valorDo("Recusados")).toBe("2"));
    expect(quadro("Recusados").innerHTML).toContain("border-l-danger");

    cleanup();
    painel = { ...painelBase(), caixas: { ...painelBase().caixas, recusados: 0 } };
    await abrir();
    await waitFor(() => expect(valorDo("Recusados")).toBe("0"));
    expect(quadro("Recusados").innerHTML).not.toContain("border-l-danger");
  });

  it("as tabelas de prazo, retorno e assinatura trazem os números do painel", async () => {
    await abrir();
    const prazos = within(await screen.findByRole("region", { name: "Controle de prazos" }));
    expect(prazos.getByRole("row", { name: /Prazo vencido 2/ })).toBeInTheDocument();
    expect(prazos.getByRole("row", { name: /Vencendo 3/ })).toBeInTheDocument();
    expect(prazos.getByRole("row", { name: /No prazo 5/ })).toBeInTheDocument();

    const retorno = within(
      screen.getByRole("region", { name: "Aguardando retorno de outras unidades" }));
    expect(retorno.getByRole("row", { name: /Prazo vencido 1/ })).toBeInTheDocument();
    expect(retorno.getByRole("row", { name: /Total enviado 2/ })).toBeInTheDocument();

    const assinaturas = within(screen.getByRole("region", { name: "Assinaturas" }));
    expect(assinaturas.getByRole("link", { name: "5" })).toHaveAttribute("href", "/para-assinar");
  });

  it("sem nenhum prazo na unidade, diz isso em vez de três zeros", async () => {
    painel = { ...painelBase(), prazos: { vencidos: 0, vencendo: 0, no_prazo: 0, sem_prazo: 12 } };
    await abrir();
    const prazos = within(await screen.findByRole("region", { name: "Controle de prazos" }));
    expect(prazos.getByText("Nenhum processo com prazo na unidade.")).toBeInTheDocument();
    expect(prazos.queryByText("Vencendo")).toBeNull();
  });

  it("quem não opera processos vê só as notificações, e o painel não é pedido", async () => {
    estado.perms = [];
    await abrir();
    await waitFor(() => expect(valorDo("Notificações")).toBe("4"));
    expect(screen.queryByText("Na unidade")).toBeNull();
    expect(screen.queryByRole("region", { name: "Controle de prazos" })).toBeNull();
    expect(painelMock).not.toHaveBeenCalled();
  });

  it("falha ao carregar o painel avisa e oferece tentar de novo", async () => {
    painelMock.mockRejectedValueOnce(new Error("fora do ar"));
    await abrir();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar os números da unidade.");
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  });
});
