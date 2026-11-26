/**
 * "Fluxo do processo" da frota: o caminho de uma solicitação de veículo, com
 * quantas estão paradas em cada passo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FASES } from "@/components/frota/MapaDaFrota";
import type { SolicitacaoVeiculo } from "@/lib/api";

const estado: { perms: string[] } = { perms: [] };

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: false },
    perms: estado.perms,
    loading: false,
    can: (codigo: string) => estado.perms.includes(codigo),
  }),
}));

const sol = (id: number, status: string, veiculo: number | null = null) =>
  ({ id, status, id_veiculo_designado: veiculo }) as unknown as SolicitacaoVeiculo;

const SOLICITACOES = [
  sol(1, "solicitada"), sol(2, "solicitada"), sol(3, "solicitada"),
  sol(4, "aprovada"),                // aprovada, sem veículo: aguarda designação
  sol(5, "aprovada", 10), sol(6, "aprovada", 11), // designadas: aguardam a saída
  sol(7, "em_uso", 12),
  sol(8, "concluida", 10), sol(9, "concluida", 11),
  sol(10, "rejeitada"), sol(11, "cancelada"),
];
const listAllMock = vi.fn(() => Promise.resolve(SOLICITACOES));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      // Preguiçoso: o `vi.mock` sobe para antes das declarações acima.
      solicitacoes: { ...actual.api.solicitacoes, listAll: () => listAllMock() },
    },
  };
});

async function abrir() {
  const { default: Pagina } = await import("@/app/(app)/m/frota/fluxo/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Pagina />
    </QueryClientProvider>,
  );
}

const passo = (key: string) => within(screen.getByTestId(`passo-${key}`));

vi.setConfig({ testTimeout: 20_000 });

beforeEach(() => {
  estado.perms = ["frota"];
  listAllMock.mockClear();
});
afterEach(cleanup);

describe("fluxo do processo da frota", () => {
  it("mostra os cinco passos na ordem, em duas fases", async () => {
    await abrir();
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Passo 1: Solicitar",
      "Passo 2: Aprovar",
      "Passo 3: Designar veículo e motorista",
      "Passo 4: Registrar a saída",
      "Passo 5: Registrar o retorno",
    ]);
    expect(screen.getByRole("region", { name: "Fase: Pedido" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Fase: Viagem" })).toBeInTheDocument();
  });

  it("separa as aprovadas entre as que esperam veículo e as que esperam a saída", async () => {
    await abrir();
    await passo("aprovar").findByText("3 solicitações aqui agora");
    expect(passo("designar").getByText("1 solicitação aqui agora")).toBeInTheDocument();
    expect(passo("saida").getByText("2 solicitações aqui agora")).toBeInTheDocument();
    expect(passo("retorno").getByText("1 veículo na rua aqui agora")).toBeInTheDocument();
    // Solicitar não tem fila: não inventa quantidade.
    expect(passo("solicitar").queryByText(/aqui agora/)).toBeNull();
  });

  it("diz como as solicitações terminaram", async () => {
    await abrir();
    const cartao = within(
      (await screen.findByText("Como uma solicitação termina")).closest("section") as HTMLElement);
    await waitFor(() =>
      expect(cartao.getAllByRole("listitem").map((li) => li.textContent)).toEqual([
        "Concluídao veículo saiu e voltou2",
        "Rejeitadapela gestão da frota, antes de aprovar1",
        "Canceladaantes de o veículo sair1",
      ]),
    );
  });

  it("quem não opera a frota vê o mapa, sem quantidades nem atalhos de trabalho", async () => {
    estado.perms = [];
    await abrir();
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(5);
    expect(listAllMock).not.toHaveBeenCalled();
    expect(screen.queryByText(/aqui agora/)).toBeNull();
    expect(passo("aprovar").queryByRole("link")).toBeNull();
  });

  it("falha ao buscar quantidades não derruba o mapa", async () => {
    listAllMock.mockRejectedValueOnce(new Error("fora do ar"));
    await abrir();
    await screen.findByText(/Não foi possível carregar as quantidades/);
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(5);
  });
});

describe("os passos repartem as solicitações em andamento", () => {
  it("toda solicitação em andamento está em exatamente um passo; encerrada, em nenhum", () => {
    const predicados = FASES.flatMap((f) => f.passos).flatMap((p) => (p.estaAqui ? [p.estaAqui] : []));
    const emQuantos = (s: SolicitacaoVeiculo) => predicados.filter((p) => p(s)).length;
    const encerradas = new Set(["concluida", "rejeitada", "cancelada"]);
    for (const s of SOLICITACOES) {
      expect(emQuantos(s), `${s.status} #${s.id}`).toBe(encerradas.has(s.status) ? 0 : 1);
    }
  });
});
