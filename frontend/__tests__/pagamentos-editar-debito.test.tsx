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
import { beforeEach, describe, expect, it, vi } from "vitest";

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

function comCliente(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

async function abrirEdicao() {
  const { EditarDebitoContent } = await import("@/components/pagamentos/EditarDebitoContent");
  comCliente(<EditarDebitoContent id={20} />);
}

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
});

describe("editar solicitação de pagamento", () => {
  it("abre com os dados do débito e salva pelo PUT, voltando ao detalhe", async () => {
    await abrirEdicao();
    const descricao = await screen.findByLabelText(/Descrição/);
    expect(descricao).toHaveValue("Compra de material");
    expect(screen.getByLabelText(/Vencimento da parcela/)).toHaveValue("2026-10-30");
    // As opções chegam depois do débito: espera o select refletir o valor.
    await waitFor(() => expect(screen.getByLabelText(/Fornecedor/)).toHaveValue("1"));

    fireEvent.change(descricao, { target: { value: "Compra de material de limpeza" } });
    fireEvent.change(screen.getByLabelText(/^Categoria/), { target: { value: "BENS" } });
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
    expect(await screen.findByText("Sem contrato, a categoria é obrigatória")).toBeInTheDocument();
    expect(updateMock).not.toHaveBeenCalled();
  });

  it("com contrato, a categoria não é pedida nem enviada", async () => {
    estado.id_contrato = 9;
    await abrirEdicao();
    await screen.findByLabelText(/Descrição/);
    expect(screen.queryByLabelText(/^Categoria/)).toBeNull();
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
    expect(screen.queryByLabelText(/Vencimento da parcela/)).toBeNull();
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
    await screen.findByRole("option", { name: "Fornecedor X" });
    await screen.findByRole("option", { name: "Secretaria de Saúde" });
    await screen.findByRole("option", { name: "Material de consumo" });
    await screen.findByRole("option", { name: "500 - Própria" });

    fireEvent.change(screen.getByLabelText(/Fornecedor/), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/Natureza/), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText(/Fonte de recursos/), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText(/^Categoria/), { target: { value: "OBRAS" } });
    fireEvent.change(screen.getByLabelText(/Unidade solicitante/), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText(/Valor total/), { target: { value: "250.5" } });
    fireEvent.change(screen.getByLabelText(/Competência/), { target: { value: "2026-10" } });
    fireEvent.change(screen.getByLabelText(/Vencimento da parcela/), { target: { value: "2026-11-05" } });
    fireEvent.change(screen.getByLabelText(/Descrição/), { target: { value: "Reforma" } });
    fireEvent.click(screen.getByRole("button", { name: "Criar Solicitação" }));

    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    expect(createMock).toHaveBeenCalledWith(expect.objectContaining({
      categoria: "OBRAS", id_contrato: null,
      parcelas: [{ numero: 1, valor: 250.5, vencimento: "2026-11-05" }],
    }));
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/m/pagamentos/solicitacoes/31"));
  });
});
