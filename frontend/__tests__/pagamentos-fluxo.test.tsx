/**
 * "Fluxo do processo": o mapa do pagamento para quem opera. Mostra os sete
 * passos em ordem, marca os que são do usuário, diz quanto trabalho há em cada
 * um e só oferece o atalho da tela a quem pode trabalhar ali.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FASES } from "@/components/pagamentos/MapaDoProcesso";
import { SITUACOES_POR_ETAPA } from "@/components/pagamentos/statusFluxo";

const estado: { perms: string[] } = { perms: [] };
let contagem: Record<string, number> = {};
let fila: Record<string, unknown[] | null> = {};

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: false },
    perms: estado.perms,
    loading: false,
    can: (codigo: string) => estado.perms.includes(codigo),
  }),
}));

const contagemMock = vi.fn(() => Promise.resolve(contagem));
const filaMock = vi.fn(() => Promise.resolve(fila));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      pagamentos: {
        ...actual.api.pagamentos,
        // Preguiçoso: o `vi.mock` sobe para antes das declarações acima.
        minhaFila: () => filaMock(),
        debitos: { ...actual.api.pagamentos.debitos, contagemPorSituacao: () => contagemMock() },
      },
    },
  };
});

async function abrir() {
  const { default: Pagina } = await import("@/app/(app)/m/pagamentos/fluxo/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Pagina />
    </QueryClientProvider>,
  );
  await waitFor(() => expect(contagemMock).toHaveBeenCalled());
}

const passo = (key: string) => within(screen.getByTestId(`passo-${key}`));

vi.setConfig({ testTimeout: 20_000 });

beforeEach(() => {
  estado.perms = [];
  contagem = {};
  fila = { liberar: null, pagar: null };
  contagemMock.mockClear();
  filaMock.mockClear();
});
afterEach(cleanup);

describe("fluxo do processo de pagamentos", () => {
  it("mostra os sete passos na ordem do processo, em duas fases", async () => {
    await abrir();
    const titulos = screen
      .getAllByRole("heading", { level: 3 })
      .map((h) => h.textContent);
    expect(titulos).toEqual([
      "Passo 1: Solicitar",
      "Passo 2: Analisar o mérito",
      "Passo 3: Validar",
      "Passo 4: Autorizar a despesa",
      "Passo 5: Liberar o pagamento",
      "Passo 6: Pagar",
      "Passo 7: Conciliar",
    ]);
    expect(screen.getByRole("region", { name: "Fase: Decisão" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Fase: Execução" })).toBeInTheDocument();
  });

  it("diz quanto há em cada passo; ajustes pendentes contam na unidade", async () => {
    contagem = {
      RASCUNHO: 2, AJUSTE_GESTOR: 1, AJUSTE_VALIDACAO: 1, AGUARDANDO_GESTOR: 1,
      AGUARDANDO_AUTORIDADE: 4, AUTORIZADA: 30, CANCELADA: 5,
    };
    await abrir();

    await passo("solicitar").findByText("4 solicitações aqui agora");
    expect(passo("gerir").getByText("1 solicitação aqui agora")).toBeInTheDocument();
    expect(passo("validar").getByText("Nada aqui agora")).toBeInTheDocument();
    expect(passo("autorizar").getByText("4 solicitações aqui agora")).toBeInTheDocument();
    // Sem leitura da fila de execução, o passo não inventa um zero.
    expect(passo("pagar").queryByText(/aqui agora/)).toBeNull();
  });

  it("marca a etapa de quem está logado e só a ela oferece o atalho", async () => {
    estado.perms = ["pagamento_pagar"];
    fila = { liberar: null, pagar: [{ id: 1 }, { id: 2 }, { id: 3 }] };
    await abrir();

    await passo("pagar").findByText("3 parcelas aqui agora");
    expect(passo("pagar").getByText("Sua etapa")).toBeInTheDocument();
    expect(passo("pagar").getByRole("link", { name: "Abrir tesouraria" })).toHaveAttribute(
      "href", "/m/pagamentos/tesouraria");
    // A conciliação também é da tesouraria.
    expect(passo("conciliar").getByText("Sua etapa")).toBeInTheDocument();

    for (const key of ["solicitar", "gerir", "validar", "autorizar", "liberar"]) {
      expect(passo(key).queryByText("Sua etapa")).toBeNull();
      expect(passo(key).queryByRole("link")).toBeNull();
    }
    // Quem não audita não vê o atalho da trilha.
    expect(screen.queryByRole("link", { name: "Trilha de auditoria" })).toBeNull();
  });

  it("cada decisão diz para onde a solicitação vai", async () => {
    await abrir();
    const saidas = within(passo("validar").getByRole("list", { name: "Saídas de Validar" }));
    expect(saidas.getByText("vai para a autoridade")).toBeInTheDocument();
    expect(saidas.getByText("volta para a unidade")).toBeInTheDocument();
    // A validação não encerra solicitação: valida ou devolve.
    expect(saidas.queryByText("encerra a solicitação")).toBeNull();
  });

  it("falha ao buscar quantidades não derruba o mapa", async () => {
    contagemMock.mockRejectedValueOnce(new Error("fora do ar"));
    await abrir();
    await screen.findByText(/Não foi possível carregar as quantidades/);
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(7);
  });
});

describe("o mapa não diverge das etapas da listagem", () => {
  it("toda situação em andamento pertence a exatamente um passo de decisão", () => {
    const noMapa = FASES[0].passos.flatMap((p) => p.situacoes ?? []);
    expect(new Set(noMapa).size).toBe(noMapa.length);
    const encerradas = ["REJEITADA_GESTOR", "INDEFERIDA_AUTORIDADE", "CANCELADA", "AUTORIZADA"];
    const emAndamento = SITUACOES_POR_ETAPA.flat().filter((s) => !encerradas.includes(s));
    expect([...noMapa].sort()).toEqual([...emAndamento].sort());
  });
});
