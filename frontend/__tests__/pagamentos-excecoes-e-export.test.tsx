/**
 * Relatório de exceções e exportação de solicitações.
 *
 * Os dois endpoints existiam desde agosto sem tela. No relatório, o modo de
 * falha que importa é o mesmo que o backend evita: lista truncada lida como
 * total ("exibindo 2" não é "há 2").
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const relatorioMock = vi.fn(() =>
  Promise.resolve({
    gerado_em: "2026-10-11",
    total_excecoes: 41,
    regras: [
      {
        codigo: "RN15_SALDO_INSUFICIENTE", titulo: "Autorização com saldo insuficiente",
        descricao: "Despesa autorizada com exceção de saldo.", severidade: "alta",
        total: 40, exibindo: 2,
        itens: [
          { id_debito: 12, justificativa: "Decisão judicial", em: "2026-10-01",
            descricao: "Obra da escola", valor: "9000.00" },
          { id_debito: 15, justificativa: "Urgência", em: "2026-10-02",
            descricao: "Medicamentos", valor: "150.50" },
        ],
      },
      {
        codigo: "DEBITO_DEVOLVIDO", titulo: "Débito devolvido para ajuste",
        descricao: "Voltou ao solicitante.", severidade: "baixa",
        total: 1, exibindo: 1,
        itens: [{ id_debito: 7, descricao: "Locação", valor: "10.00",
                  situacao_tramitacao: "AJUSTE_GESTOR" }],
      },
      {
        codigo: "PAGO_NAO_CONCILIADO", titulo: "Pago ainda não conciliado",
        descricao: "Saiu da tesouraria.", severidade: "baixa", total: 0, exibindo: 0, itens: [],
      },
    ],
  }),
);
const listMock = vi.fn((_p?: unknown) => Promise.resolve([]));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      pagamentos: {
        ...actual.api.pagamentos,
        relatorioExcecoes: relatorioMock,
        debitos: { ...actual.api.pagamentos.debitos, list: listMock },
      },
    },
  };
});

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Auditor", is_super_usuario: false },
    perms: ["pagamento_auditar"],
    loading: false,
    can: (codigo: string) => codigo === "pagamento_auditar",
  }),
}));

function comCliente(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("relatório de exceções", () => {
  it("mostra o total real de cada regra e avisa quando a lista está truncada", async () => {
    const { default: Pagina } = await import("@/app/(app)/m/pagamentos/excecoes/page");
    comCliente(<Pagina />);

    const titulo = await screen.findByRole("heading", { name: "Autorização com saldo insuficiente" });
    const regra = within(titulo.closest("section") as HTMLElement);
    expect(regra.getByText("40 ocorrências")).toBeInTheDocument();
    expect(regra.getByText(/exibindo as 2 primeiras/)).toBeInTheDocument();
    expect(regra.getByText("Severidade alta")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("41 exceções no total");
  });

  it("cada linha leva à solicitação, com valor em reais e etapa em português", async () => {
    const { default: Pagina } = await import("@/app/(app)/m/pagamentos/excecoes/page");
    comCliente(<Pagina />);

    const link = await screen.findByRole("link", { name: "#12" });
    expect(link).toHaveAttribute("href", "/m/pagamentos/solicitacoes/12");
    expect(screen.getByText(/9\.000,00/)).toBeInTheDocument();

    const devolvido = within(
      screen.getByRole("heading", { name: "Débito devolvido para ajuste" }).closest("section") as HTMLElement,
    );
    expect(devolvido.getByText("1 ocorrência")).toBeInTheDocument();
    expect(devolvido.queryByText(/exibindo/)).toBeNull();
    expect(devolvido.queryByText("AJUSTE_GESTOR")).toBeNull();
  });

  it("regra sem ocorrência aparece como conferida, não some", async () => {
    const { default: Pagina } = await import("@/app/(app)/m/pagamentos/excecoes/page");
    comCliente(<Pagina />);
    const conferidas = within(
      (await screen.findByRole("heading", { name: "Regras conferidas sem ocorrência" }))
        .closest("section") as HTMLElement,
    );
    expect(conferidas.getByText("Pago ainda não conciliado")).toBeInTheDocument();
  });
});

describe("exportar solicitações", () => {
  it("o arquivo segue a etapa escolhida no seletor", async () => {
    const { default: Pagina } = await import("@/app/(app)/m/pagamentos/solicitacoes/page");
    comCliente(<Pagina />);
    const exportar = await screen.findByRole("link", {
      name: "Exportar solicitações de pagamento em CSV",
    });
    expect(exportar.getAttribute("href")).toMatch(/\/pagamentos\/debitos\/exportar\.csv$/);

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "AGUARDANDO_GESTOR" } });
    await waitFor(() =>
      expect(exportar.getAttribute("href")).toMatch(
        /\/pagamentos\/debitos\/exportar\.csv\?situacao_tramitacao=AGUARDANDO_GESTOR$/,
      ),
    );
  });
});
