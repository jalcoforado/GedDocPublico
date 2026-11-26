/**
 * "Fluxo do processo" do transporte regulado: três caminhos independentes
 * (alvará, recadastramento, ocorrência), cada um com a própria numeração.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const estado: { perms: string[] } = { perms: [] };

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: false },
    perms: estado.perms,
    loading: false,
    can: (codigo: string) => estado.perms.includes(codigo),
  }),
}));

const kpisMock = vi.fn(() =>
  Promise.resolve({ total_alvaras: 50, ativos: 30, vencidos: 12, a_renovar_30d: 4, indefinidos: 4 }),
);
const ciclosMock = vi.fn((_p?: Record<string, unknown>) =>
  Promise.resolve({ items: [], total: 1, page: 1, page_size: 1 }),
);
const ocorrenciasMock = vi.fn((p?: { situacao?: string }) =>
  Promise.resolve({
    items: [], total: p?.situacao === "registrada" ? 5 : 2, page: 1, page_size: 1,
  }),
);

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      // Preguiçosos: o `vi.mock` sobe para antes das declarações acima.
      alvaras: {
        ...actual.api.alvaras,
        relatorio: { ...actual.api.alvaras.relatorio, kpis: () => kpisMock() },
      },
      recadastramento: {
        ...actual.api.recadastramento,
        ciclos: {
          ...actual.api.recadastramento.ciclos,
          list: (p?: Record<string, unknown>) => ciclosMock(p),
        },
      },
      ocorrenciasTransporte: {
        ...actual.api.ocorrenciasTransporte,
        list: (p?: { situacao?: string }) => ocorrenciasMock(p),
      },
    },
  };
});

async function abrir() {
  const { default: Pagina } = await import("@/app/(app)/m/transporte/fluxo/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Pagina />
    </QueryClientProvider>,
  );
}

const passo = (key: string) => within(screen.getByTestId(`passo-${key}`));
const titulosDe = (fluxo: string) =>
  within(screen.getByRole("region", { name: `Fluxo: ${fluxo}` }))
    .getAllByRole("heading", { level: 3 })
    .map((h) => h.textContent);

vi.setConfig({ testTimeout: 20_000 });

beforeEach(() => {
  estado.perms = ["transporte_regulado"];
  for (const m of [kpisMock, ciclosMock, ocorrenciasMock]) m.mockClear();
});
afterEach(cleanup);

describe("fluxo do processo do transporte regulado", () => {
  it("são três caminhos, cada um numerado a partir de 1", async () => {
    await abrir();
    expect(titulosDe("Alvará")).toEqual([
      "Passo 1: Cadastrar titular e veículos",
      "Passo 2: Emitir o alvará",
      "Passo 3: Renovar ou revogar",
    ]);
    expect(titulosDe("Recadastramento")).toEqual([
      "Passo 1: Abrir o ciclo",
      "Passo 2: Convocar",
      "Passo 3: Atender e conferir",
      "Passo 4: Decidir",
    ]);
    expect(titulosDe("Ocorrência")).toEqual([
      "Passo 1: Registrar",
      "Passo 2: Iniciar a apuração",
      "Passo 3: Apurar e decidir",
    ]);
  });

  it("mostra o que há em cada passo que tem contagem confiável", async () => {
    await abrir();
    await passo("iniciar-apuracao").findByText("5 ocorrências aguardam apuração aqui agora");
    expect(passo("decidir-ocorrencia").getByText("2 ocorrências em apuração aqui agora"))
      .toBeInTheDocument();
    expect(passo("ciclo").getByText("1 ciclo aberto aqui agora")).toBeInTheDocument();
    expect(await screen.findByText("4 vencem em 30 dias")).toBeInTheDocument();

    // Pede só o total, por situação — nunca a listagem inteira.
    expect(ocorrenciasMock.mock.calls.map((c) => c[0])).toEqual(
      expect.arrayContaining([
        { situacao: "registrada", page_size: 1 },
        { situacao: "em_apuracao", page_size: 1 },
      ]),
    );
    expect(ciclosMock).toHaveBeenCalledWith({ situacao: "aberto", page_size: 1 });
  });

  it("os passos de alvará não mostram quantidade", async () => {
    // O relatório conta pela validade e inclui alvará já renovado ou revogado:
    // os 12 "vencidos" não são 12 alvarás esperando renovação.
    await abrir();
    await screen.findByText("4 vencem em 30 dias");
    for (const key of ["cadastrar", "emitir", "renovar"]) {
      expect(passo(key).queryByText(/aqui agora/)).toBeNull();
    }
  });

  it("deferir e indeferir aparecem como saídas da decisão do recadastramento", async () => {
    await abrir();
    const saidas = within(
      passo("decidir-recadastramento").getByRole("list", { name: "Saídas de Decidir" }));
    expect(saidas.getByText("recadastramento concluído")).toBeInTheDocument();
    expect(saidas.getByText("encerra, com o parecer")).toBeInTheDocument();
  });

  it("quem não opera o módulo vê o mapa, sem quantidades nem atalhos de trabalho", async () => {
    estado.perms = [];
    await abrir();
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(10);
    for (const m of [kpisMock, ciclosMock, ocorrenciasMock]) expect(m).not.toHaveBeenCalled();
    expect(screen.queryByText(/aqui agora/)).toBeNull();
    expect(passo("emitir").queryByRole("link")).toBeNull();
  });

  it("falha numa das consultas avisa e mantém as outras quantidades", async () => {
    kpisMock.mockRejectedValueOnce(new Error("fora do ar"));
    await abrir();
    await screen.findByText(/Não foi possível carregar todas as quantidades/);
    expect(await passo("ciclo").findByText("1 ciclo aberto aqui agora")).toBeInTheDocument();
    expect(screen.queryByText(/vencem em 30 dias/)).toBeNull();
  });
});
