/**
 * Formulários dos cadastros e do caixa de Pagamentos no padrão de formulário:
 *  - erro só depois da tentativa (nunca ao abrir), embaixo do campo, com o
 *    foco no primeiro inválido — e nada é enviado;
 *  - o fornecedor muda o rótulo do documento conforme o tipo de pessoa;
 *  - o lançamento no caixa mostra o saldo depois e envia o mesmo corpo de antes.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const fornecedorCreate = vi.fn((_d: unknown) => Promise.resolve({ id: 9 }));
const lancarMock = vi.fn((_d: unknown) => Promise.resolve({ id: 1 }));

vi.mock("@/lib/api", async () => {
  const actual: any = await vi.importActual("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      pagamentos: {
        ...actual.api.pagamentos,
        cadastros: {
          ...actual.api.pagamentos.cadastros,
          fornecedores: {
            list: () => Promise.resolve([]),
            create: (d: unknown) => fornecedorCreate(d),
            update: vi.fn(),
            remove: vi.fn(),
            situacaoHistorico: () => Promise.resolve([]),
            dadosBancarios: vi.fn(),
          },
          contas: {
            list: () =>
              Promise.resolve([{ id: 3, nome: "Conta Movimento", banco: "BB", ativa: true }]),
          },
        },
        caixa: {
          ...actual.api.pagamentos.caixa,
          painel: () =>
            Promise.resolve([
              {
                id_conta: 3, nome: "Conta Movimento", banco: "BB", grupo_despesa: "CUSTEIO",
                saldo_inicial: "0", total_entradas: "1000.00", total_saidas: "0",
                saldo_atual: "1000.00", comprometido: "0", disponivel: "1000.00",
                saldo_minimo_alerta: "0", abaixo_minimo: false, bloqueado: "0",
                disponivel_projetado: "1000.00",
              },
            ]),
          extrato: () => Promise.resolve([]),
          lancar: (d: unknown) => lancarMock(d),
        },
        bloqueios: { list: () => Promise.resolve([]), create: vi.fn(), remove: vi.fn() },
      },
    },
  };
});

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));
vi.mock("@/components/ui/confirm", () => ({ useConfirm: () => vi.fn() }));

function comCliente(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeAll(async () => {
  await import("@/app/(app)/m/pagamentos/cadastros/fornecedores/page");
  await import("@/app/(app)/m/pagamentos/caixa/page");
}, 60_000);

beforeEach(() => {
  fornecedorCreate.mockClear();
  lancarMock.mockClear();
});

describe("novo fornecedor", () => {
  it("não acusa erro ao abrir; ao cadastrar vazio, mostra o que falta, foca e não envia", async () => {
    const { default: Pagina } = await import("@/app/(app)/m/pagamentos/cadastros/fornecedores/page");
    comCliente(<Pagina />);
    fireEvent.click((await screen.findAllByRole("button", { name: /Novo fornecedor/ }))[0]);
    const dialogo = within(await screen.findByRole("dialog"));

    expect(dialogo.queryByText("Informe o CNPJ do fornecedor.")).toBeNull();
    fireEvent.click(dialogo.getByRole("button", { name: "Cadastrar fornecedor" }));

    expect(await dialogo.findByText("Informe o CNPJ do fornecedor.")).toBeInTheDocument();
    expect(dialogo.getByText("Informe o nome como está no documento.")).toBeInTheDocument();
    expect(dialogo.getByLabelText(/^CNPJ/)).toHaveFocus();
    expect(fornecedorCreate).not.toHaveBeenCalled();
  });

  it("pessoa física pede CPF e nome completo, e envia o mesmo corpo de antes", async () => {
    const { default: Pagina } = await import("@/app/(app)/m/pagamentos/cadastros/fornecedores/page");
    comCliente(<Pagina />);
    fireEvent.click((await screen.findAllByRole("button", { name: /Novo fornecedor/ }))[0]);
    const dialogo = within(await screen.findByRole("dialog"));

    fireEvent.click(dialogo.getByRole("radio", { name: "Pessoa física" }));
    fireEvent.change(dialogo.getByLabelText(/^CPF/), { target: { value: "123.456.789-09" } });
    fireEvent.change(dialogo.getByLabelText(/^Nome completo/), { target: { value: "Maria da Silva" } });
    fireEvent.change(dialogo.getByLabelText(/Chave PIX/), { target: { value: "maria@ex.com" } });
    fireEvent.click(dialogo.getByRole("button", { name: "Cadastrar fornecedor" }));

    await waitFor(() =>
      expect(fornecedorCreate).toHaveBeenCalledWith({
        tipo_pessoa: "FISICA",
        cnpj_cpf: "123.456.789-09",
        nome: "Maria da Silva",
        situacao_cadastral: "REGULAR",
        motivo_pendencia: null,
        dados_bancarios: { banco: null, agencia: null, conta: null, chave_pix: "maria@ex.com" },
      }),
    );
  });

  it("situação pendente pede o motivo", async () => {
    const { default: Pagina } = await import("@/app/(app)/m/pagamentos/cadastros/fornecedores/page");
    comCliente(<Pagina />);
    fireEvent.click((await screen.findAllByRole("button", { name: /Novo fornecedor/ }))[0]);
    const dialogo = within(await screen.findByRole("dialog"));

    expect(dialogo.queryByLabelText(/Motivo/)).toBeNull();
    fireEvent.click(dialogo.getByRole("radio", { name: "Pendente" }));
    fireEvent.change(dialogo.getByLabelText(/^CNPJ/), { target: { value: "12.345.678/0001-90" } });
    fireEvent.change(dialogo.getByLabelText(/^Razão social/), { target: { value: "Comercial X" } });
    fireEvent.click(dialogo.getByRole("button", { name: "Cadastrar fornecedor" }));

    expect(await dialogo.findByText(/Diga o que está pendente/)).toBeInTheDocument();
    expect(dialogo.getByLabelText(/Motivo da pendência/)).toHaveFocus();
    expect(fornecedorCreate).not.toHaveBeenCalled();
  });
});

describe("caixa — lançar entrada ou saída", () => {
  it("mostra o saldo depois e envia o lançamento como antes", async () => {
    const { default: Pagina } = await import("@/app/(app)/m/pagamentos/caixa/page");
    comCliente(<Pagina />);
    await screen.findByText("Conta Movimento");
    fireEvent.click(await screen.findByRole("button", { name: /Lançar entrada\/saída/ }));
    const dialogo = within(await screen.findByRole("dialog"));

    // Conta única: já vem escolhida.
    await waitFor(() => expect(dialogo.getByLabelText(/^Conta/)).toHaveValue("3"));
    fireEvent.click(dialogo.getByRole("radio", { name: "Saída" }));
    fireEvent.change(dialogo.getByLabelText(/^Valor/), { target: { value: "250" } });
    expect(await dialogo.findByText(/Saldo depois: R\$\s?750,00/)).toBeInTheDocument();

    fireEvent.click(dialogo.getByRole("button", { name: "Lançar saída" }));
    await waitFor(() =>
      expect(lancarMock).toHaveBeenCalledWith(
        expect.objectContaining({ id_conta: 3, tipo: "SAIDA", origem: "APORTE", valor: 250 }),
      ),
    );
  });

  it("sem valor, não lança: mostra o erro sob o campo", async () => {
    const { default: Pagina } = await import("@/app/(app)/m/pagamentos/caixa/page");
    comCliente(<Pagina />);
    await screen.findByText("Conta Movimento");
    fireEvent.click(await screen.findByRole("button", { name: /Lançar entrada\/saída/ }));
    const dialogo = within(await screen.findByRole("dialog"));
    await waitFor(() => expect(dialogo.getByLabelText(/^Conta/)).toHaveValue("3"));

    fireEvent.click(dialogo.getByRole("button", { name: "Lançar entrada" }));
    expect(await dialogo.findByText(/Informe um valor maior que zero/)).toBeInTheDocument();
    expect(dialogo.getByLabelText(/^Valor/)).toHaveFocus();
    expect(lancarMock).not.toHaveBeenCalled();
  });
});
