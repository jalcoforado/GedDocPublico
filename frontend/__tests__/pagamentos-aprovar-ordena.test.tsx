/**
 * "Aprovar e ordenar pagamento" no detalhe da solicitação.
 *
 * O que não pode voltar: aprovar sem escolher a conta pagadora. Era o que o
 * botão fazia — o débito saía "autorizado" sem ordem de pagamento, e não havia
 * mais como pagá-lo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AutoridadeAprovarPayload, ContaElegivel } from "@/lib/api";

const conta = (id: number, nome: string, disponivel: string): ContaElegivel => ({
  id_conta: id, nome, banco: "001", agencia: "1", conta_mascarada: "***1",
  saldo_atual: disponivel, disponivel, abaixo_minimo: false, reservado: "0", bloqueado: "0",
  saldo_conciliado: disponivel, disponivel_projetado: disponivel, atualizado_em: null,
});

let contas: ContaElegivel[] = [];
const contasMock = vi.fn((_fonte: number) => Promise.resolve(contas));
const aprovarMock = vi.fn((_id: number, _p: AutoridadeAprovarPayload) => Promise.resolve({}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      pagamentos: {
        ...actual.api.pagamentos,
        contasElegiveis: contasMock,
        retencoes: {
          ...actual.api.pagamentos.retencoes,
          listarDoDebito: () =>
            Promise.resolve({ valor_bruto: "1000.00", valor_liquido: "1000.00", retencoes: [] }),
        },
        debitos: {
          ...actual.api.pagamentos.debitos,
          get: () => Promise.resolve({
            id: 20, id_fornecedor: 1, nome_fornecedor: "Fornecedor X", id_natureza: 1,
            id_fonte_recursos: 7, id_conta: null, id_conta_pagadora: null, id_contrato: null,
            valor_total: "1000.00", competencia: "2026-09", numero_ne: "NE-1", numero_nf: null,
            criticidade: "MEDIA", urgente: false, justificativa_urgencia: null,
            descricao: "Serviço de teste", status: "EM_ANALISE",
            situacao_tramitacao: "AGUARDANDO_AUTORIDADE", situacao_fila: "REGISTRADA",
            situacao_pagamento: "NAO_INICIADA", id_unidade: 1, versao: 1, lock_version: 5,
            id_gestor_decisor: null, id_validador: null, id_usuario_solicitante: 1,
            liquidacao_confirmada: true, data_liquidacao: "2026-09-01",
            criado_em: "2026-09-01T10:00:00Z", atualizado_em: null,
            parcelas: [], historico: [],
          }),
          listarPedidosAjuste: () => Promise.resolve([]),
          listarVersoes: () => Promise.resolve([]),
          listarAnexos: () => Promise.resolve([]),
          listarExcecoes: () => Promise.resolve([]),
          checklist: () => Promise.resolve([]),
          posicaoDebito: () => Promise.reject(new actual.ApiError("Sem posição na fila.", 404)),
          autoridadeAprovar: aprovarMock,
        },
      },
    },
  };
});

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Autoridade", is_super_usuario: false },
    perms: ["pagamento_autorizar"],
    loading: false,
    can: (codigo: string) => codigo === "pagamento_autorizar",
  }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

async function abrirAprovacao() {
  const { DetalheDebitoContent } = await import("@/components/pagamentos/DetalheDebitoContent");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DetalheDebitoContent id={20} />
    </QueryClientProvider>,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Aprovar e ordenar pagamento" }));
  return screen.findByRole("button", { name: "Confirmar" });
}

beforeEach(() => {
  contas = [conta(3, "Conta Movimento", "5000.00"), conta(4, "Conta Convênio", "200.00")];
  contasMock.mockClear();
  aprovarMock.mockClear();
});

describe("aprovar e ordenar pagamento", () => {
  it("lista as contas da fonte do débito e não confirma sem conta escolhida", async () => {
    const confirmar = await abrirAprovacao();
    await screen.findByRole("option", { name: /Conta Movimento/ });
    expect(contasMock).toHaveBeenCalledWith(7);
    expect(confirmar).toBeDisabled();
    fireEvent.click(confirmar);
    expect(aprovarMock).not.toHaveBeenCalled();
  });

  it("com conta que cobre o valor, envia a conta pagadora", async () => {
    const confirmar = await abrirAprovacao();
    await screen.findByRole("option", { name: /Conta Movimento/ });
    fireEvent.change(screen.getByLabelText(/Conta pagadora/), { target: { value: "3" } });
    expect(screen.queryByText(/não cobre o valor/)).toBeNull();
    fireEvent.click(confirmar);
    await waitFor(() =>
      expect(aprovarMock).toHaveBeenCalledWith(20, {
        lock_version: 5, id_conta_pagadora: 3,
        permitir_saldo_insuficiente: false, justificativa_excecao: null,
      }),
    );
  });

  it("sem saldo, só confirma com a exceção marcada E justificada", async () => {
    const confirmar = await abrirAprovacao();
    await screen.findByRole("option", { name: /Conta Convênio/ });
    fireEvent.change(screen.getByLabelText(/Conta pagadora/), { target: { value: "4" } });
    expect(await screen.findByText(/não cobre o valor/)).toBeInTheDocument();
    expect(confirmar).toBeDisabled();

    fireEvent.click(screen.getByLabelText(/Autorizar mesmo assim/));
    expect(confirmar).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Justificativa da exceção/), {
      target: { value: "Decisão judicial com prazo." },
    });
    expect(confirmar).toBeEnabled();
    fireEvent.click(confirmar);
    await waitFor(() =>
      expect(aprovarMock).toHaveBeenCalledWith(20, {
        lock_version: 5, id_conta_pagadora: 4,
        permitir_saldo_insuficiente: true,
        justificativa_excecao: "Decisão judicial com prazo.",
      }),
    );
  });

  it("fonte sem conta pagadora: avisa e não deixa confirmar", async () => {
    contas = [];
    const confirmar = await abrirAprovacao();
    expect(await screen.findByText(/Nenhuma conta pagadora ativa/)).toBeInTheDocument();
    expect(confirmar).toBeDisabled();
  });
});
