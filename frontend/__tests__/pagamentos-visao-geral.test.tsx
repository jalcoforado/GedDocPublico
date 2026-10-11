/**
 * Visão geral de pagamentos × permissão de caixa.
 *
 * O painel de caixa exige `pagamento_cadastro` no backend. A tela o consultava
 * para todo mundo: quem não tinha a permissão levava 403 e via "Nenhuma conta
 * cadastrada" — uma informação falsa, não uma ausência.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const estado = { perms: [] as string[] };
const painelMock = vi.fn(() =>
  Promise.resolve([
    { id_conta: 1, nome: "Conta Movimento", disponivel: "900.00", comprometido: "100.00", saldo_atual: "1000.00" },
  ]),
);
const filaMock = vi.fn(() =>
  Promise.resolve({
    solicitar: [{ id: 7, nome_fornecedor: "Fornecedor X", valor_total: "50.00", descricao: "Teste" }],
    validar: [], encaminhar: [], autorizar: [], liberar: [], pagar: [], pendencias_ajuste: [],
  }),
);

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      pagamentos: {
        ...actual.api.pagamentos,
        minhaFila: filaMock,
        caixa: { ...actual.api.pagamentos.caixa, painel: painelMock },
      },
    },
  };
});

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: false },
    perms: estado.perms,
    loading: false,
    can: (codigo: string) => estado.perms.includes(codigo),
  }),
}));

async function abrir() {
  const { default: Pagina } = await import("@/app/(app)/m/pagamentos/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Pagina />
    </QueryClientProvider>,
  );
  await waitFor(() => expect(filaMock).toHaveBeenCalled());
}

beforeEach(() => {
  painelMock.mockClear();
  filaMock.mockClear();
});

describe("visão geral de pagamentos", () => {
  it("sem pagamento_cadastro: não consulta o caixa nem mostra a seção", async () => {
    estado.perms = ["pagamento_validar"];
    await abrir();
    await screen.findByText("Meus rascunhos");
    expect(painelMock).not.toHaveBeenCalled();
    expect(screen.queryByRole("heading", { name: "Caixa" })).toBeNull();
    expect(screen.queryByText("Nenhuma conta cadastrada.")).toBeNull();
  });

  it("com pagamento_cadastro: mostra o caixa e o caminho até a tela", async () => {
    estado.perms = ["pagamento_cadastro"];
    await abrir();
    expect(await screen.findByText("Conta Movimento")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "ver caixa" })).toHaveAttribute(
      "href", "/m/pagamentos/caixa",
    );
  });

  it("os links dos cards apontam para a rota atual, não para o redirecionamento antigo", async () => {
    estado.perms = ["pagamento_solicitar"];
    await abrir();
    await screen.findByText("Meus rascunhos");
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href") ?? "");
    expect(hrefs.some((h) => h.startsWith("/m/pagamentos/solicitacoes"))).toBe(true);
    expect(hrefs.filter((h) => h.includes("contas-a-pagar"))).toEqual([]);
  });
});
