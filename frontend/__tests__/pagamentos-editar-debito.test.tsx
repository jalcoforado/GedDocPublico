/**
 * Edição da solicitação de pagamento e o campo "Categoria".
 *
 * Dois modos de falha que existiam e não podem voltar:
 *  - o formulário prometia "poderá editar enquanto estiver em rascunho" e não
 *    havia tela de edição;
 *  - débito sem contrato precisa de categoria para a liquidação ser
 *    confirmada, e o formulário não tinha o campo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, back: vi.fn() }),
  usePathname: () => "/m/pagamentos/solicitacoes/20/editar",
  useSearchParams: () => new URLSearchParams(),
}));

const estado = {
  tramitacao: "RASCUNHO",
  id_contrato: null as number | null,
  categoria: null as string | null,
  parcelas: [
    { id: 1, id_debito: 20, numero: 1, valor: "1000.00", vencimento: "2026-10-30", status: "ABERTA" },
  ] as Array<Record<string, unknown>>,
};

const createMock = vi.fn((_d: unknown) => Promise.resolve({ id: 31 }));
const updateMock = vi.fn((_id: number, _d: unknown) => Promise.resolve({ id: 20 }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      unidades: {
        ...actual.api.unidades,
        list: () => Promise.resolve({ items: [{ id: 5, unidade_trabalho: "Secretaria de Saúde" }] }),
      },
      pagamentos: {
        ...actual.api.pagamentos,
        cadastros: {
          ...actual.api.pagamentos.cadastros,
          fornecedores: { list: () => Promise.resolve([{ id: 1, nome: "Fornecedor X" }]) },
          naturezas: { list: () => Promise.resolve([{ id: 2, descricao: "Material de consumo" }]) },
          fontes: { list: () => Promise.resolve([{ id: 3, codigo: "500", descricao: "Própria" }]) },
          contratos: { list: () => Promise.resolve([{ id: 9, numero: "CT-9" }]) },
        },
        debitos: {
          ...actual.api.pagamentos.debitos,
          create: createMock,
          update: updateMock,
          get: () => Promise.resolve({
            id: 20, id_fornecedor: 1, nome_fornecedor: "Fornecedor X", id_natureza: 2,
            id_fonte_recursos: 3, id_conta: null, id_conta_pagadora: null,
            id_contrato: estado.id_contrato, categoria: estado.categoria,
            valor_total: "1000.00", competencia: "2026-10", numero_ne: null, numero_nf: "NF-7",
            criticidade: "MEDIA", urgente: false, justificativa_urgencia: null,
            descricao: "Compra de material", status: "RASCUNHO",
            situacao_tramitacao: estado.tramitacao, situacao_fila: "NAO_REGISTRADA",
            situacao_pagamento: "NAO_INICIADA", id_unidade: 5, versao: 1, lock_version: 0,
            id_gestor_decisor: null, id_validador: null, id_usuario_solicitante: 1,
            liquidacao_confirmada: false, data_liquidacao: null,
            criado_em: "2026-10-01T10:00:00Z", atualizado_em: null,
            parcelas: estado.parcelas, historico: [],
          }),
        },
      },
    },
  };
});

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const auth = { id_unidade_trabalho: 5 as number | null };
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id_unidade_trabalho: auth.id_unidade_trabalho } }),
}));

function comCliente(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

/** Abre a lista do campo (Combobox com busca) e escolhe a opção. */
async function escolher(rotulo: RegExp, opcao: RegExp) {
  fireEvent.click(screen.getByLabelText(rotulo));
  fireEvent.mouseDown(await screen.findByRole("option", { name: opcao }));
}

async function abrirEdicao() {
  const { EditarDebitoContent } = await import("@/components/pagamentos/EditarDebitoContent");
  comCliente(<EditarDebitoContent id={20} />);
}

// O formulário carrega muitos módulos (ícones, combobox, roteiro): a primeira
// importação passava dos 5 s do teste. Aquecer aqui tira o custo dos testes.
beforeAll(async () => {
  await import("@/components/pagamentos/EditarDebitoContent");
}, 30_000);

beforeEach(() => {
  estado.tramitacao = "RASCUNHO";
  estado.id_contrato = null;
  estado.categoria = null;
  estado.parcelas = [
    { id: 1, id_debito: 20, numero: 1, valor: "1000.00", vencimento: "2026-10-30", status: "ABERTA" },
  ];
  createMock.mockClear();
  updateMock.mockClear();
  pushMock.mockClear();
  auth.id_unidade_trabalho = 5;
});

describe("editar solicitação de pagamento", () => {
  it("abre com os dados do débito e salva pelo PUT, voltando ao detalhe", async () => {
    await abrirEdicao();
    const descricao = await screen.findByLabelText(/Descrição/);
    expect(descricao).toHaveValue("Compra de material");
    expect(screen.getByLabelText(/^Vencimento/)).toHaveValue("2026-10-30");
    // As opções chegam depois do débito: espera o campo mostrar o escolhido.
    await waitFor(() => expect(screen.getByLabelText(/^Fornecedor/)).toHaveTextContent("Fornecedor X"));

    fireEvent.change(descricao, { target: { value: "Compra de material de limpeza" } });
    fireEvent.click(screen.getByRole("radio", { name: "Bens" }));
    fireEvent.click(screen.getByRole("button", { name: "Salvar alterações" }));

    await waitFor(() => expect(updateMock).toHaveBeenCalledTimes(1));
    expect(updateMock).toHaveBeenCalledWith(20, expect.objectContaining({
      descricao: "Compra de material de limpeza", categoria: "BENS", numero_nf: "NF-7",
      numero_ne: null, parcelas: [{ numero: 1, valor: 1000, vencimento: "2026-10-30" }],
    }));
    expect(createMock).not.toHaveBeenCalled();
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/m/pagamentos/solicitacoes/20"));
  });

  it("sem contrato, não salva sem categoria", async () => {
    await abrirEdicao();
    await screen.findByLabelText(/Descrição/);
    fireEvent.click(screen.getByRole("button", { name: "Salvar alterações" }));
    expect(await screen.findByText(/Sem contrato, escolha a categoria/)).toBeInTheDocument();
    expect(updateMock).not.toHaveBeenCalled();
    // O foco vai ao campo que falta (a primeira opção da categoria).
    expect(screen.getByRole("radio", { name: "Bens" })).toHaveFocus();
  });

  it("com contrato, a categoria não é pedida nem enviada", async () => {
    estado.id_contrato = 9;
    await abrirEdicao();
    await screen.findByLabelText(/Descrição/);
    expect(screen.queryByRole("group", { name: "Categoria" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Salvar alterações" }));
    await waitFor(() => expect(updateMock).toHaveBeenCalledTimes(1));
    expect(updateMock).toHaveBeenCalledWith(20, expect.objectContaining({
      id_contrato: 9, categoria: null,
    }));
  });

  it("débito com várias parcelas: salva sem tocar em valor nem em parcelas", async () => {
    estado.categoria = "SERVICOS";
    estado.parcelas = [
      { id: 1, id_debito: 20, numero: 1, valor: "500.00", vencimento: "2026-10-30", status: "ABERTA" },
      { id: 2, id_debito: 20, numero: 2, valor: "500.00", vencimento: "2026-11-30", status: "ABERTA" },
    ];
    await abrirEdicao();
    await screen.findByLabelText(/Descrição/);
    expect(screen.getByLabelText(/Valor total/)).toBeDisabled();
    expect(screen.queryByLabelText(/^Vencimento/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Salvar alterações" }));
    await waitFor(() => expect(updateMock).toHaveBeenCalledTimes(1));
    const corpo = updateMock.mock.calls[0][1] as Record<string, unknown>;
    expect(corpo).not.toHaveProperty("parcelas");
    expect(corpo).not.toHaveProperty("valor_total");
  });

  it("fora de rascunho/ajuste, não mostra o formulário", async () => {
    estado.tramitacao = "AGUARDANDO_GESTOR";
    await abrirEdicao();
    expect(
      await screen.findByText("Esta solicitação não pode mais ser editada"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Salvar alterações" })).toBeNull();
  });

  it("em ajuste, avisa que alteração material invalida as aprovações", async () => {
    estado.tramitacao = "AJUSTE_VALIDACAO";
    estado.categoria = "SERVICOS";
    await abrirEdicao();
    expect(await screen.findByText(/alteração material/)).toBeInTheDocument();
  });
});

describe("nova solicitação", () => {
  it("envia a categoria escolhida", async () => {
    const { FormularioDebito } = await import("@/components/pagamentos/FormularioDebito");
    comCliente(<FormularioDebito />);

    await escolher(/^Fornecedor/, /Fornecedor X/);
    await escolher(/^Natureza/, /Material de consumo/);
    await escolher(/^Fonte de recursos/, /500 - Própria/);
    fireEvent.click(screen.getByRole("radio", { name: "Obras" }));
    fireEvent.change(screen.getByLabelText(/Valor total/), { target: { value: "250.5" } });
    fireEvent.change(screen.getByLabelText(/Competência/), { target: { value: "2026-10" } });
    fireEvent.change(screen.getByLabelText(/^Vencimento/), { target: { value: "2026-11-05" } });
    fireEvent.change(screen.getByLabelText(/Descrição/), { target: { value: "Reforma" } });
    // A unidade solicitante já vem com a do usuário.
    await waitFor(() =>
      expect(screen.getByLabelText(/^Unidade solicitante/)).toHaveTextContent("Secretaria de Saúde"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Criar solicitação" }));

    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    expect(createMock).toHaveBeenCalledWith(expect.objectContaining({
      id_fornecedor: 1, id_natureza: 2, id_fonte_recursos: 3, id_unidade: 5,
      categoria: "OBRAS", id_contrato: null, competencia: "2026-10",
      parcelas: [{ numero: 1, valor: 250.5, vencimento: "2026-11-05" }],
    }));
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/m/pagamentos/solicitacoes/31"));
  });

  it("não acusa erro ao abrir; acusa ao sair do campo vazio", async () => {
    const { FormularioDebito } = await import("@/components/pagamentos/FormularioDebito");
    comCliente(<FormularioDebito />);
    const descricao = await screen.findByLabelText(/Descrição/);
    expect(screen.queryByText("Descreva em uma linha o que está sendo pago.")).toBeNull();
    expect(descricao).not.toHaveAttribute("aria-invalid", "true");

    fireEvent.blur(descricao);
    expect(await screen.findByText("Descreva em uma linha o que está sendo pago.")).toBeInTheDocument();
    expect(descricao).toHaveAttribute("aria-invalid", "true");
  });

  it("ao criar com campos faltando, não envia, lista o que falta e foca o primeiro", async () => {
    auth.id_unidade_trabalho = null;
    const { FormularioDebito } = await import("@/components/pagamentos/FormularioDebito");
    comCliente(<FormularioDebito />);
    await screen.findByLabelText(/Descrição/);
    fireEvent.click(screen.getByRole("button", { name: "Criar solicitação" }));

    expect(await screen.findByText(/Faltam \d+ campos para continuar/)).toBeInTheDocument();
    expect(screen.getByText("Escolha quem vai receber o pagamento.")).toBeInTheDocument();
    expect(screen.getByLabelText(/^Fornecedor/)).toHaveFocus();
    expect(createMock).not.toHaveBeenCalled();
    // A competência nasce no mês corrente: não está entre o que falta.
    expect(screen.queryByText("Informe o mês a que a despesa se refere.")).toBeNull();
  });
});
