/**
 * Task 7 (F2 pagamentos): pendências de ajuste e versões no detalhe, e o
 * bloco de pendências na caixa de trabalho.
 *
 * Duas propriedades do produto ficam cobertas aqui:
 *  1. pedido de ajuste ABERTO bloqueia o reenvio ("Reenviar para análise")
 *     — sem isso a unidade reenviaria e o backend devolveria 409 sem
 *     explicação nenhuma na tela;
 *  2. `minhaFila().pendencias_ajuste` aparece na caixa de trabalho, linkando
 *     para o detalhe do débito — sem isso o responsável só descobre que tem
 *     um ajuste para responder abrindo cada solicitação manualmente.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  DebitoOut,
  MinhaFila,
  PedidoAjuste,
} from "@/lib/api";

const debitoBase: DebitoOut = {
  id: 1,
  id_fornecedor: 10,
  nome_fornecedor: "Fornecedor Teste",
  id_natureza: 1,
  id_fonte_recursos: 1,
  id_conta: null,
  id_conta_pagadora: null,
  id_contrato: null,
  valor_total: "1000.00",
  competencia: "2026-08",
  numero_ne: null,
  numero_nf: null,
  criticidade: "normal",
  urgente: false,
  justificativa_urgencia: null,
  descricao: "Despesa de teste",
  status: "ativo" as any,
  id_usuario_solicitante: 1,
  liquidacao_confirmada: false,
  data_liquidacao: null,
  criado_em: "2026-08-01T10:00:00Z",
  atualizado_em: null,
  situacao_tramitacao: "AJUSTE_GESTOR",
  situacao_fila: "NAO_REGISTRADA",
  situacao_pagamento: "NAO_INICIADA",
  id_unidade: 1,
  versao: 1,
  lock_version: 3,
  id_gestor_decisor: null,
  id_validador: null,
};

const pedidoAberto: PedidoAjuste = {
  id: 55,
  id_debito: 1,
  versao_debito: 1,
  etapa_solicitante: "GESTOR",
  id_usuario_solicitante: 2,
  motivo: "Falta anexar a nota fiscal",
  descricao: "A nota fiscal não confere com o valor solicitado.",
  transacao_responsavel: "pagamento_solicitar",
  tipo: "NAO_MATERIAL",
  prazo: null,
  campos_relacionados: null,
  situacao: "ABERTO",
  resposta: null,
  id_usuario_resposta: null,
  respondido_em: null,
  resolvido_em: null,
  criado_em: "2026-08-10T09:00:00Z",
};

const getMock = vi.fn(() =>
  Promise.resolve({ ...debitoBase, parcelas: [], historico: [] }),
);
const listarPedidosMock = vi.fn(() => Promise.resolve([pedidoAberto]));
const listarVersoesMock = vi.fn(() => Promise.resolve([]));
const responderAjusteMock = vi.fn();
const solicitarAjusteMock = vi.fn();
const criarPedidoAjusteMock = vi.fn();
const responderPedidoAjusteMock = vi.fn();
const cancelarPedidoAjusteMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      pagamentos: {
        debitos: {
          get: getMock,
          listarPedidosAjuste: listarPedidosMock,
          listarVersoes: listarVersoesMock,
          responderAjuste: responderAjusteMock,
          solicitarAjuste: solicitarAjusteMock,
          criarPedidoAjuste: criarPedidoAjusteMock,
          responderPedidoAjuste: responderPedidoAjusteMock,
          cancelarPedidoAjuste: cancelarPedidoAjusteMock,
          confirmarLiquidacao: vi.fn(),
        },
        caixa: { painel: () => Promise.resolve([]) },
        minhaFila: () =>
          Promise.resolve({
            solicitar: [],
            validar: [],
            encaminhar: [],
            autorizar: [],
            liberar: [],
            pagar: [],
            pendencias_ajuste: [
              {
                id_pedido: 55,
                id_debito: 1,
                descricao_debito: "Despesa de teste",
                motivo: "Falta anexar a nota fiscal",
                prazo: null,
                criado_em: "2026-08-10T09:00:00Z",
                etapa_solicitante: "GESTOR",
              },
            ],
          } satisfies MinhaFila),
      },
    },
  };
});

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Solicitante", is_super_usuario: false },
    perms: ["pagamento_solicitar"],
    loading: false,
    can: (codigo: string) => codigo === "pagamento_solicitar",
  }),
}));

const toastErrorMock = vi.fn();

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: toastErrorMock, info: vi.fn(), warning: vi.fn() }),
}));

function renderComQueryClient(children: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return { client, ...render(<QueryClientProvider client={client}>{children}</QueryClientProvider>) };
}

describe("Detalhe da solicitação — pendências de ajuste (F2)", () => {
  it("pedido ABERTO bloqueia o botão de reenvio, com o motivo explicado", async () => {
    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={1} />);

    await waitFor(() => expect(screen.getByText(/falta anexar a nota fiscal/i)).toBeInTheDocument());

    // Situação do pedido é ícone + texto, não só cor.
    expect(screen.getByText("Aguardando resposta")).toBeInTheDocument();

    const reenviar = screen.getByRole("button", { name: /reenviar para análise/i });
    expect(reenviar).toBeDisabled();
    expect(reenviar).toHaveAttribute("title", expect.stringMatching(/pedido de ajuste em aberto/i));
  });

  it("libera o reenvio quando não há mais pedido ABERTO", async () => {
    listarPedidosMock.mockResolvedValueOnce([
      { ...pedidoAberto, situacao: "RESPONDIDO", resposta: "Nota fiscal anexada." },
    ]);
    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={1} />);

    await waitFor(() => expect(screen.getByText("Respondido")).toBeInTheDocument());
    const reenviar = screen.getByRole("button", { name: /reenviar para análise/i });
    expect(reenviar).not.toBeDisabled();
  });

  it("409 no reenvio (pedido ABERTO surgiu entre o carregamento e o clique): mostra o conflito, recarrega os dados e NÃO repete a mutation", async () => {
    // Tela abriu com o único pedido já RESPONDIDO — botão liberado — mas o
    // backend recusa com 409 no exato formato que `lib/api.ts` lança para
    // qualquer resposta HTTP não-ok (ApiError real, não um objeto solto).
    listarPedidosMock.mockResolvedValueOnce([
      { ...pedidoAberto, situacao: "RESPONDIDO", resposta: "Nota fiscal anexada." },
    ]);
    const { ApiError } = await import("@/lib/api");
    responderAjusteMock.mockRejectedValueOnce(
      new ApiError(
        "Há pedido(s) de ajuste ainda não respondido(s): #55: Falta anexar a nota fiscal.",
        409,
      ),
    );

    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    const { client } = renderComQueryClient(<DetalheDebitoContent id={1} />);
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const reenviar = await screen.findByRole("button", { name: /reenviar para análise/i });
    expect(reenviar).not.toBeDisabled();

    fireEvent.click(reenviar);

    // Mensagem de conflito visível ao usuário (via toast).
    await waitFor(() =>
      expect(toastErrorMock).toHaveBeenCalledWith(
        expect.stringMatching(/pedido de ajuste em aberto/i),
      ),
    );

    // Dados recarregados: as três queries do detalhe são invalidadas.
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["pag-debito", 1] }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["pag-pedidos-ajuste", 1] }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["pag-versoes", 1] }),
    );

    // A mutation de reenvio NÃO é repetida automaticamente após o 409.
    expect(responderAjusteMock).toHaveBeenCalledTimes(1);
  });
});

describe("Caixa de pagamentos — pendências para você responder (F2)", () => {
  it("lista a pendência de ajuste e linka para o detalhe do débito", async () => {
    const { default: PagamentosHomePage } = await import("@/app/(app)/m/pagamentos/page");
    renderComQueryClient(<PagamentosHomePage />);

    await waitFor(() =>
      expect(screen.getByText("Pendências para você responder")).toBeInTheDocument(),
    );
    const link = await screen.findByRole("link", {
      name: /despesa de teste.*falta anexar a nota fiscal/i,
    });
    expect(link).toHaveAttribute("href", "/m/pagamentos/solicitacoes/1");
  });
});
